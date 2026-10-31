import io
import unittest
from contextlib import redirect_stderr, redirect_stdout
from types import SimpleNamespace
from unittest.mock import patch

from haunted_terminal import cli
from haunted_terminal.core import (
    _make_prompt,
    generate_commentary,
    is_install_command,
    run_command,
)


class InstallDetectionTests(unittest.TestCase):
    def test_detects_package_install_commands(self):
        commands = (
            ["npm", "install"],
            ["pnpm", "add", "react"],
            ["python3", "-m", "pip", "install", "requests"],
            ["uv", "pip", "install", "ruff"],
            ["cargo", "add", "serde"],
            ["sudo", "apt", "install", "curl"],
            ["dotnet", "add", "package", "Newtonsoft.Json"],
            ["pacman", "-S", "git"],
        )
        for command in commands:
            with self.subTest(command=command):
                self.assertTrue(is_install_command(command))

    def test_ignores_non_install_commands(self):
        commands = (
            [],
            ["npm", "test"],
            ["python3", "-m", "pip", "list"],
            ["git", "status"],
            ["echo", "npm install"],
        )
        for command in commands:
            with self.subTest(command=command):
                self.assertFalse(is_install_command(command))


class CommentaryTests(unittest.TestCase):
    def test_prompt_redacts_common_secrets(self):
        prompt = _make_prompt(
            ["npm", "install", "--token", "do-not-send", "api_key=also-secret"]
        )
        self.assertNotIn("do-not-send", prompt)
        self.assertNotIn("also-secret", prompt)
        self.assertIn("[REDACTED]", prompt)

    @patch("haunted_terminal.core.urllib.request.urlopen")
    def test_uses_local_model_response(self, urlopen):
        response = unittest.mock.MagicMock()
        response.__enter__.return_value.read.return_value = b'{"response":"A ghost stirs."}'
        urlopen.return_value = response

        self.assertEqual(generate_commentary(["npm", "install"]), "A ghost stirs.")
        request = urlopen.call_args.args[0]
        self.assertEqual(request.full_url, "http://127.0.0.1:11434/api/generate")
        self.assertEqual(urlopen.call_args.kwargs["timeout"], 120)

    @patch("haunted_terminal.core.urllib.request.urlopen", side_effect=OSError("offline"))
    def test_uses_fallback_when_local_model_is_unavailable(self, _urlopen):
        errors = io.StringIO()
        with redirect_stderr(errors):
            commentary = generate_commentary(["npm", "install"])

        self.assertTrue(commentary)
        self.assertIn("offline whisper", errors.getvalue())

    @patch("haunted_terminal.core.generate_commentary", return_value="The ghost stirs.")
    @patch("haunted_terminal.core.subprocess.run")
    def test_prints_comment_before_running_install(self, run, _commentary):
        output = io.StringIO()
        captured_before_run = []
        run.side_effect = lambda *_args, **_kwargs: (
            captured_before_run.append(output.getvalue()),
            SimpleNamespace(returncode=0),
        )[1]

        with redirect_stdout(output):
            result = run_command(["python3", "-m", "pip", "install", "requests"])

        self.assertEqual(result, 0)
        self.assertIn("[THE GHOST AWAKENS]", captured_before_run[0])
        self.assertIn("The ghost stirs.", captured_before_run[0])
        run.assert_called_once_with(
            ["python3", "-m", "pip", "install", "requests"],
            check=False,
        )

    @patch("haunted_terminal.core.subprocess.run")
    def test_does_not_generate_commentary_for_other_commands(self, run):
        run.return_value.returncode = 0
        with patch("haunted_terminal.core.generate_commentary") as commentary:
            output = io.StringIO()
            with redirect_stdout(output):
                result = run_command(["git", "status"])

        self.assertEqual(result, 0)
        self.assertEqual(output.getvalue(), "")
        commentary.assert_not_called()


class CliTests(unittest.TestCase):
    @patch("haunted_terminal.cli.run_command", return_value=7)
    @patch("sys.argv", ["haunted", "run", "--", "echo", "hello"])
    def test_passes_command_to_runner_and_returns_status(self, run):
        self.assertEqual(cli.main(), 7)
        run.assert_called_once_with(["echo", "hello"])

    @patch("sys.argv", ["haunted", "run"])
    def test_requires_a_command_after_run(self):
        errors = io.StringIO()
        with redirect_stderr(errors):
            result = cli.main()

        self.assertEqual(result, 2)
        self.assertIn("provide a command", errors.getvalue())


if __name__ == "__main__":
    unittest.main()
