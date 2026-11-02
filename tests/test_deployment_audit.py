"""Verify drift detection and secret exclusion using disposable Git fixtures."""
import contextlib
import importlib.util
import io
from pathlib import Path
import subprocess
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('audit', Path(__file__).resolve().parents[1] / 'scripts/audit-deployment.py')
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)

class DeploymentAuditTests(unittest.TestCase):
    def check_fixture(self, change):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder); source = base / 'source'; live = base / 'live'
            for root in [source, live]:
                (root / 'scripts').mkdir(parents=True)
                (root / 'scripts/core.sh').write_text('#!/bin/sh\necho core\n')
                (root / 'secrets').mkdir()
                (root / 'secrets/private.env').write_text('SECRET_SENTINEL')
                (root / '.env').write_text('SECRET_SENTINEL')
            subprocess.run(['git','init','-q',str(source)],check=True)
            subprocess.run(['git','-C',str(source),'add','.'],check=True)
            subprocess.run(['git','-C',str(source),'-c','user.name=Fixture','-c','user.email=fixture@example.invalid','commit','-qm','fixture'],check=True)
            change(live, base)
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                code = audit.audit(source, live, 'HEAD')
            self.assertNotIn('SECRET_SENTINEL', output.getvalue())
            self.assertNotIn('private.env', output.getvalue())
            return code, output.getvalue()

    def test_identical_core_excludes_secrets(self):
        code, output = self.check_fixture(lambda *_: None)
        self.assertEqual(code, 0)
        self.assertIn('MATCH=1',output)

    def test_modified_core(self):
        code, output = self.check_fixture(lambda live,_: (live/'scripts/core.sh').write_text('changed'))
        self.assertEqual(code,1)
        self.assertIn('MODIFIED scripts/core.sh',output)

    def test_extra_core(self):
        code, output = self.check_fixture(lambda live,_: (live/'scripts/new.sh').write_text('new'))
        self.assertEqual(code,1)
        self.assertIn('EXTRA scripts/new.sh',output)

    def test_symlink_never_reads_target(self):
        def change(live, base):
            target = base/'private'; target.write_text('SECRET_SENTINEL')
            (live/'scripts/core.sh').unlink()
            (live/'scripts/core.sh').symlink_to(target)
        code, output = self.check_fixture(change)
        self.assertEqual(code,1)
        self.assertIn('SYMLINK scripts/core.sh',output)

if __name__ == '__main__':
    unittest.main()
