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

    def ai_config(self, response):
        config = self.repo / "test-runner.json"
        runner_code = f"print({response!r})"
        config.write_text(
            json.dumps(
                {
                    "provider": "command",
                    "command": [sys.executable, "-c", runner_code],
                }
            ),
            encoding="utf-8",
        )
        return config

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

    def test_pre_commit_gate_allows_clean_structured_review(self):
        (self.repo / "app.py").write_text("def answer():\n    return 42\n", encoding="utf-8")
        self.git("add", "app.py")
        config = self.ai_config('{"summary":"通过","findings":[]}')

        result = self.cli("--config", str(config), "--hook", "pre-commit")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("AI 审查结论: 通过", result.stderr)
        self.assertIn("AI 未发现", result.stderr)

    def test_pre_commit_gate_fails_closed_for_malformed_ai_output(self):
        (self.repo / "app.py").write_text("def answer():\n    return 42\n", encoding="utf-8")
        self.git("add", "app.py")
        config = self.ai_config("not-json")

        result = self.cli("--config", str(config), "--hook", "pre-commit")

        self.assertEqual(result.returncode, 2)
        self.assertIn("不是有效的纯 JSON", result.stderr)

    def test_pre_push_gate_reviews_exact_ref_range(self):
        old_head = self.git("rev-parse", "HEAD").stdout.strip()
        (self.repo / "app.py").write_text("def answer():\n    return 42\n", encoding="utf-8")
        self.git("add", "app.py")
        self.git("commit", "-q", "-m", "answer 42")
        new_head = self.git("rev-parse", "HEAD").stdout.strip()
        config = self.ai_config('{"summary":"push 通过","findings":[]}')
        update = f"refs/heads/main {new_head} refs/heads/main {old_head}\n"

        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                str(self.repo),
                "--config",
                str(config),
                "--hook",
                "pre-push",
                "--hook-remote",
                "origin",
            ],
            cwd=self.repo,
            input=update,
            check=False,
            text=True,
            capture_output=True,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("push 通过", result.stderr)

    def test_hook_install_chains_and_restores_existing_hook(self):
        hooks = self.repo / ".git" / "hooks"
        original = hooks / "pre-commit"
        original.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        original.chmod(0o755)

        installed = self.cli("--install-hooks")

        self.assertEqual(installed.returncode, 0, installed.stderr)
        self.assertIn(ai_review.HOOK_MARKER, original.read_text(encoding="utf-8"))
        backup = hooks / f"pre-commit{ai_review.HOOK_BACKUP_SUFFIX}"
        self.assertEqual(backup.read_text(encoding="utf-8"), "#!/bin/sh\nexit 0\n")
        pre_push = (hooks / "pre-push").read_text(encoding="utf-8")
        self.assertIn("mktemp", pre_push)
        self.assertIn("hook-remote", pre_push)

        installed_again = self.cli("--install-hooks")
        self.assertEqual(installed_again.returncode, 0, installed_again.stderr)
        self.assertEqual(backup.read_text(encoding="utf-8"), "#!/bin/sh\nexit 0\n")

        uninstalled = self.cli("--uninstall-hooks")

        self.assertEqual(uninstalled.returncode, 0, uninstalled.stderr)
        self.assertEqual(original.read_text(encoding="utf-8"), "#!/bin/sh\nexit 0\n")
        self.assertFalse(backup.exists())
        self.assertFalse((hooks / "pre-push").exists())

    def test_installed_pre_commit_hook_blocks_until_ai_succeeds(self):
        config = self.ai_config('{"summary":"hook 通过","findings":[]}')
        installed = self.cli(
            "--config",
            str(config),
            "--install-hooks",
            "--hooks",
            "pre-commit",
        )
        self.assertEqual(installed.returncode, 0, installed.stderr)
        (self.repo / "app.py").write_text("def answer():\n    return 42\n", encoding="utf-8")
        self.git("add", "app.py")

        committed = subprocess.run(
            ["git", "commit", "-m", "reviewed change"],
            cwd=self.repo,
            check=False,
            text=True,
            capture_output=True,
        )

        self.assertEqual(committed.returncode, 0, committed.stderr)
        self.assertIn("AI 审查结论: hook 通过", committed.stderr)

    def test_installed_pre_push_hook_reviews_new_remote_branch(self):
        config = self.ai_config('{"summary":"remote push 通过","findings":[]}')
        installed = self.cli(
            "--config",
            str(config),
            "--install-hooks",
            "--hooks",
            "pre-push",
        )
        self.assertEqual(installed.returncode, 0, installed.stderr)
        remote_temporary = tempfile.TemporaryDirectory()
        self.addCleanup(remote_temporary.cleanup)
        remote = Path(remote_temporary.name) / "remote.git"
        subprocess.run(["git", "init", "--bare", "-q", str(remote)], check=True)
        self.git("remote", "add", "origin", str(remote))

        pushed = subprocess.run(
            ["git", "push", "-u", "origin", "main"],
            cwd=self.repo,
            check=False,
            text=True,
            capture_output=True,
        )

        self.assertEqual(pushed.returncode, 0, pushed.stderr)
        self.assertIn("AI 审查结论: remote push 通过", pushed.stderr)

    def test_hook_install_refuses_custom_hooks_path(self):
        self.git("config", "core.hooksPath", ".shared-hooks")

        result = self.cli("--install-hooks")

        self.assertEqual(result.returncode, 2)
        self.assertIn("core.hooksPath", result.stderr)
        self.assertFalse((self.repo / ".shared-hooks").exists())


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
        self.assertIn("Authorization", online_installer)
        self.assertIn("GITHUB_TOKEN", online_installer)
        self.assertIn("^[A-Za-z0-9._-]+$", online_installer)
        self.assertIn("-ExecutionPolicy Bypass", installer_cmd)
        self.assertIn("@args", shim)

    def test_default_config_is_valid(self):
        config = json.loads((ROOT / "config" / "default.json").read_text(encoding="utf-8"))
        ai_review.validate_config(config)

    def test_structured_findings_are_normalized_and_sorted(self):
        result = ai_review.parse_gate_review(
            "```json\n"
            '{"summary":"2 risks","findings":['
            '{"id":"R2","severity":"p3","category":"performance","file":"a.py",'
            '"line":"7","title":"slow","evidence":"loop","recommendation":"cache"},'
            '{"id":"R1","severity":"P0","category":"security","file":"b.py",'
            '"line":null,"title":"injection","evidence":"raw SQL","recommendation":"bind"}'
            "]}\n```"
        )

        self.assertEqual([item.identifier for item in result.findings], ["R1", "R2"])
        self.assertEqual(result.findings[1].line, 7)

    def test_each_finding_and_final_gate_require_confirmation(self):
        findings = [
            ai_review.Finding("R1", "P1", "bug", "a.py", 3, "one", "why", "fix"),
            ai_review.Finding("R2", "P2", "security", "b.py", None, "two", "why", "fix"),
        ]
        answers = iter(["a", "m", "CONFIRM"])

        accepted = ai_review.confirm_findings(findings, lambda _prompt: next(answers))

        self.assertTrue(accepted)

    def test_fix_choice_blocks_gate_immediately(self):
        finding = ai_review.Finding("R1", "P1", "bug", "a.py", 3, "one", "why", "fix")

        accepted = ai_review.confirm_findings([finding], lambda _prompt: "f")

        self.assertFalse(accepted)


if __name__ == "__main__":
    unittest.main()
