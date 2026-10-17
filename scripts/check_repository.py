#!/usr/bin/env python3
"""Check local documentation links, Python syntax, SVGs and CMake source references."""
import ast
from pathlib import Path
import re
import sys
from urllib.parse import unquote, urlsplit
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]


def main():
    errors = []
    paths = [p for folder in ('tools', 'scripts', 'tests') for p in (ROOT / folder).rglob('*.py')]
    for path in paths:
        try:
            ast.parse(path.read_text(), filename=str(path.relative_to(ROOT)))
        except SyntaxError as error:
            errors.append(str(error))
    docs = list(ROOT.glob('*.md'))
    for folder in ('docs', 'firmware', 'tools', '.github'):
        docs += [p for p in (ROOT / folder).rglob('*.md') if 'build' not in p.parts]
    for path in docs:
        source = path.read_text()
        links = re.findall(r'!?\[[^\]]*\]\(([^)]+)\)', source)
        links += re.findall(r'(?:src|href)="([^"]+)"', source)
        for link in links:
            target = link.split(' "', 1)[0].strip('<>')
            parsed = urlsplit(target)
            if parsed.scheme or parsed.netloc or not parsed.path:
                continue
            destination = path.parent / unquote(parsed.path)
            if not destination.exists():
                errors.append(f'{path.relative_to(ROOT)}: missing link {target}')
    for path in (ROOT / 'docs/images').glob('*.svg'):
        try:
            ET.parse(path)
        except ET.ParseError as error:
            errors.append(f'{path.name}: {error}')
    for path in (ROOT / 'firmware').glob('*/main/CMakeLists.txt'):
        for name in re.findall(r'"([^\"]+\.(?:cpp|c|S))"', path.read_text()):
            if not (path.parent / name).is_file():
                errors.append(f'{path.relative_to(ROOT)}: missing source {name}')
    if errors:
        print('\n'.join(errors), file=sys.stderr)
        return 1
    print(f'Checked {len(paths)} Python files, {len(docs)} documents, SVGs and CMake sources.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
