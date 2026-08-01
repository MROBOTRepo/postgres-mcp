# MCP PostgreSQL → Copilot Studio

## PASO 1: Preparar (en tu PowerShell)

```powershell
cd C:\Users\mreba\MCP_Datalake

python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## PASO 2: Configurar las credenciales

Editá el archivo `.env.example`:

```powershell
notepad .env.example
```

Reemplazá esta línea:
```
PGPASSWORD=REEMPLAZA_CON_PASSWORD_NUEVA
```

Con una password nueva y fuerte (ej: `MyNewPass123!@`).

Guardá como `.env` (File → Save As, y escribí el nombre como `.env`).

**IMPORTANTE:** Antes de ejecutar server.py, tenes que rotar la password en Azure:
- Portal Azure → tu servidor PostgreSQL → Reset password → copilot_reader
- Usá la misma password que pusiste en `.env`

## PASO 3: Levantar el server

```powershell
python server.py
```

Debería decir:
```
MCP escuchando en http://0.0.0.0:8000/mcp
```

**No cierres esta ventana.** Abrí una ventana NUEVA de PowerShell.

## PASO 4: Publicar en internet (nueva ventana PowerShell)

```powershell
winget install Microsoft.devtunnel
devtunnel user login
devtunnel host -p 8000 --allow-anonymous
```

Te va a devolver algo como:
```
https://abc123-8000.usw2.devtunnels.ms
```

**Anotá `abc123-8000.usw2.devtunnels.ms` — es tu HOST.**

## PASO 5: Crear el conector en Power Platform

1. Abrí https://make.powerapps.com
2. Izquierda → Custom connectors
3. New custom connector → Import an OpenAPI file
4. Subí el archivo `copilot-connector.yaml` de esta carpeta
5. Cuando cargue, busca la línea `host:` y reemplazá con tu HOST del PASO 4
6. Arriba a la derecha → Update connector
7. Cuando termine → Close

## PASO 6: Agregar el conector al agente

1. Abrí tu agente en https://copilotstudio.microsoft.com
2. Izquierda → Tools
3. Add a tool → Model Context Protocol
4. Elegí DatalakePostgres
5. Add

Deberías ver 5 herramientas: salud, listar_tablas, describir_tabla, valores_distintos, consultar_sql.

## PASO 7: Configurar el agente

1. Izquierda → Settings
2. Buscá "Orchestration" o "Generative AI"
3. Cambiá de "Classic" a "Generative"
4. Save

## PASO 8: Probar

Arriba a la derecha → Test

Escribí:
```
¿Estás conectado a la base?
```

Si responde algo sobre PostgreSQL, **funcionó todo**.

---

## Si algo falla

**"No module named psycopg"**
→ No corriste `pip install -r requirements.txt`

**"dmdl-server.postgres.database.azure.com: Temporary failure in name resolution"**
→ Sin internet o firewall de Azure bloquea tu IP. En Azure Portal:
   - Tu servidor PostgreSQL → Networking → Firewall rules
   - Add current client IP address

**"password authentication failed"**
→ Password incorrecta en `.env` o no la rotaste en Azure.

**El agente no ve las herramientas**
→ ¿Está en modo Generative? (PASO 7)
→ ¿El conector se creó sin errores? (PASO 5)

**El agente ve las herramientas pero no las llama**
→ Confirmá que está en modo Generative, no Classic.

---

**Dudas en algún PASO específico, decime cuál y te ayudo.**
