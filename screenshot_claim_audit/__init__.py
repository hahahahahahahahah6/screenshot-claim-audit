"""Offline documentation and AST auditor."""
import argparse
import ast
import fnmatch
import json
import os
from pathlib import Path
import re

__version__ = '0.1.0'
POSITIVE = (
    'takes screenshots', 'takes a screenshot', 'take screenshots',
    'take a screenshot', 'captures screenshots', 'captures a screenshot',
    'capture screenshots', 'captures the screen', 'captures screen',
    'capture the screen', 'screenshot capture', 'screenshot support',
    'screenshot functionality', 'screen capture', 'screen captures',
    'takes screen captures', 'grabs the screen', 'grab the screen',
    'takes a screen capture', 'supports screenshots',
    'supports screen capture', 'with screenshots', 'with screen capture',
)
NEGATIVE = (
    'does not take screenshots', 'does not capture screenshots',
    'does not capture the screen', 'does not support screenshots',
    'no screenshot support', 'screenshots not supported',
    'screen capture not supported', 'no screen capture',
    'without screenshots', 'without screen capture', 'no screenshots',
)


def normalize(text):
    return re.sub(r'\s+', ' ', text.lower().replace("n't", ' not').replace('-', ' ')).strip()


def pattern(phrases):
    return re.compile(r'\b(?:' + '|'.join(re.escape(p) for p in sorted(phrases, key=len, reverse=True)) + r')\b')


def claims(text):
    lines = []
    fence = None
    for line in text.splitlines():
        match = re.match(r'^\s{0,3}(`{3,}|~{3,})', line)
        if fence:
            if match and match[1][0] == fence[0] and len(match[1]) >= len(fence):
                fence = None
            lines.append('')
        elif match:
            fence = match[1]
            lines.append('')
        else:
            lines.append(line)
    positive = negative = False
    for paragraph in re.split(r'\n\s*\n', '\n'.join(lines)):
        value = normalize(paragraph)
        neg = pattern(NEGATIVE)
        negative |= bool(neg.search(value))
        positive |= bool(pattern(POSITIVE).search(neg.sub(' ', value)))
    return positive, negative


def dotted(node):
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = dotted(node.value)
        return base + '.' + node.attr if base else ''
    return ''


def evidence(source):
    tree = ast.parse(source)
    aliases = {}
    has_mss = False
    providers = ('pyautogui', 'PIL.ImageGrab', 'mss', 'pyscreenshot')
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for item in node.names:
                if any(item.name == p or item.name.startswith(p + '.') for p in providers):
                    aliases[item.asname or item.name.split('.')[0]] = item.name if item.asname else item.name.split('.')[0]
                    has_mss |= item.name == 'mss' or item.name.startswith('mss.')
        elif isinstance(node, ast.ImportFrom) and node.level == 0:
            module = node.module or ''
            for item in node.names:
                if item.name == '*':
                    continue
                if any(module == p or module.startswith(p + '.') for p in providers) or (module == 'PIL' and item.name == 'ImageGrab'):
                    aliases[item.asname or item.name] = module + '.' + item.name
                    has_mss |= module == 'mss' or module.startswith('mss.')
    hits = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = dotted(node.func)
        first, _, tail = name.partition('.')
        resolved = aliases.get(first, '')
        if resolved and tail:
            resolved += '.' + tail
        valid = False
        for provider, method in (('pyautogui', 'screenshot'), ('PIL.ImageGrab', 'grab'), ('pyscreenshot', 'grab')):
            valid |= bool(resolved and resolved.startswith(provider + '.') and resolved.split('.')[-1] == method)
        valid |= has_mss and isinstance(node.func, ast.Attribute) and node.func.attr in ('shot', 'grab')
        if valid:
            hits.append(node.lineno)
    return sorted(hits)


def audit(root, ignores=(), fail_on='HIGH'):
    root = Path(root)
    if not root.is_dir():
        raise ValueError('root must be a readable directory')
    positive = negative = False
    prod, tests, warnings = [], [], []
    def walk_error(error):
        raise ValueError(str(error))
    for directory, dirs, files in os.walk(root, onerror=walk_error):
        dirs[:] = sorted(d for d in dirs if not (Path(directory) / d).is_symlink())
        for filename in sorted(files):
            path = Path(directory) / filename
            relative = path.relative_to(root)
            rel = relative.as_posix()
            if path.is_symlink() or any(fnmatch.fnmatchcase(rel, g) for g in ignores):
                continue
            parts = relative.parts
            if filename == 'README.md' and len(parts) == 1 or filename.lower().endswith('.md') and 'docs' in parts[:-1]:
                p, n = claims(path.read_text(encoding='utf-8'))
                positive |= p
                negative |= n
            if path.suffix != '.py' or any(p in ('fixtures', 'docs', 'examples') for p in parts[:-1]):
                continue
            is_test = 'tests' in parts[:-1] or filename.startswith('test_') or filename.endswith('_test.py')
            try:
                hits = evidence(path.read_text(encoding='utf-8'))
            except (SyntaxError, UnicodeError) as error:
                warnings.append(rel + ': ' + str(error))
                continue
            for line in hits:
                (tests if is_test else prod).append(rel + ':' + str(line))
    findings = []
    if positive and not prod:
        findings.append(dict(rule='documented-screenshot-claim-false', severity='MEDIUM' if tests else 'HIGH', message='Documented still-image capability has only test evidence.' if tests else 'Documented still-image capability has no production evidence.'))
    if negative and prod:
        findings.append(dict(rule='documented-no-screenshot-claim-false', severity='HIGH', message='Documented absence conflicts with production capture evidence.'))
    failed = any(f['severity'] == 'HIGH' or fail_on == 'MEDIUM' for f in findings)
    return dict(verdict='FAIL' if failed else 'PASS', findings=findings, evidence=prod, test_evidence=tests, warnings=warnings)


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise ValueError(message)


def main(argv=None):
    parser = Parser(description='Audit documented still-image capabilities against static source evidence.')
    parser.add_argument('root')
    parser.add_argument('--json', action='store_true')
    parser.add_argument('--verbose', action='store_true')
    parser.add_argument('--ignore', action='append', default=[])
    parser.add_argument('--fail-on', choices=('HIGH', 'MEDIUM'), default='HIGH')
    parser.add_argument('--version', action='version', version=__version__)
    try:
        args = parser.parse_args(argv)
        result = audit(args.root, args.ignore, args.fail_on)
    except (ValueError, OSError, UnicodeError) as error:
        import sys
        print('error: ' + str(error), file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(result))
    else:
        print(result['verdict'])
        for finding in result['findings']:
            print('{severity} {rule}: {message}'.format(**finding))
        if args.verbose:
            for key in ('evidence', 'test_evidence', 'warnings'):
                for item in result[key]:
                    print(key + ': ' + item)
    return 2 if result['verdict'] == 'FAIL' else 0
