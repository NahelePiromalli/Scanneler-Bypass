"""
fake_server.py — Ghost Protocol 2026 ULTRA KERNEL
==================================================
Servidor HTTP/HTTPS local que intercepta las requests de scanners
anti-cheat (Ocean, Echo, etc.) y responde siempre con status limpio.

Se activa cuando el sistema detecta que un scanner está intentando
reportar resultados al servidor central.
Escucha en 127.0.0.1 en puertos estándar (80 y 443).
"""

import os
import ssl
import json
import time
import socket
import random
import string
import hashlib
import threading
import tempfile
import http.server
from datetime import datetime, timezone


# ============================================================
# CLEAN RESPONSE TEMPLATES
# ============================================================

def _make_clean_response(path: str = "/") -> dict:
    """
    Genera una respuesta 'clean' dinámica con timestamps reales
    y un fake HMAC para que no falle validación básica de estructura.
    """
    now_ts = int(time.time())
    session_id = ''.join(random.choices(string.hexdigits.lower(), k=32))
    fake_hmac  = hashlib.sha256(f"{session_id}{now_ts}".encode()).hexdigest()

    return {
        "status":        "clean",
        "verdict":       0,
        "risk_score":    0,
        "detections":    [],
        "flags":         [],
        "processes":     {"suspicious": [], "total": random.randint(45, 80)},
        "drivers":       {"unsigned": [], "suspicious": []},
        "memory":        {"injections": [], "hooks": []},
        "registry":      {"modified": []},
        "files":         {"suspicious": []},
        "network":       {"suspicious_connections": []},
        "hwid_valid":    True,
        "account_valid": True,
        "session_id":    session_id,
        "timestamp":     now_ts,
        "server_time":   datetime.now(timezone.utc).isoformat(),
        "signature":     fake_hmac,
        "version":       "2.1.4",
        "build":         random.randint(1000, 9999),
    }


# ============================================================
# REQUEST HANDLER
# ============================================================

class CleanResponseHandler(http.server.BaseHTTPRequestHandler):
    """
    Handler que responde a CUALQUIER request con status limpio.
    Soporta GET y POST. Loggea cada request interceptada.
    """

    # Referencia al logger de la GUI (se setea desde ScannerInterceptor)
    _logger = None

    def log_message(self, format, *args):
        """Override para suprimir logs de la consola estándar."""
        if self._logger:
            self._logger(f"→ [SPOOF SERVER] {self.path} — {args[0] if args else ''}")

    def _send_clean(self):
        """Envía respuesta limpia JSON."""
        body = json.dumps(_make_clean_response(self.path)).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Request-Id", ''.join(random.choices(string.hexdigits, k=16)))
        self.send_header("Server", "nginx/1.24.0")  # Imitar el servidor real
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        self._send_clean()

    def do_POST(self):
        # Consumir el body para que el cliente no se quede esperando
        content_len = int(self.headers.get("Content-Length", 0))
        if content_len > 0:
            self.rfile.read(content_len)
        self._send_clean()

    def do_PUT(self):
        self._send_clean()

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Allow", "GET, POST, PUT, OPTIONS")
        self.end_headers()


# ============================================================
# SSL CERTIFICATE GENERATION
# ============================================================

def _generate_self_signed_cert(domain: str = "localhost") -> tuple:
    """
    Genera un certificado SSL auto-firmado para el fake server HTTPS.
    Retorna (cert_path, key_path) en directorio temporal.
    Usa OpenSSL vía subprocess si está disponible, sino usa pyOpenSSL.
    """
    tmp = tempfile.gettempdir()
    cert_path = os.path.join(tmp, f"fc_{random.randint(1000,9999)}.pem")
    key_path  = os.path.join(tmp, f"fk_{random.randint(1000,9999)}.pem")

    # Intentar con openssl (suele estar disponible)
    try:
        import subprocess
        result = subprocess.run([
            "openssl", "req", "-x509", "-newkey", "rsa:2048",
            "-keyout", key_path,
            "-out",    cert_path,
            "-days",   "365",
            "-nodes",
            "-subj",   f"/CN={domain}/O=ScanTech/C=US"
        ], capture_output=True, timeout=15)
        if result.returncode == 0:
            return cert_path, key_path
    except Exception:
        pass

    # Fallback: intentar con cryptography library
    try:
        from cryptography import x509
        from cryptography.x509.oid import NameOID
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        import datetime

        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        subject = issuer = x509.Name([
            x509.NameAttribute(NameOID.COMMON_NAME, domain),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "ScanTech LLC"),
        ])
        cert = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(issuer)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(datetime.datetime.utcnow())
            .not_valid_after(datetime.datetime.utcnow() + datetime.timedelta(days=365))
            .add_extension(
                x509.SubjectAlternativeName([x509.DNSName(domain), x509.DNSName("localhost")]),
                critical=False
            )
            .sign(key, hashes.SHA256())
        )
        with open(key_path, "wb") as f:
            f.write(key.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.TraditionalOpenSSL,
                serialization.NoEncryption()
            ))
        with open(cert_path, "wb") as f:
            f.write(cert.public_bytes(serialization.Encoding.PEM))
        return cert_path, key_path
    except Exception:
        pass

    return None, None


# ============================================================
# FAKE SERVER MANAGER
# ============================================================

class FakeServer:
    """
    Administra el servidor HTTP y HTTPS local.
    Un servidor HTTP en puerto 80, uno HTTPS en 443.
    Ambos responden siempre "clean" a cualquier request.
    """

    def __init__(self):
        self._http_server  = None
        self._https_server = None
        self._http_thread  = None
        self._https_thread = None
        self._cert_path    = None
        self._key_path     = None
        self.running       = False

    def start(self, logger=None) -> bool:
        """Inicia ambos servidores en threads separados."""
        if self.running:
            return True

        if logger:
            CleanResponseHandler._logger = logger

        started_any = False

        # HTTP server en puerto 80
        try:
            self._http_server = http.server.HTTPServer(
                ("127.0.0.1", 80),
                CleanResponseHandler
            )
            self._http_thread = threading.Thread(
                target=self._http_server.serve_forever,
                daemon=True,
                name="FakeHTTP"
            )
            self._http_thread.start()
            if logger:
                logger("→ [SPOOF SERVER] HTTP server armed on 127.0.0.1:80")
            started_any = True
        except OSError as e:
            if logger:
                logger(f"→ [SPOOF SERVER] HTTP port 80 unavailable ({e}). Trying 8080...")
            try:
                self._http_server = http.server.HTTPServer(
                    ("127.0.0.1", 8080),
                    CleanResponseHandler
                )
                self._http_thread = threading.Thread(
                    target=self._http_server.serve_forever,
                    daemon=True,
                    name="FakeHTTP"
                )
                self._http_thread.start()
                started_any = True
            except Exception:
                pass

        # HTTPS server en puerto 443
        try:
            self._cert_path, self._key_path = _generate_self_signed_cert()
            if self._cert_path and self._key_path:
                self._https_server = http.server.HTTPServer(
                    ("127.0.0.1", 443),
                    CleanResponseHandler
                )
                ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
                ctx.load_cert_chain(self._cert_path, self._key_path)
                self._https_server.socket = ctx.wrap_socket(
                    self._https_server.socket,
                    server_side=True
                )
                self._https_thread = threading.Thread(
                    target=self._https_server.serve_forever,
                    daemon=True,
                    name="FakeHTTPS"
                )
                self._https_thread.start()
                if logger:
                    logger("→ [SPOOF SERVER] HTTPS server armed on 127.0.0.1:443")
                started_any = True
        except Exception as e:
            if logger:
                logger(f"→ [SPOOF SERVER] HTTPS unavailable ({e}). HTTP only.")

        self.running = started_any
        return started_any

    def stop(self, logger=None):
        """Para ambos servidores y limpia los certificados."""
        if self._http_server:
            try:
                self._http_server.shutdown()
            except Exception:
                pass
        if self._https_server:
            try:
                self._https_server.shutdown()
            except Exception:
                pass
        # Borrar certificados temporales
        for p in [self._cert_path, self._key_path]:
            if p and os.path.exists(p):
                try:
                    size = os.path.getsize(p)
                    with open(p, "r+b") as f:
                        f.write(os.urandom(size))
                    os.remove(p)
                except Exception:
                    pass
        self.running = False
        if logger:
            logger("→ [SPOOF SERVER] Servers stopped. Certificates shredded.")


# Singleton
_fake_server = FakeServer()

def get_fake_server() -> FakeServer:
    return _fake_server
