"""MCP server de solo lectura sobre PostgreSQL con pg8000."""

import logging
import os
import re
import ssl

import pg8000.native
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

load_dotenv()

logging.basicConfig(level="INFO", format="%(asctime)s %(levelname)s %(name)s :: %(message)s")
LOG = logging.getLogger("pg-mcp")

PGHOST = os.getenv("PGHOST")
PGDATABASE = os.getenv("PGDATABASE")
PGUSER = os.getenv("PGUSER")
PGPASSWORD = os.getenv("PGPASSWORD")
PGPORT = int(os.getenv("PGPORT", "5432"))
PGSSLMODE = os.getenv("PGSSLMODE", "require")
ALLOWED_SCHEMAS = tuple(s.strip() for s in os.getenv("ALLOWED_SCHEMAS", "public").split(",") if s.strip())
MAX_ROWS = int(os.getenv("MAX_ROWS", "500"))
# Detectar si se ejecuta bajo Gunicorn (importado)
_IS_GUNICORN = "gunicorn" in os.environ.get("SERVER_SOFTWARE", "") or os.getenv("_SERVER_SOFTWARE") == "gunicorn"
# En Azure App Service, usar WEBSITES_PORT; sino, usar HTTP_PORT
# Si es Gunicorn, FastMCP usa puerto 9000; si es main, usa 8000
HTTP_PORT = 9000 if _IS_GUNICORN else int(os.getenv("WEBSITES_PORT", os.getenv("HTTP_PORT", "8000")))
# Host de FastMCP: 127.0.0.1 (solo local) si es Gunicorn (proxy reenvía), 0.0.0.0 si es desarrollo
FASTMCP_HOST = "127.0.0.1" if _IS_GUNICORN else "0.0.0.0"
HTTP_HOST = os.getenv("HTTP_HOST", FASTMCP_HOST)


def get_connection():
    ssl_context = ssl.create_default_context() if PGSSLMODE == "require" else None
    return pg8000.native.connect(
        host=PGHOST, port=PGPORT, database=PGDATABASE, user=PGUSER, password=PGPASSWORD,
        ssl_context=ssl_context, timeout=15
    )


_COMMENTS = re.compile(r"(--[^\n]*)|(/\*.*?\*/)", re.DOTALL)
_FORBIDDEN = re.compile(
    r"\b(insert|update|delete|drop|alter|create|truncate|grant|revoke|copy|vacuum|analyze|reindex|"
    r"cluster|comment|call|do|merge|refresh|listen|notify|unlisten|prepare|execute|deallocate|discard|"
    r"lock|begin|commit|rollback|savepoint|checkpoint|reset|pg_read_file|pg_read_binary_file|pg_ls_dir|"
    r"pg_sleep|lo_import|lo_export|dblink|pg_terminate_backend|pg_cancel_backend|set_config|current_setting)\b",
    re.IGNORECASE
)


def sanear(sql):
    if not sql or not sql.strip():
        raise ValueError("Consulta vacia")
    limpio = _COMMENTS.sub(" ", sql).strip().rstrip(";").strip()
    if not limpio:
        raise ValueError("Solo comentarios")
    if ";" in limpio:
        raise ValueError("Solo una sentencia permitida")
    if not re.match(r"^\s*(select|with)\b", limpio, re.IGNORECASE):
        raise ValueError("Solo SELECT permitido")
    if _FORBIDDEN.search(limpio):
        raise ValueError("Palabra clave no permitida")
    if re.search(r"\binto\b", limpio, re.IGNORECASE) and not re.search(r"\binsert\s+into\b", limpio, re.IGNORECASE):
        raise ValueError("SELECT INTO no permitido")
    if re.search(r"\bfor\s+(update|share)\b", limpio, re.IGNORECASE):
        raise ValueError("Locks no permitidos")
    return limpio


def jsonable(v):
    if isinstance(v, (int, float, str, bool, type(None))):
        return v
    if isinstance(v, (list, tuple)):
        return [jsonable(x) for x in v]
    if isinstance(v, dict):
        return {k: jsonable(val) for k, val in v.items()}
    return str(v)


def ejecutar(sql):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SET statement_timeout = '15s'")
            cur.execute("SET default_transaction_read_only = on")
            cur.execute(sql)
            filas = cur.fetchmany(MAX_ROWS + 1)

        truncado = len(filas) > MAX_ROWS
        filas = filas[:MAX_ROWS]

        if filas and hasattr(filas[0], '__iter__') and not isinstance(filas[0], str):
            cols = [desc[0] for desc in cur.description] if cur.description else []
            datos = [{cols[i]: jsonable(v) for i, v in enumerate(f)} for f in filas]
        else:
            datos = [jsonable(f) for f in filas]

        return {"filas": datos, "cantidad_filas": len(datos), "truncado": truncado}
    finally:
        conn.close()


mcp = FastMCP("postgres-dmdl", host=FASTMCP_HOST, port=HTTP_PORT)


@mcp.tool()
def salud():
    """Verifica conexion a Postgres."""
    try:
        conn = get_connection()
        with conn.cursor() as cur:
            cur.execute("SELECT version(), current_user")
            ver, usr = cur.fetchone()
        conn.close()
        return {"estado": "ok", "version": ver, "usuario": usr}
    except Exception as e:
        return {"estado": "error", "error": str(e)}


@mcp.tool()
def listar_tablas():
    """Lista tablas y vistas disponibles."""
    sql = "SELECT c.relname, n.nspname, CASE c.relkind WHEN 'r' THEN 'tabla' WHEN 'v' THEN 'vista' ELSE c.relkind::text END FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace WHERE c.relkind IN ('r','v','m') AND n.nspname = ANY(%s) AND has_table_privilege(c.oid,'SELECT') ORDER BY n.nspname, c.relname"
    try:
        conn = get_connection()
        with conn.cursor() as cur:
            cur.execute(sql, (list(ALLOWED_SCHEMAS),))
            filas = cur.fetchall()
        conn.close()
        tablas = [{"tabla": f[0], "esquema": f[1], "tipo": f[2]} for f in filas]
        return {"tablas": tablas, "esquemas_visibles": list(ALLOWED_SCHEMAS)}
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
def describir_tabla(nombre_tabla):
    """Describe columnas de una tabla."""
    if "." in nombre_tabla:
        esquema, tabla = nombre_tabla.split(".", 1)
    else:
        esquema, tabla = ALLOWED_SCHEMAS[0], nombre_tabla

    sql = "SELECT a.attname, format_type(a.atttypid, a.atttypmod) FROM pg_attribute a JOIN pg_class c ON c.oid = a.attrelid JOIN pg_namespace n ON n.oid = c.relnamespace WHERE c.relname = %s AND n.nspname = %s AND a.attnum > 0 AND NOT a.attisdropped ORDER BY a.attnum"
    try:
        conn = get_connection()
        with conn.cursor() as cur:
            cur.execute(sql, (tabla, esquema))
            filas = cur.fetchall()
        conn.close()
        if not filas:
            return {"error": "Tabla no encontrada"}
        columnas = [{"columna": f[0], "tipo": f[1]} for f in filas]
        return {"tabla": nombre_tabla, "columnas": columnas}
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
def valores_distintos(nombre_tabla, columna):
    """Lista valores distintos de una columna."""
    if "." in nombre_tabla:
        esquema, tabla = nombre_tabla.split(".", 1)
    else:
        esquema, tabla = ALLOWED_SCHEMAS[0], nombre_tabla

    try:
        conn = get_connection()
        with conn.cursor() as cur:
            query = f'SELECT "{columna}" AS valor, COUNT(*) AS frecuencia FROM "{esquema}"."{tabla}" GROUP BY "{columna}" ORDER BY COUNT(*) DESC LIMIT 50'
            cur.execute(query)
            filas = cur.fetchall()
        conn.close()
        valores = [{"valor": f[0], "frecuencia": f[1]} for f in filas]
        return {"tabla": nombre_tabla, "columna": columna, "valores": valores}
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
def consultar_sql(consulta):
    """Ejecuta un SELECT de solo lectura."""
    try:
        sql = sanear(consulta)
        res = ejecutar(sql)
        res["sql_ejecutado"] = sql
        return res
    except ValueError as e:
        return {"error": str(e), "rechazado": True}
    except Exception as e:
        return {"error": str(e)}


def app(environ, start_response):
    """WSGI proxy - redirige /mcp/* a FastMCP en puerto 9000."""
    import urllib.request
    import traceback

    path = environ.get('PATH_INFO', '')
    if path.startswith('/mcp/'):
        try:
            method = environ['REQUEST_METHOD']
            content_length = int(environ.get('CONTENT_LENGTH', 0) or 0)
            body = environ['wsgi.input'].read(content_length) if content_length > 0 else b''

            # FastMCP expone en /, Copilot llama a /
            url = f'http://127.0.0.1:9000{path}'
            LOG.debug(f"Proxy request: {method} {url}")

            req = urllib.request.Request(
                url,
                data=body if method != 'GET' else None,
                method=method
            )
            for header in environ:
                if header.startswith('HTTP_'):
                    header_name = header[5:].replace('_', '-')
                    req.add_header(header_name, environ[header])

            with urllib.request.urlopen(req, timeout=30) as resp:
                status = f"{resp.status} {resp.reason}"
                headers = [(k, v) for k, v in resp.headers.items()]
                response_body = resp.read()
                LOG.debug(f"Proxy response: {status}, size={len(response_body)}")
                start_response(status, headers)
                return [response_body]
        except Exception as e:
            LOG.error(f"Proxy error: {e}\n{traceback.format_exc()}")
            start_response('503 Service Unavailable', [('Content-Type', 'text/plain')])
            return [b'MCP Backend unavailable\n']

    start_response('200 OK', [('Content-Type', 'text/plain')])
    return [b'MCP Server (proxy mode)\n']


if __name__ == "__main__":
    # FastMCP es el servidor principal en puerto 8000
    LOG.info("Conectado a %s/%s como %s", PGHOST, PGDATABASE, PGUSER)
    LOG.info("FastMCP servidor en http://0.0.0.0:8000/")

    # Crear nuevo FastMCP en puerto 8000 (accesible)
    mcp_server = FastMCP("postgres-dmdl", host="0.0.0.0", port=8000)

    # Re-registrar todas las herramientas en el nuevo servidor
    @mcp_server.tool()
    def salud():
        """Verifica conexion a Postgres."""
        try:
            conn = get_connection()
            with conn.cursor() as cur:
                cur.execute("SELECT version(), current_user")
                ver, usr = cur.fetchone()
            conn.close()
            return {"estado": "ok", "version": ver, "usuario": usr}
        except Exception as e:
            return {"estado": "error", "error": str(e)}

    @mcp_server.tool()
    def listar_tablas():
        """Lista tablas y vistas disponibles."""
        sql = "SELECT c.relname, n.nspname, CASE c.relkind WHEN 'r' THEN 'tabla' WHEN 'v' THEN 'vista' ELSE c.relkind::text END FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace WHERE c.relkind IN ('r','v','m') AND n.nspname = ANY(%s) AND has_table_privilege(c.oid,'SELECT') ORDER BY n.nspname, c.relname"
        try:
            conn = get_connection()
            with conn.cursor() as cur:
                cur.execute(sql, (list(ALLOWED_SCHEMAS),))
                filas = cur.fetchall()
            conn.close()
            tablas = [{"tabla": f[0], "esquema": f[1], "tipo": f[2]} for f in filas]
            return {"tablas": tablas, "esquemas_visibles": list(ALLOWED_SCHEMAS)}
        except Exception as e:
            return {"error": str(e)}

    @mcp_server.tool()
    def describir_tabla(nombre_tabla):
        """Describe columnas de una tabla."""
        if "." in nombre_tabla:
            esquema, tabla = nombre_tabla.split(".", 1)
        else:
            esquema, tabla = ALLOWED_SCHEMAS[0], nombre_tabla

        sql = "SELECT a.attname, format_type(a.atttypid, a.atttypmod) FROM pg_attribute a JOIN pg_class c ON c.oid = a.attrelid JOIN pg_namespace n ON n.oid = c.relnamespace WHERE c.relname = %s AND n.nspname = %s AND a.attnum > 0 AND NOT a.attisdropped ORDER BY a.attnum"
        try:
            conn = get_connection()
            with conn.cursor() as cur:
                cur.execute(sql, (tabla, esquema))
                filas = cur.fetchall()
            conn.close()
            if not filas:
                return {"error": "Tabla no encontrada"}
            columnas = [{"columna": f[0], "tipo": f[1]} for f in filas]
            return {"tabla": nombre_tabla, "columnas": columnas}
        except Exception as e:
            return {"error": str(e)}

    @mcp_server.tool()
    def valores_distintos(nombre_tabla, columna):
        """Lista valores distintos de una columna."""
        if "." in nombre_tabla:
            esquema, tabla = nombre_tabla.split(".", 1)
        else:
            esquema, tabla = ALLOWED_SCHEMAS[0], nombre_tabla

        try:
            conn = get_connection()
            with conn.cursor() as cur:
                query = f'SELECT "{columna}" AS valor, COUNT(*) AS frecuencia FROM "{esquema}"."{tabla}" GROUP BY "{columna}" ORDER BY COUNT(*) DESC LIMIT 50'
                cur.execute(query)
                filas = cur.fetchall()
            conn.close()
            valores = [{"valor": f[0], "frecuencia": f[1]} for f in filas]
            return {"tabla": nombre_tabla, "columna": columna, "valores": valores}
        except Exception as e:
            return {"error": str(e)}

    @mcp_server.tool()
    def consultar_sql(consulta):
        """Ejecuta un SELECT de solo lectura."""
        try:
            sql = sanear(consulta)
            res = ejecutar(sql)
            res["sql_ejecutado"] = sql
            return res
        except ValueError as e:
            return {"error": str(e), "rechazado": True}
        except Exception as e:
            return {"error": str(e)}

    # Ejecutar servidor
    mcp_server.run(transport="streamable-http")
