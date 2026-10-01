import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from pypdf import PdfWriter
import broadcast_presentations as slides


class PresentationPreparation(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.source = Path(self.temp.name) / 'Türkçe sunum.pptx'
        self.source.write_bytes(b'original PPTX')
        self.target = self.source.parent / 'sunum-onizleme' / (self.source.name + '.pdf')
        self.target.parent.mkdir()

    def pdf(self, target):
        writer = PdfWriter()
        writer.add_blank_page(width=960, height=540)
        writer.add_blank_page(width=960, height=540)
        writer.write(target)

    def test_conversion_uses_isolated_profile_and_persists_reusable_pdf(self):
        def convert(args, **options):
            self.assertEqual(args[-1], str(self.source))
            self.assertIn('pdf:impress_pdf_Export', args)
            self.assertEqual(options['timeout'], 90)
            self.assertNotIn('shell', options)
            profile = next(a for a in args if a.startswith('-env:UserInstallation='))
            self.assertIn('file:///', profile)
            out = Path(args[args.index('--outdir') + 1])
            self.pdf(out / (self.source.stem + '.pdf'))
            return subprocess.CompletedProcess(args, 0)
        with patch.object(slides.subprocess, 'run', side_effect=convert):
            slides._convert(self.source, self.target, 'soffice', str(self.source))
        with patch.object(slides, 'office_command', return_value=None):
            state = slides.prepared_presentation(self.source)
        self.assertEqual((state['status'], state['pages']), ('ready', 2))
        self.assertEqual(self.source.read_bytes(), b'original PPTX')
        self.assertFalse(list(self.target.parent.glob('pptx-*')))

    def test_timeout_is_visible_and_does_not_queue_repeated_retries(self):
        with patch.object(slides.subprocess, 'run', side_effect=subprocess.TimeoutExpired('soffice', 90)):
            slides._convert(self.source, self.target, 'soffice', str(self.source))
        with patch.object(slides, 'office_command', return_value='soffice'), patch.object(slides._pool, 'submit') as queue:
            for _ in range(3):
                self.assertEqual(slides.prepared_presentation(self.source)['status'], 'failed')
            queue.assert_not_called()
            self.assertEqual(slides.prepared_presentation(self.source, retry=True)['status'], 'preparing')
            queue.assert_called_once()
        with slides._lock:
            slides._jobs.pop(str(self.source), None)

    def test_missing_converter_and_corrupt_cache_report_failure(self):
        self.target.write_bytes(b'broken PDF')
        with patch.object(slides, 'office_command', return_value=None):
            state = slides.prepared_presentation(self.source)
        self.assertEqual(state['status'], 'failed')
        self.assertIn('hizmeti etkin değil', state['message'])
        self.assertFalse(self.target.exists())
