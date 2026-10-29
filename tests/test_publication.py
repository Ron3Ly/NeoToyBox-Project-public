import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from privacy_guard import check_text, validate, PublicationError


class PublicationTests(unittest.TestCase):
    def sample(self, directory):
        p=Path(directory)
        (p/'README.md').write_text('Example only\n',encoding='utf-8')
        (p/'.public-manifest.json').write_text(json.dumps({'files':{'README.md':hashlib.sha256((p/'README.md').read_bytes()).hexdigest()}}),encoding='utf-8')
        return p

    def test_valid(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(validate(self.sample(d)),1)

    def test_extra_file(self):
        with tempfile.TemporaryDirectory() as d:
            p=self.sample(d);(p/'extra.txt').write_text('not reviewed')
            with self.assertRaises(PublicationError): validate(p)

    def test_changed_content(self):
        with tempfile.TemporaryDirectory() as d:
            p=self.sample(d);(p/'README.md').write_text('changed')
            with self.assertRaises(PublicationError): validate(p)

    def test_missing_file(self):
        with tempfile.TemporaryDirectory() as d:
            p=self.sample(d);(p/'README.md').unlink()
            with self.assertRaises(PublicationError): validate(p)

    def test_private_value(self):
        with self.assertRaises(PublicationError): check_text('file','hidden.internal.invalid',('hidden.internal.invalid',))

    def test_literal_credential(self):
        with self.assertRaises(PublicationError): check_text('file','password: '+'not-a-real-credential')

    def test_key_marker(self):
        marker='-----BEGIN '+'PRIVATE KEY-----'
        with self.assertRaises(PublicationError): check_text('file',marker)

    def test_placeholder(self):
        check_text('file','password: CHANGE_ME')


if __name__=='__main__': unittest.main()
