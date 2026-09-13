"""Verified TLS using packaged public CAs and the OS-managed CA bundle."""
import ssl
from pathlib import Path
from functools import lru_cache
import certifi
@lru_cache(maxsize=1)
def wechat_context():
 context=ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
 context.load_verify_locations(cafile=certifi.where())
 system=Path('/etc/ssl/certs/ca-certificates.crt')
 if system.is_file():context.load_verify_locations(cafile=str(system))
 assert context.check_hostname and context.verify_mode==ssl.CERT_REQUIRED
 return context
