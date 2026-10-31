# Haunted Terminal

A small, opt-in terminal wrapper that adds eerie commentary before package
installation commands. It uses Gemma locally through Ollama.

## Requirements

- Python 3
- [Ollama](https://ollama.com/) with Gemma available

Pull the default model once:

```sh
ollama pull gemma3:1b
```

## Run it

Use the full path to the launcher from any directory. The wrapped command runs
in your current directory:

```sh
/path/to/haunted-terminal/haunted run -- npm install
```

For example, run `npm install` from a Node project directory that contains a
`package.json`. To safely check the ghost without installing anything:

```sh
/path/to/haunted-terminal/haunted run -- python3 -m pip install --help
```

It also recognizes install commands such as:

```sh
/path/to/haunted-terminal/haunted run -- python3 -m pip install requests
/path/to/haunted-terminal/haunted run -- cargo add serde
```

The wrapper runs only the command you explicitly provide. It does not monitor
or modify your existing shell, and it does not evaluate Gemma's response.

## Configure

The default model is `gemma3:1b`. Select another model already available in
Ollama with `HAUNTED_MODEL`:

```sh
HAUNTED_MODEL=gemma3:4b /path/to/haunted-terminal/haunted run -- npm install
```

Gemma has up to 120 seconds to respond. Change that limit with
`HAUNTED_TIMEOUT_SECONDS`:

```sh
HAUNTED_TIMEOUT_SECONDS=180 /path/to/haunted-terminal/haunted run -- npm install
```

If Ollama is stopped or Gemma times out, the wrapper prints a built-in spooky
line and still runs the requested command.

## Run tests

The test suite uses Python's standard library and does not need Ollama:

```sh
python3 -m unittest discover -s tests -v
```
