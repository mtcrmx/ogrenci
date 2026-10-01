"""Convert school PPTX uploads once; TVs only receive protected slide images."""
import os
import shutil
import subprocess
import tempfile
import threading
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
from pathlib import Path

_pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix='school-pptx')
_lock = threading.Lock()
_jobs = OrderedDict()
FAILED = 'Sunum hazırlanamadı. Dosyayı kontrol edip yeniden hazırlayın veya PDF yükleyin.'


def office_command():
    configured = os.environ.get('YAYIN_SOFFICE')
    if configured:
        return configured if Path(configured).is_file() else shutil.which(configured)
    return (shutil.which('libreoffice') or shutil.which('soffice') or
            next((str(p) for p in (Path('C:/Program Files/LibreOffice/program/soffice.exe'),
                                  Path('C:/Program Files (x86)/LibreOffice/program/soffice.exe')) if p.is_file()), None))


@lru_cache(maxsize=128)
def _pages(path, modified):
    from pypdf import PdfReader
    reader = PdfReader(path)
    count = len(reader.pages)
    if reader.is_encrypted or not 1 <= count <= 100:
        raise ValueError('Invalid converted presentation')
    return count


def _convert(source, target, command, key):
    try:
        # Isolated profile avoids attaching to another Office instance. Macro execution
        # and link updates are disabled for uploaded documents, including unattended use.
        with tempfile.TemporaryDirectory(prefix='pptx-', dir=target.parent) as temporary:
            root = Path(temporary)
            profile = root / 'profile'
            (profile / 'user').mkdir(parents=True)
            (profile / 'user/registrymodifications.xcu').write_text('''<?xml version="1.0"?>
<oor:items xmlns:oor="http://openoffice.org/2001/registry">
<item oor:path="/org.openoffice.Office.Common/Security/Scripting"><prop oor:name="MacroSecurityLevel" oor:op="fuse"><value>3</value></prop></item>
<item oor:path="/org.openoffice.Office.Common/Load"><prop oor:name="UpdateLinks" oor:op="fuse"><value>false</value></prop></item>
</oor:items>''', encoding='utf-8')
            result = subprocess.run([command, '-env:UserInstallation=' + profile.as_uri(),
                '--headless', '--nologo', '--nodefault', '--norestore', '--convert-to',
                'pdf:impress_pdf_Export', '--outdir', str(root), str(source)],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=90,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
            converted = root / (source.stem + '.pdf')
            if result.returncode or not converted.is_file() or converted.stat().st_size > 100 * 1024 * 1024:
                raise ValueError('Conversion failed')
            _pages(str(converted), converted.stat().st_mtime_ns)
            os.replace(converted, target)
        # Regenerable PDFs are bounded separately from original uploads and JPEGs.
        entries = sorted(target.parent.glob('*.pdf'), key=lambda p: p.stat().st_mtime)
        total = sum(p.stat().st_size for p in entries)
        for entry in entries:
            if total <= 256 * 1024 * 1024:
                break
            if entry != target:
                total -= entry.stat().st_size
                entry.unlink(missing_ok=True)
        state = ('ready', '')
    except Exception:
        state = ('failed', FAILED)
    with _lock:
        _jobs[key] = state


def prepared_presentation(source, retry=False):
    """Nonblocking status lookup. Never expose cache paths to the public payload."""
    source = Path(source).resolve()
    if not source.is_file():
        return dict(status='failed', message='Sunum dosyası bulunamadı.')
    cache = source.parent / 'sunum-onizleme'
    cache.mkdir(exist_ok=True)
    target = cache / (source.name + '.pdf')
    key = str(source)
    if target.is_file():
        try:
            return dict(status='ready', message='Tüm ekranlar için hazır', path=target,
                        pages=_pages(str(target), target.stat().st_mtime_ns))
        except Exception:
            target.unlink(missing_ok=True)
    command = office_command()
    if not command:
        return dict(status='failed', message='PowerPoint hazırlama hizmeti etkin değil. Okul yöneticisine bildirin; bu sırada PDF yükleyebilirsiniz.')
    with _lock:
        state = _jobs.get(key)
        if state and state[0] == 'failed' and not retry:
            return dict(status=state[0], message=state[1])
        if not state or state[0] == 'ready' or (retry and state[0] != 'preparing'):
            if sum(s[0] == 'preparing' for s in _jobs.values()) >= 32:
                return dict(status='preparing', message='Hazırlama sırası bekleniyor')
            _jobs[key] = ('preparing', 'Slaytlar hazırlanıyor; sayfayı biraz sonra yenileyin.')
            while len(_jobs) > 128:
                old = next(k for k, s in _jobs.items() if s[0] != 'preparing')
                del _jobs[old]
            _pool.submit(_convert, source, target, command, key)
        return dict(status='preparing', message='Slaytlar hazırlanıyor; sayfayı biraz sonra yenileyin.')
