"""WSGI app - Inicia FastMCP y proxy WSGI"""
import logging
import os
import threading
import urllib.request
import traceback

logging.basicConfig(level="INFO", format="%(asctime)s %(levelname)s %(name)s :: %(message)s")
LOG = logging.getLogger("app")

# Importar server para obtener herramientas y config
from server import mcp, FASTMCP_HOST, HTTP_PORT, PGHOST, PGDATABASE, PGUSER

# Iniciar FastMCP en thread
LOG.info("Inicializando FastMCP...")
mcp_thread = threading.Thread(
    target=lambda: mcp.run(transport="streamable-http"),
    daemon=True
)
mcp_thread.start()
LOG.info("FastMCP iniciado en http://%s:%d", FASTMCP_HOST, HTTP_PORT)


def app(environ, start_response):
    """WSGI proxy - reenvía a FastMCP en 127.0.0.1:9000"""
    path = environ.get('PATH_INFO', '')

    if path.startswith('/'):
        try:
            method = environ['REQUEST_METHOD']
            content_length = int(environ.get('CONTENT_LENGTH', 0) or 0)
            body = environ['wsgi.input'].read(content_length) if content_length > 0 else b''

            url = f'http://{FASTMCP_HOST}:{HTTP_PORT}{path}'
            LOG.debug(f"Proxy: {method} {url}")

            req = urllib.request.Request(url, data=body if method != 'GET' else None, method=method)
            for header in environ:
                if header.startswith('HTTP_'):
                    header_name = header[5:].replace('_', '-')
                    req.add_header(header_name, environ[header])

            with urllib.request.urlopen(req, timeout=30) as resp:
                status = f"{resp.status} {resp.reason}"
                headers = [(k, v) for k, v in resp.headers.items()]
                response_body = resp.read()
                start_response(status, headers)
                return [response_body]
        except Exception as e:
            LOG.error(f"Proxy error: {e}\n{traceback.format_exc()}")
            start_response('503 Service Unavailable', [('Content-Type', 'text/plain')])
            return [b'Service Unavailable\n']

    start_response('404 Not Found', [('Content-Type', 'text/plain')])
    return [b'Not Found\n']
