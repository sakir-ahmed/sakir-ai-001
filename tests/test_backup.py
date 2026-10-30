"""Exercise backup failure handling with isolated files and fake external commands."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]

class BackupTests(unittest.TestCase):
    def run_backup(self, tar_status=0, age_status=0, hook=False):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for name in ['lib', 'scripts/backup.d', 'backups', 'bin']:
                (root / name).mkdir(parents=True, exist_ok=True)
            # Keep the real shell flow; replace only external services and logging.
            (root / 'lib/common.sh').write_text('''require_root() { :; }
info() { :; }; ok() { :; }; warn() { echo "WARN:$*"; }; error() { echo "ERROR:$*"; }
hc_ping() { :; }; notify_telegram() { echo ALERT; }
''')
            (root / 'recipient').write_text('test public recipient')
            commands = {
                'docker': '#!/bin/bash\necho fixture-database\n',
                'tar': '#!/bin/bash\nif [[ "$1" == "-czf" ]]; then echo files > "$2"; exit "${TEST_TAR_STATUS}"; fi\necho outer-archive\n',
                'age': '#!/bin/bash\nwhile [[ $# -gt 0 ]]; do if [[ "$1" == "-o" ]]; then shift; out="$1"; fi; shift; done\ncat > "$out"\nexit "${TEST_AGE_STATUS}"\n',
                'rclone': '#!/bin/bash\nexit 0\n',
                'flock': '#!/bin/bash\nexit 0\n',
            }
            for name, body in commands.items():
                f = root / 'bin' / name; f.write_text(body); f.chmod(0o755)
            if hook:
                (root / 'scripts/backup.d/fail.sh').write_text('exit 9\n')
            env = dict(os.environ, INSTALL_DIR=str(root),
                       RECIPIENT=str(root / 'recipient'), LOG_FILE=str(root / 'log'),
                       PATH=str(root / 'bin') + ':' + os.environ['PATH'],
                       TEST_TAR_STATUS=str(tar_status), TEST_AGE_STATUS=str(age_status))
            script = root / 'backup.sh'
            script.write_text((ROOT / 'scripts/backup.sh').read_text().replace('RECIPIENT=/root/backup-recipient.txt', 'RECIPIENT="$INSTALL_DIR/recipient"'))
            result = subprocess.run(['bash', str(script)], env=env, text=True, capture_output=True)
            archives = list((root / 'backups').glob('sakir-ai_*.tar.age'))
            return result.returncode, result.stdout + result.stderr, len(archives)

    def test_changed_live_file_is_warning(self):
        code, output, count = self.run_backup(tar_status=1)
        self.assertEqual(code, 0, output)
        self.assertEqual(count, 1)
        self.assertIn('WARN:', output)

    def test_real_archive_error_fails(self):
        code, output, count = self.run_backup(tar_status=2)
        self.assertNotEqual(code, 0)
        self.assertEqual(count, 0)
        self.assertIn('ALERT', output)

    def test_encryption_failure_never_publishes_backup(self):
        code, output, count = self.run_backup(age_status=1)
        self.assertNotEqual(code, 0)
        self.assertEqual(count, 0)
        self.assertIn('ALERT', output)

    def test_failed_product_dump_fails_whole_backup(self):
        code, output, count = self.run_backup(hook=True)
        self.assertNotEqual(code, 0)
        self.assertEqual(count, 0)

    def test_normal_backup(self):
        code, output, count = self.run_backup()
        self.assertEqual(code, 0, output)
        self.assertEqual(count, 1)

if __name__ == '__main__':
    unittest.main()
