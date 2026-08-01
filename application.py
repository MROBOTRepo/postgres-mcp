"""Entry point que Oryx detecta - Limpia caché de Oryx al iniciar"""
import os
import sys

# Limpiar caché de Oryx que interfiere con deployments
print("⚙️  Limpiando caché de Oryx...", file=sys.stderr)
for file in ['/home/site/wwwroot/oryx-manifest.toml', '/home/site/wwwroot/output.tar.zst']:
    if os.path.exists(file):
        try:
            os.remove(file)
            print(f"✓ Eliminado: {file}", file=sys.stderr)
        except Exception as e:
            print(f"⚠ No se pudo eliminar {file}: {e}", file=sys.stderr)

from server import app

__all__ = ['app']
