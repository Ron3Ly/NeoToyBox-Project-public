"""Fail closed on extra files, changed approved hashes, and known sensitive patterns."""
from pathlib import Path
import argparse
import hashlib
import json
import re


class PublicationError(ValueError):
    pass


def check_text(name, text, denied=()):
    patterns = [
        r'-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----',
        r'AGE-SECRET-KEY-[A-Z0-9]+',
        r'\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{30,})\b',
        r'\bAKIA[A-Z0-9]{16}\b',
        r'(?i)C:\\Users\\[^\s\\]+\\',
        r'(?m)^sops:\s*$',
    ]
    if any(re.search(pattern,text) for pattern in patterns):
        raise PublicationError(f'sensitive pattern in {name}; content omitted')
    for line in text.splitlines():
        match=re.match(r'\s*(?:secret_[\w]+|password|api_token|api_key|smtp_password)\s*[:=]\s*(.*?)\s*$',line,re.I)
        if not match: continue
        value=match[1].strip('"\' ')
        if value and not any(marker in value for marker in ('CHANGE_ME','{{','null','None','example.invalid')):
            raise PublicationError(f'literal credential in {name}; content omitted')
    for value in denied:
        if value and value.lower() in text.lower():
            raise PublicationError(f'private deployment value in {name}; content omitted')


def validate(root, denied=()):
    root=Path(root)
    manifest=json.loads((root/'.public-manifest.json').read_text(encoding='utf-8'))
    expected=manifest['files']
    found={}
    for path in root.rglob('*'):
        rel=path.relative_to(root).as_posix()
        if rel=='.git' or rel.startswith('.git/') or '__pycache__' in path.parts:
            continue
        if path.is_symlink(): raise PublicationError(f'symlink rejected: {rel}')
        if not path.is_file() or rel=='.public-manifest.json': continue
        if rel not in expected: raise PublicationError(f'file outside approved allowlist: {rel}')
        if any(part in ('private','observed','.venv','exports') for part in path.relative_to(root).parts):
            raise PublicationError(f'private/generated directory: {rel}')
        if path.suffix.lower() in ('.pem','.key','.p12','.pfx','.age','.zip','.gz','.sql','.dump','.sqlite') or 'secrets.sops.' in path.name:
            raise PublicationError(f'secret or data file type: {rel}')
        content=path.read_bytes()
        digest=hashlib.sha256(content).hexdigest()
        if digest!=expected[rel]: raise PublicationError(f'unreviewed content hash: {rel}')
        text=content.decode('utf-8-sig')
        check_text(rel,text,denied)
        found[rel]=digest
    if set(found)!=set(expected): raise PublicationError('missing files from approved allowlist')
    return len(found)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('root',nargs='?',default='.')
    parser.add_argument('--deny-config')
    args=parser.parse_args()
    denied=json.loads(Path(args.deny_config).read_text(encoding='utf-8'))['values'] if args.deny_config else ()
    print(f'Publication allowlist/privacy/hash checks passed: {validate(args.root,denied)} files')


if __name__=='__main__': main()
