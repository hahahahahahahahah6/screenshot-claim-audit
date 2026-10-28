"""Numbered requirements 1–27; generated phrase tests cover every constant entry."""
import contextlib
import io
import json
from pathlib import Path
import re
import tempfile
import unittest
from unittest.mock import patch

from screenshot_claim_audit import NEGATIVE, POSITIVE, audit, claims, evidence, main, normalize, pattern

ROOT = Path(__file__).resolve().parents[1]
GOOD = 'import pyautogui\npyautogui.screenshot()\n'


class AuditTests(unittest.TestCase):
    def project(self, doc='takes screenshots', source=None, name='app.py'):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        (root / 'README.md').write_text(doc)
        if source is not None:
            target = root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(source)
        return root

    def check(self, source, good=True, doc='takes screenshots'):
        result = audit(self.project(doc, source))
        self.assertEqual(result['verdict'], 'PASS' if good else 'FAIL')
        self.assertEqual(len(result['findings']), 0 if good else 1)
        if not good:
            self.assertEqual(result['findings'][0]['severity'], 'HIGH')
            self.assertEqual(result['findings'][0]['rule'], 'documented-screenshot-claim-false')
        return result

    def cli(self, *args):
        output = io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(io.StringIO()):
            code = main(list(map(str, args)))
        return code, output.getvalue()

    def test_01_plain(self): self.check(GOOD)
    def test_02_alias(self): self.check('import pyautogui as pg\npg.screenshot()', doc='takes a screenshot')
    def test_03_from(self): self.check('from pyautogui import screenshot as shot\nshot()', doc='take screenshots')
    def test_04_pil(self): self.check('from PIL import ImageGrab\nImageGrab.grab()', doc='captures the screen')
    def test_05_pil_from(self): self.check('from PIL.ImageGrab import grab\ngrab()', doc='captures a screenshot')
    def test_06_mss(self): self.check('import mss\nthing.shot()')
    def test_07_mss_alias(self): self.check('import mss as ms\nthing.grab()', doc='captures the screen')
    def test_08_pyscreenshot(self): self.check('import pyscreenshot\npyscreenshot.grab()', doc='takes a screenshot')
    def test_09_import(self): self.check('import pyautogui', False)
    def test_10_strings(self): self.check('value = "screenshot.png"', False)
    def test_11_image_io(self): self.check('from PIL import Image\nImage.open("a").save("b")', False)
    def test_12_video(self): self.check('import cv2\ncv2.VideoCapture(0).read()', False)
    def test_13_mss_absent(self): self.check('thing.shot()\nthing.grab()', False)
    def test_14_negative(self):
        result = audit(self.project('no screenshot support', GOOD))
        self.assertEqual(result['verdict'], 'FAIL')
        self.assertEqual([ (f['rule'], f['severity']) for f in result['findings']], [('documented-no-screenshot-claim-false', 'HIGH')])
    def test_15_no_claim(self): self.check(GOOD, doc='Useful automation.')
    def test_16_noun(self): self.check('import pyautogui', doc='the screenshot chapter explains delivery')
    def test_17_video_claim(self): self.check(GOOD, doc='records video')
    def test_18_clipboard(self): self.check(GOOD, doc='copy to clipboard')
    def test_19_no_source(self):
        self.check(None, False)
        self.check(None, doc='no screenshot support')
    def test_20_tests_only(self):
        root = self.project(source=GOOD, name='tests/helper.py')
        result = audit(root)
        self.assertEqual(result['verdict'], 'PASS')
        self.assertEqual(len(result['findings']), 1)
        self.assertEqual(result['findings'][0]['severity'], 'MEDIUM')
        self.assertEqual(self.cli(root)[0], 0)
        self.assertEqual(self.cli(root, '--fail-on', 'MEDIUM')[0], 2)
    def test_21_fences_inline(self):
        self.check(None, doc='```text\ntakes screenshots\n```')
        self.check(None, False, doc='`takes screenshots`')
    def test_22_negation(self):
        self.assertEqual(claims('does not take screenshots'), (False, True))
        self.check(None, doc="doesn't take screenshots")
    def test_23_self(self):
        text = (ROOT / 'README.md').read_text()
        self.assertIsNone(pattern(POSITIVE + NEGATIVE).search(normalize(text)))
        self.assertIsNone(re.search(r'\b(using|uses|with|via|over|supports|sends|send)\s+screenshot claim audit\b', normalize(text)))
        result = audit(ROOT)
        self.assertEqual(result['verdict'], 'PASS')
        self.assertEqual(result['findings'], [])
    def test_24_cli(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output), self.assertRaises(SystemExit) as caught:
            main(['--version'])
        self.assertEqual(caught.exception.code, 0)
        self.assertEqual(output.getvalue().strip(), '0.1.0')
        root = self.project(source=GOOD)
        code, output = self.cli(root, '--json')
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(output)['verdict'], 'PASS')
        self.assertIn('app.py:2', self.cli(root, '--verbose')[1])
        root = self.project('Neutral')
        (root / 'docs').mkdir()
        (root / 'docs' / 'guide.md').write_text('takes screenshots')
        self.assertEqual(self.cli(root)[0], 2)
        self.assertEqual(self.cli(root, '--ignore', 'docs/*')[0], 0)
        for args in [[], ['/nonexistent-root'], [root, '--bogus'], [root, '--fail-on', 'LOW']]:
            self.assertEqual(self.cli(*args)[0], 1)
    def test_25_env(self):
        root = ROOT / 'tests' / 'fixtures' / 'good'
        original = Path.read_text
        def guarded(path, *args, **kwargs):
            self.assertNotEqual(path.name, '.env')
            return original(path, *args, **kwargs)
        with patch.object(Path, 'read_text', guarded):
            self.assertEqual(audit(root)['verdict'], 'PASS')
    def test_26_packaging(self):
        for path in list((ROOT / 'screenshot_claim_audit').glob('*.py')) + list((ROOT / 'tests').glob('*.py')) + [ROOT / 'README.md', ROOT / 'pyproject.toml']:
            self.assertIsNone(re.search(r'(?<![\w-])' + 'py' + r'thon\b', path.read_text()))
        config = (ROOT / 'pyproject.toml').read_text()
        self.assertIn('setuptools>=77', config)
        self.assertIn('license = "MIT"', config)
        self.assertIn('recursive-include tests', (ROOT / 'MANIFEST.in').read_text())
    def test_27_phrase_counts(self):
        self.assertEqual(len(POSITIVE), 23)
        self.assertEqual(len(NEGATIVE), 11)

    def test_extra_provider_routes(self):
        for source in ['import PIL.ImageGrab\nPIL.ImageGrab.grab()', 'import PIL.ImageGrab as ig\nig.grab()', 'from PIL.ImageGrab import grab as g\ng()', 'from pyscreenshot import grab as g\ng()', 'import pyscreenshot as ps\nps.grab()', 'from mss import mss as factory\ns.shot()', 'from pyautogui.sub import screenshot as s\ns()']:
            with self.subTest(source=source): self.check(source)
    def test_extra_false_routes(self):
        for source in ['from elsewhere import grab\ngrab()', 'import pyautogui\npyautogui.click()', 'def screenshot():\n return "hello"\nscreenshot()', '@app.get("/")\ndef view():\n return "screenshot"', 'import subprocess\nsubprocess.run(["scrot"])', '"""pyautogui.screenshot()"""', 'pyautogui.screenshot()']:
            with self.subTest(source=source): self.check(source, False)
    def test_extra_scope(self):
        for name in ['examples/app.py', 'docs/app.py', 'fixtures/app.py']:
            self.assertEqual(audit(self.project(source=GOOD, name=name))['findings'][0]['severity'], 'HIGH')
        for name in ['test_app.py', 'app_test.py']:
            self.assertEqual(audit(self.project(source=GOOD, name=name))['findings'][0]['severity'], 'MEDIUM')
        root = self.project(source='import pyautogui')
        (root / 'linked.py').symlink_to(ROOT / 'tests' / 'fixtures' / 'good' / 'app.py')
        self.assertEqual(audit(root)['verdict'], 'FAIL')
    def test_extra_normalization(self):
        self.assertEqual(claims('TAKES\nSCREENSHOTS'), (True, False))
        self.assertEqual(claims('takes\n\nscreenshots'), (False, False))
        self.assertEqual(claims('screen-capture'), (True, False))
        self.assertEqual(claims('retakes screenshots'), (False, False))
    def test_extra_two_families(self):
        result = audit(self.project('takes screenshots. No screenshots.'))
        self.assertEqual(len(result['findings']), 1)
        result = audit(self.project('no screenshots', GOOD, 'test_capture.py'))
        self.assertEqual(result['findings'], [])


def phrase_test(phrase, negative):
    def test(self):
        self.assertEqual(claims(phrase), (not negative, negative))
        root = self.project(phrase, GOOD if negative else None)
        result = audit(root)
        self.assertEqual(result['verdict'], 'FAIL')
        self.assertEqual(len(result['findings']), 1)
        self.assertEqual(result['findings'][0]['severity'], 'HIGH')
        expected = 'documented-no-screenshot-claim-false' if negative else 'documented-screenshot-claim-false'
        self.assertEqual(result['findings'][0]['rule'], expected)
    return test


for family, phrases in [('positive', POSITIVE), ('negative', NEGATIVE)]:
    for index, phrase in enumerate(phrases):
        setattr(AuditTests, 'test_phrase_' + family + '_' + str(index), phrase_test(phrase, family == 'negative'))
