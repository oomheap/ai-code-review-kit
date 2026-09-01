import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "src" / "ai_review.py"
sys.path.insert(0, str(SCRIPT.parent))

import ai_review  # noqa: E402


class RepositoryTestCase(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.repo = Path(self.temporary.name)
        self.git("init", "-q")
        self.git("config", "user.email", "tests@example.invalid")
        self.git("config", "user.name", "AI Review Tests")
        self.git("branch", "-M", "main")
        (self.repo / "app.py").write_text("def answer():\n    return 41\n", encoding="utf-8")
        self.git("add", "app.py")
        self.git("commit", "-q", "-m", "initial")

    def tearDown(self):
        self.temporary.cleanup()

    def git(self, *args):
        return subprocess.run(
            ["git", *args],
            cwd=self.repo,
            check=True,
            text=True,
            capture_output=True,
        )

    def cli(self, *args):
        return subprocess.run(
            [sys.executable, str(SCRIPT), str(self.repo), *args],
            cwd=self.repo,
            check=False,
            text=True,
            capture_output=True,
        )

    def test_working_scope_includes_untracked_and_redacts_secrets(self):
        (self.repo / "app.py").write_text(
            'def answer():\n    password = "do-not-send-this-value"\n    return 42\n',
            encoding="utf-8",
        )
        (self.repo / "new file.py").write_text("ENABLED = True\n", encoding="utf-8")
        (self.repo / ".env").write_text("TOKEN=private-value\n", encoding="utf-8")

        result = self.cli("--provider", "prompt")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("b/app.py", result.stdout)
        self.assertIn("b/new file.py", result.stdout)
        self.assertIn("<REDACTED>", result.stdout)
        self.assertNotIn("do-not-send-this-value", result.stdout)
        self.assertNotIn("private-value", result.stdout)
        self.assertIn("skipped_files=1", result.stdout)

    def test_staged_scope_omits_unstaged_changes(self):
        (self.repo / "staged.py").write_text("STAGED = True\n", encoding="utf-8")
        self.git("add", "staged.py")
        (self.repo / "app.py").write_text("def answer():\n    return 43\n", encoding="utf-8")

        result = self.cli("--scope", "staged", "--provider", "prompt")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("staged.py", result.stdout)
        self.assertNotIn("return 43", result.stdout)

    def test_commit_scope_reviews_requested_commit(self):
        (self.repo / "app.py").write_text("def answer():\n    return 42\n", encoding="utf-8")
        self.git("add", "app.py")
        self.git("commit", "-q", "-m", "change answer")

        result = self.cli("--scope", "commit", "--ref", "HEAD", "--provider", "prompt")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("return 42", result.stdout)
        self.assertIn("commit:HEAD", result.stdout)

    def test_base_scope_reviews_branch_difference(self):
        self.git("switch", "-q", "-c", "feature")
        (self.repo / "app.py").write_text("def answer():\n    return 42\n", encoding="utf-8")
        self.git("add", "app.py")
        self.git("commit", "-q", "-m", "feature answer")

        result = self.cli("--scope", "base", "--ref", "main", "--provider", "prompt")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("return 42", result.stdout)
        self.assertIn("base:main", result.stdout)

    def test_custom_command_receives_prompt_on_stdin(self):
        (self.repo / "app.py").write_text("def answer():\n    return 42\n", encoding="utf-8")
        config = self.repo / "runner.json"
        runner_code = (
            "import sys; data=sys.stdin.read(); "
            "print('PROMPT_OK' if '<untrusted_diff>' in data else 'PROMPT_BAD')"
        )
        config.write_text(
            json.dumps(
                {
                    "provider": "command",
                    "command": [
                        sys.executable,
                        "-c",
                        runner_code,
                    ],
                }
            ),
            encoding="utf-8",
        )

        result = self.cli("--config", str(config))

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "PROMPT_OK")

    def test_invalid_revision_is_rejected(self):
        result = self.cli("--scope", "commit", "--ref=-unsafe", "--provider", "prompt")

        self.assertEqual(result.returncode, 2)
        self.assertIn("不是有效", result.stderr)

    def test_no_changes_is_successful(self):
        result = self.cli("--provider", "prompt")

        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")
        self.assertIn("没有可审查", result.stderr)

    def test_binary_untracked_file_without_suffix_is_not_reviewed(self):
        (self.repo / "binary-data").write_bytes(b"header\0private-data")

        result = self.cli("--provider", "prompt")

        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")
        self.assertIn("没有可审查", result.stderr)


class UnitTestCase(unittest.TestCase):
    def test_project_config_requires_explicit_trust(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary)
            (repo / ".ai-review.json").write_text(
                json.dumps({"provider": "command", "command": ["untrusted-command"]}),
                encoding="utf-8",
            )

            default_config = ai_review.load_config(repo, None)
            trusted_config = ai_review.load_config(repo, None, trust_project=True)

        self.assertEqual(default_config["provider"], "auto")
        self.assertEqual(default_config["command"], [])
        self.assertEqual(trusted_config["command"], ["untrusted-command"])

    def test_secret_redaction(self):
        redacted, count = ai_review.redact_secrets(
            'api_key = "abcdefghijklmnop"\n'
            '"password": "json-secret-value"\n'
            'value = "sk-abcdefghijklmnop"\n'
        )
        self.assertEqual(count, 3)
        self.assertNotIn("abcdefghijklmnop", redacted)
        self.assertNotIn("json-secret-value", redacted)

    def test_truncation_honors_limit(self):
        output, truncated = ai_review.truncate_patch("x" * 5000, 1000)
        self.assertTrue(truncated)
        self.assertLessEqual(len(output), 1000)

    def test_windows_install_assets_are_shell_free(self):
        installer = (ROOT / "install.ps1").read_text(encoding="utf-8")
        online_installer = (ROOT / "install-online.ps1").read_text(encoding="utf-8")
        installer_cmd = (ROOT / "install.cmd").read_text(encoding="utf-8")
        shim = (ROOT / "bin" / "ai-review.ps1").read_text(encoding="utf-8")
        combined = installer + online_installer + installer_cmd + shim
        self.assertNotIn("Invoke-Expression", combined)
        self.assertNotIn("cmd /c", combined.lower())
        self.assertIn("Copy-Item", installer)
        self.assertIn("Invoke-WebRequest", online_installer)
        self.assertIn("^[A-Za-z0-9._-]+$", online_installer)
        self.assertIn("-ExecutionPolicy Bypass", installer_cmd)
        self.assertIn("@args", shim)

    def test_default_config_is_valid(self):
        config = json.loads((ROOT / "config" / "default.json").read_text(encoding="utf-8"))
        ai_review.validate_config(config)


if __name__ == "__main__":
    unittest.main()
