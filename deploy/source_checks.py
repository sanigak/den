"""DOC: security#verification"""
import ast
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent.parent


class AssetCheck(HTMLParser):
    def handle_starttag(self, tag, pairs):
        attrs = dict(pairs)
        assert not any(key.startswith('on') or key == 'style' for key in attrs), 'Inline browser behavior'
        if tag == 'script':
            assert attrs.get('src', '').startswith("{% static 'den/"), 'Nonlocal or inline script'
        if tag == 'style':
            raise AssertionError('Inline stylesheet')
        for key in ('src', 'href'):
            value = attrs.get(key, '')
            if tag in ('script', 'link', 'img'):
                assert not value.startswith(('http:', 'https:', '//', 'javascript:')), 'External browser asset'


def main():
    names = (ROOT/'deploy/package-files.txt').read_text().splitlines()
    findings = []
    secret = re.compile(r'sk-(?:ant|or)-[a-zA-Z0-9_-]{30,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----')
    for name in names + ['../start_infonet.bat']:
        path = ROOT/'infonet'/name
        if path.suffix not in ('.py', '.html', '.js', '.css', '.txt', '.bat'):
            continue
        content = path.read_text(encoding='utf-8-sig')
        for number, line in enumerate(content.splitlines(), 1):
            if secret.search(line):
                findings.append({'file': name, 'line': number, 'finding': 'REDACTED credential pattern'})
        if path.suffix == '.py':
            ast.parse(content, filename=name)
        if path.suffix == '.html':
            AssetCheck().feed(content)
        if path.suffix == '.js':
            assert not re.search(r'\b(?:eval|Function)\s*\(|innerHTML\s*=|document\.write\s*\(', content), name
    manifest = json.loads((ROOT/'deploy/vendor-manifest.json').read_text())
    for entry in manifest:
        assert hashlib.sha256((ROOT/entry['file']).read_bytes()).hexdigest() == entry['sha256'], entry['file']
    report = {'passed': not findings, 'packaged_files': len(names), 'credential_findings': findings,
              'scope': 'Explicit deployment allowlist and Den launcher; legacy archives and OpenClaw excluded.',
              'browser_checks': 'No inline scripts/styles/handlers, external assets, or JavaScript HTML sinks.',
              'vendor_hashes_checked': len(manifest)}
    (ROOT/'.hardening').mkdir(exist_ok=True)
    (ROOT/'.hardening/source-checks.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report))
    return bool(findings)


if __name__ == '__main__':
    raise SystemExit(main())
