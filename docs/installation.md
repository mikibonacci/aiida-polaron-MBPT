# Installation

The package needs Python 3.10 or newer, with compatible installations of `aiida-core`, `aiida-quantumespresso`, `aiida-yambo` and `aiida-pseudo`. All of these are installed as dependencies.

```bash
git clone https://github.com/mikibonacci/aiida-polaron-MBPT.git
pip install -e aiida-polaron-MBPT
```

Then restart the AiiDA daemon (`verdi daemon restart`) so that it picks up the new entry point. Check that the workflow is registered:

```bash
verdi plugin list aiida.workflows polaron_mbpt
```

## What you need in your AiiDA profile

- A configured profile, with a running daemon.
- Codes for `pw.x`, `yambo` and `p2y`.
- A pseudopotential family installed with `aiida-pseudo`, for example:

```bash
aiida-pseudo install pseudo-dojo -v 0.4 -x PBE -r SR -p standard -f upf
```

## Building the documentation locally

```bash
pip install -e ".[docs]"
mkdocs serve
```
