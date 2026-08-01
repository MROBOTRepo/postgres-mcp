"""Entry point - Inicia FastMCP en thread y sirve WSGI"""
import os
import sys
import threading
import time
import logging

logging.basicConfig(level="INFO")
LOG = logging.getLogger("app")

# Importar server y config
from server import mcp, LOG as server_log

# Iniciar FastMCP en thread ANTES de que Gunicorn intente conectar
LOG.info("Iniciando FastMCP en thread...")
mcp_thread = threading.Thread(
    target=lambda: mcp.run(transport="streamable-http"),
    daemon=True
)
mcp_thread.start()
time.sleep(3)  # Espera a que FastMCP inicie
LOG.info("FastMCP iniciado")

# WSGI app simple
def app(environ, start_response):
    start_response('200 OK', [('Content-Type', 'text/plain')])
    return [b'MCP Server running\n']
