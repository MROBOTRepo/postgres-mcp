"""
Prueba directa contra PostgreSQL. Sin MCP, sin conector, sin Power Platform.

Es el primer eslabon de la cadena: si esto no anda, nada de lo demas puede andar.
Confirma credenciales, SSL, firewall y permisos del usuario.

Uso:
    python probar_postgres.py
"""

import os
import sys

try:
    import psycopg
except ImportError:
    print('Falta el driver. Instalalo con:  pip install "psycopg[binary]" python-dotenv')
    sys.exit(1)

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


HOST = os.getenv("PGHOST", "dmdl-server.postgres.database.azure.com")
PORT = os.getenv("PGPORT", "5432")
BASE = os.getenv("PGDATABASE", "postgres")
USER = os.getenv("PGUSER", "copilot_reader")
PASS = os.getenv("PGPASSWORD") or ""

if not PASS:
    PASS = input("Password de copilot_reader: ").strip()

CONN = (
    f"host={HOST} port={PORT} dbname={BASE} user={USER} password={PASS} "
    f"sslmode=require connect_timeout=15"
)


def main() -> int:
    print(f"\nConectando a {HOST}:{PORT}/{BASE} como {USER} ...\n")

    try:
        conn = psycopg.connect(CONN)
    except psycopg.OperationalError as e:
        msg = str(e)
        print(f"NO CONECTA:\n  {msg}\n")
        if "timeout" in msg.lower() or "unreachable" in msg.lower():
            print("Causa mas probable: el firewall de Azure Postgres bloquea tu IP.")
            print("  Portal Azure -> tu servidor -> Networking -> Firewall rules")
            print("  -> Add current client IP address -> Save")
        elif "password" in msg.lower() or "authentication" in msg.lower():
            print("Causa mas probable: password incorrecta o usuario inexistente.")
        elif "does not exist" in msg.lower():
            print(f"La base '{BASE}' no existe en ese servidor.")
        return 1

    with conn:
        with conn.cursor() as cur:

            # --- 1. Identidad ---------------------------------------------
            cur.execute("SELECT version(), current_user, current_database()")
            ver, usr, db = cur.fetchone()
            print("CONECTADO")
            print(f"  {ver.split(',')[0]}")
            print(f"  usuario: {usr}   base: {db}\n")

            # --- 2. Que tablas ve este usuario -----------------------------
            cur.execute(
                """
                SELECT n.nspname, c.relname,
                       CASE c.relkind WHEN 'r' THEN 'tabla' WHEN 'v' THEN 'vista'
                                      WHEN 'm' THEN 'vista mat.' ELSE c.relkind::text END,
                       GREATEST(c.reltuples::bigint, 0)
                FROM pg_class c
                JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE c.relkind IN ('r','v','m','p')
                  AND n.nspname NOT IN ('pg_catalog','information_schema')
                  AND has_table_privilege(c.oid,'SELECT')
                ORDER BY 1, 2
                """
            )
            tablas = cur.fetchall()

            if not tablas:
                print("El usuario no ve NINGUNA tabla.")
                print("Falta correr los GRANT. Mira setup_readonly.sql")
                return 1

            print(f"TABLAS VISIBLES ({len(tablas)}):")
            for esq, tab, tipo, filas in tablas:
                print(f"  {esq}.{tab:<32} {tipo:<12} ~{filas} filas")

            # --- 3. Detalle de la primera tabla ---------------------------
            esq, tab = tablas[0][0], tablas[0][1]
            ref = f'"{esq}"."{tab}"'
            print(f"\nDETALLE DE {esq}.{tab}\n")

            cur.execute(
                """
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_schema = %s AND table_name = %s
                ORDER BY ordinal_position
                """,
                (esq, tab),
            )
            cols = cur.fetchall()
            print("  Columnas:")
            for nom, tipo, nul in cols:
                print(f"    {nom:<28} {tipo:<24} {'NULL' if nul == 'YES' else 'NOT NULL'}")

            cur.execute(f"SELECT COUNT(*) FROM {ref}")
            print(f"\n  Filas reales: {cur.fetchone()[0]}")

            cur.execute(f"SELECT * FROM {ref} LIMIT 5")
            nombres = [d.name for d in cur.description]
            print(f"\n  Primeras 5 filas:")
            print("    " + " | ".join(nombres))
            for fila in cur.fetchall():
                print("    " + " | ".join(str(v)[:22] for v in fila))

            # --- 4. Confirmar que es de solo lectura ----------------------
            print("\nVERIFICACION DE SOLO LECTURA")
            try:
                cur.execute(f"CREATE TEMP TABLE _prueba_escritura (x int)")
                conn.rollback()
                print("  ATENCION: el usuario puede crear objetos.")
                print("  Corre setup_readonly.sql para restringirlo.")
            except psycopg.Error:
                conn.rollback()
                print("  OK: el usuario no puede escribir.")

    print("\nListo. La base responde y el usuario lee bien.")
    print("Siguiente paso: levantar server.py\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
