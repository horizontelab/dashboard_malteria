"""Servidor web del dashboard: arma al arrancar, re-arma todos los dias y pide clave."""
import base64
import hmac
import os
import threading
import time
import traceback
from datetime import datetime, timedelta
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from zoneinfo import ZoneInfo

from armar_dashboard import armar

TZ = ZoneInfo("America/Argentina/Buenos_Aires")
HORA = int(os.environ.get("HORA_ACTUALIZACION", "6"))      # 6 = 6:00 de la maniana
USUARIO = os.environ.get("DASHBOARD_USUARIO", "socias")
CLAVE = os.environ.get("DASHBOARD_CLAVE", "")              # vacia = sin clave (solo para probar)
CARPETA = "dist"
candado = threading.Lock()


def actualizar():
    if not candado.acquire(blocking=False):                 # si ya se esta armando, no arrancar otro
        return
    try:
        print(f"[{datetime.now(TZ):%d/%m %H:%M}] Armando dashboard...", flush=True)
        datos = armar(CARPETA)
        ok = sum(e["ok"] for e in datos["estado"])
        print(f"[{datetime.now(TZ):%d/%m %H:%M}] Listo: {ok}/{len(datos['estado'])} bloques OK", flush=True)
    except Exception:
        traceback.print_exc()
    finally:
        candado.release()


def programador():
    """Duerme hasta la proxima HORA en punto y actualiza. Para siempre."""
    while True:
        ahora = datetime.now(TZ)
        proxima = ahora.replace(hour=HORA, minute=0, second=0, microsecond=0)
        if proxima <= ahora:
            proxima += timedelta(days=1)
        time.sleep((proxima - ahora).total_seconds())
        actualizar()


class Manejador(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=CARPETA, **kwargs)

    def autorizado(self):
        if not CLAVE:
            return True
        cabecera = self.headers.get("Authorization", "")
        if not cabecera.startswith("Basic "):
            return False
        try:
            usuario, _, clave = base64.b64decode(cabecera[6:]).decode().partition(":")
        except Exception:
            return False
        return hmac.compare_digest(usuario, USUARIO) and hmac.compare_digest(clave, CLAVE)

    def responder(self, codigo, texto):
        cuerpo = texto.encode("utf-8")
        self.send_response(codigo)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(cuerpo)))
        self.end_headers()
        self.wfile.write(cuerpo)

    def do_GET(self):
        if self.path == "/salud":                            # para que Railway sepa que esta vivo
            return self.responder(200, "ok")
        if not self.autorizado():
            self.send_response(401)
            self.send_header("WWW-Authenticate", 'Basic realm="Dashboard Ovunque + Amola"')
            self.end_headers()
            return
        if self.path == "/actualizar":
            threading.Thread(target=actualizar, daemon=True).start()
            return self.responder(200, "Actualizando. Volve a la pagina principal en uno o dos minutos.")
        if not os.path.exists(os.path.join(CARPETA, "index.html")):
            return self.responder(503, "El dashboard se esta generando. Volve a cargar en un minuto.")
        super().do_GET()


if __name__ == "__main__":
    os.makedirs(CARPETA, exist_ok=True)
    threading.Thread(target=actualizar, daemon=True).start()     # primera version al arrancar
    threading.Thread(target=programador, daemon=True).start()    # y despues, todos los dias
    puerto = int(os.environ.get("PORT", "8000"))
    print(f"Servidor en el puerto {puerto} (actualiza todos los dias a las {HORA}:00)", flush=True)
    ThreadingHTTPServer(("0.0.0.0", puerto), Manejador).serve_forever()
