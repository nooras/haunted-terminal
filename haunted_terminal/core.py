import json
import os
import random
import re
import shlex
import subprocess
import sys
import urllib.request


OLLAMA_URL = "http://127.0.0.1:11434/api/generate"
DEFAULT_MODEL = "gemma3:1b"
MODEL_TIMEOUT_SECONDS = 120

_INSTALL_ACTIONS = {
    "npm": {"install", "i", "add"},
    "pnpm": {"install", "i", "add"},
    "yarn": {"install", "add"},
    "bun": {"install", "i", "add"},
    "pip": {"install"},
    "pip3": {"install"},
    "pipx": {"install"},
    "poetry": {"add", "install"},
    "pipenv": {"install"},
    "conda": {"install"},
    "mamba": {"install"},
    "cargo": {"install", "add"},
    "go": {"get", "install"},
    "gem": {"install"},
    "bundle": {"install", "add"},
    "composer": {"install", "require"},
    "apt": {"install"},
    "apt-get": {"install"},
    "brew": {"install"},
    "dnf": {"install"},
    "yum": {"install"},
    "apk": {"add"},
    "choco": {"install"},
    "winget": {"install"},
    "scoop": {"install"},
}

_FALLBACKS = (
    "Another dependency? You invite strangers into this machine and wonder why it feels haunted.",
    "A new package crosses the threshold. I hope you remember who invited it.",
    "More code from the outside world. The machine grows quieter... and less alone.",
)


def _basename(token: str) -> str:
    return token.replace("\\", "/").rsplit("/", 1)[-1].lower()


def _is_python_executable(executable: str) -> bool:
    executable = executable.removesuffix(".exe")
    return bool(re.fullmatch(r"python(?:\d+(?:\.\d+)*)?", executable))


def _unwrap_command(command: list[str]) -> list[str]:
    parts = command[:]
    while parts:
        executable = _basename(parts[0])
        if executable in {"command"}:
            parts.pop(0)
            if parts and parts[0] == "--":
                parts.pop(0)
            continue
        if executable in {"sudo", "doas"}:
            parts.pop(0)
            while parts and parts[0].startswith("-"):
                option = parts.pop(0)
                if option in {"-u", "-g", "-h", "-p", "-C", "-T"} and parts:
                    parts.pop(0)
                if option == "--":
                    break
            continue
        if executable == "env":
            parts.pop(0)
            while parts:
                if parts[0] == "--":
                    parts.pop(0)
                    break
                if re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", parts[0]):
                    parts.pop(0)
                    continue
                if parts[0] in {"-u", "--unset"} and len(parts) > 1:
                    parts[:2] = []
                    continue
                if parts[0].startswith("-"):
                    parts.pop(0)
                    continue
                break
            continue
        break
    return parts


def is_install_command(command: list[str]) -> bool:
    """Return whether argv describes a common package installation action."""
    parts = _unwrap_command(command)
    if not parts:
        return False

    executable = _basename(parts[0])
    arguments = [argument.lower() for argument in parts[1:]]
    if (
        _is_python_executable(executable)
        and len(arguments) >= 3
        and arguments[0] == "-m"
        and arguments[1] in {"pip", "pip3"}
    ):
        return arguments[2] == "install"
    if executable == "uv":
        return bool(
            arguments
            and (
                arguments[0] == "add"
                or arguments[:2] == ["pip", "install"]
            )
        )
    if executable == "dotnet":
        return arguments[:2] == ["add", "package"] or arguments[:2] == [
            "tool",
            "install",
        ]
    if executable == "pacman":
        return any(argument == "-s" or argument.startswith("-s") for argument in arguments)

    actions = _INSTALL_ACTIONS.get(executable)
    return bool(actions and arguments and arguments[0] in actions)


def _redact_secrets(command_text: str) -> str:
    text = re.sub(
        r"(?i)\b(token|password|passwd|secret|api[_-]?key)=([^\s]+)",
        r"\1=[REDACTED]",
        command_text,
    )
    return re.sub(
        r"(?i)(--(?:token|password|passwd|secret|api[-_]?key)\s+)([^\s]+)",
        r"\1[REDACTED]",
        text,
    )


def _make_prompt(command: list[str]) -> str:
    safe_command = _redact_secrets(shlex.join(command))
    return (
        "You are a playful, eerie terminal ghost. In one or two short sentences, "
        "comment on this package installation. Be spooky but harmless; do not "
        "give advice, claim the command succeeded, or output instructions. "
        f"Command: {safe_command}"
    )


def _fallback_commentary() -> str:
    return random.choice(_FALLBACKS)


def _model_timeout_seconds() -> int:
    value = os.environ.get("HAUNTED_TIMEOUT_SECONDS")
    if value is None:
        return MODEL_TIMEOUT_SECONDS
    try:
        timeout = int(value)
    except ValueError as error:
        raise ValueError("HAUNTED_TIMEOUT_SECONDS must be a positive integer") from error
    if timeout <= 0:
        raise ValueError("HAUNTED_TIMEOUT_SECONDS must be a positive integer")
    return timeout


def generate_commentary(command: list[str]) -> str:
    payload = json.dumps(
        {
            "model": os.environ.get("HAUNTED_MODEL", DEFAULT_MODEL),
            "prompt": _make_prompt(command),
            "stream": False,
            "options": {"temperature": 0.9, "num_predict": 70},
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        OLLAMA_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(
            request,
            timeout=_model_timeout_seconds(),
        ) as response:
            result = json.loads(response.read().decode("utf-8"))
        if not isinstance(result, dict) or not isinstance(result.get("response"), str):
            raise ValueError("Gemma returned an invalid response")
        commentary = result["response"].strip()
        if not commentary:
            raise ValueError("Gemma returned an empty response")
        return " ".join(commentary.split())[:240]
    except (
        OSError,
        json.JSONDecodeError,
        KeyError,
        TypeError,
        ValueError,
    ) as error:
        print(
            f"haunted: Gemma unavailable ({error}); using an offline whisper.",
            file=sys.stderr,
        )
        return _fallback_commentary()


def run_command(command: list[str]) -> int:
    if is_install_command(command):
        print("\n[THE GHOST AWAKENS]\n")
        print(f'"{generate_commentary(command)}"\n', flush=True)

    try:
        return subprocess.run(command, check=False).returncode
    except FileNotFoundError:
        print(f"haunted: command not found: {command[0]}", file=sys.stderr)
        return 127
    except PermissionError:
        print(f"haunted: permission denied: {command[0]}", file=sys.stderr)
        return 126
    except OSError as error:
        print(f"haunted: could not run {command[0]}: {error}", file=sys.stderr)
        return 126
