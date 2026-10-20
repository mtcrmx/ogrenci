import os
import tempfile
from pathlib import Path

# Test modülleri database'i içe aktarmadan önce çalışır; aksi halde testler gerçek okul veritabanına yazar.
_sandbox = tempfile.TemporaryDirectory(prefix='ogrenci-takip-test-')
os.environ.setdefault('OGR_TAKIP_DB_PATH', str(Path(_sandbox.name) / 'test.db'))
