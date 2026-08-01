"""WSGI Proxy a FastMCP - Redirige requests a puerto 9000"""
import urllib.request
import logging

logging.basicConfig(level="INFO")
LOG = logging.getLogger("proxy")

def app(environ, start_response):
    """WSGI app que hace proxy a FastMCP en 9000"""
    path = environ.get('PATH_INFO', '/')
    method = environ['REQUEST_METHOD']
    content_length = int(environ.get('CONTENT_LENGTH', 0) or 0)
    body = environ['wsgi.input'].read(content_length) if content_length > 0 else b''
    
    try:
        url = f'http://127.0.0.1:9000{path}'
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
        LOG.error(f"Proxy error: {e}")
        start_response('503 Service Unavailable', [('Content-Type', 'text/plain')])
        return [b'Service Unavailable\n']
