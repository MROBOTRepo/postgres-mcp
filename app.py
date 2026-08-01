"""Entry point que Oryx detecta - Inicia FastMCP en thread"""
import os
import sys
import threading
import time

from server import mcp

# Iniciar FastMCP en thread
print("⚙️  Iniciando FastMCP en thread...", file=sys.stderr)
mcp_thread = threading.Thread(
    target=lambda: mcp.run(transport="streamable-http"),
    daemon=True
)
mcp_thread.start()
time.sleep(2)  # Espera a que FastMCP inicie

# WSGI app
def app(environ, start_response):
    """Simple WSGI - solo retorna 200"""
    start_response('200 OK', [('Content-Type', 'text/plain')])
    return [b'MCP Server running\n']
