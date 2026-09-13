import ssl,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tls_config import wechat_context

def test_ca_bundle_loaded_and_verification_required():
 ctx=wechat_context()
 assert ctx.check_hostname
 assert ctx.verify_mode==ssl.CERT_REQUIRED
 assert ctx.cert_store_stats()['x509_ca']>0
