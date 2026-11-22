# Renpho Health for Home Assistant: agent instructions

This file guides AI coding agents working in this repository. `CLAUDE.md` imports it, so edit this file.

A Home Assistant custom integration (domain `renpho_health`, distributed through HACS) that polls the Renpho Health cloud API (`cloud.renpho.com`) and exposes body composition readings from Renpho smart scales as sensors. Python, Home Assistant config flow plus a `DataUpdateCoordinator`, `aiohttp` for HTTP, `pycryptodome` for the AES payload encoding and `zstandard` for response bodies (`README.md`, `custom_components/renpho_health/manifest.json`).

## Repo map

- `custom_components/renpho_health/api.py`: Renpho client: login, device and measurement requests, AES payload encoding, response decoding (plain, gzip, deflate, zstd), token refresh retries.
- `custom_components/renpho_health/coordinator.py`, `sensor.py`, `config_flow.py`, `__init__.py`: coordinator, the 12 sensors, the UI setup flow, and `async_setup_entry` / `async_unload_entry`.
- `custom_components/renpho_health/const.py`, `translations/en.json`: constants and UI strings.
- `custom_components/renpho_health/manifest.json`: `requirements` (version floors) and the integration `version`.
- `hacs.json`: HACS metadata, including the `homeassistant` minimum (`2024.1.0`).
- `tests/test_api.py`, `tests/test_maintenance.py`: the whole test suite (49 tests). `tests/README.md` explains what the tests do and do not prove.
- `tests/requirements.txt` (modern lane) and `tests/requirements-min.txt` (minimum lane): exact test pins.
- `renovate.json`: Renovate rules that protect the floors (see Rules).
- `.github/workflows/checks.yml`: CI, the source of truth for the gate commands.

## Setup and commands

Use `uv`, from the repo root. Two separate environments are needed; never install an older Home Assistant over the modern one, because HA pins conflicting aiohttp versions (`tests/README.md`).

```sh
# Modern lane: Python 3.13.11, Home Assistant 2026.2.3
uv venv --python 3.13.11 .venv
uv pip install --python .venv/bin/python -r tests/requirements.txt
.venv/bin/python -m pytest -q
.venv/bin/ruff check custom_components tests
.venv/bin/mypy --follow-imports=silent custom_components/renpho_health
.venv/bin/python -m compileall -q custom_components tests
git diff --check

# Minimum lane: Python 3.11.14, Home Assistant 2024.1.0
uv venv --python 3.11.14 .venv-min
uv pip install --python .venv-min/bin/python -r tests/requirements-min.txt
.venv-min/bin/python -m pytest -q
.venv-min/bin/python -m compileall -q custom_components tests
```

Ruff and mypy run only in the modern lane. CI also runs Hassfest (`home-assistant/actions/hassfest`), which cannot run locally. `.venv`, `.venv-min` and the tool caches are gitignored.

## Rules and traps

- Keep the code importable on Home Assistant 2024.1.0. The newer `ConfigFlowResult` name is imported under `TYPE_CHECKING` only; do not import HA names at runtime that 2024.1.0 lacks (`tests/README.md`).
- Three places state the minimum Home Assistant and must move together: `hacs.json` `homeassistant`, the README "Requirements" section, and the `homeassistant` pin in `tests/requirements-min.txt`. The CI matrix and the README's tested versions also move together.
- `manifest.json` `requirements` are floors (`>=`), the oldest release that works, installed into Home Assistant's shared environment. Never raise a floor to the newest release; it forces an upgrade for every other integration. `renovate.json` uses `rangeStrategy: "replace"` for this and disables Renovate for the `homeassistant` pin in `tests/requirements-min.txt` (commit 006769d, PR #10). Do not weaken either rule; the tested versions are the exact pins in `tests/requirements*.txt`, which Renovate keeps current.
- Privacy is a tested property: never log account or health payloads, provider response strings or credentials, and never put them in exception messages. `tests/test_maintenance.py` plants privacy canaries and inspects captured logs and formatted exception chains.
- Setup must close the privately owned HTTP session on failure or cancellation and roll back only state it owns; unload closes it only after a successful unload (`tests/test_maintenance.py` lifecycle tests).
- Measurement timestamps are timezone-aware UTC. The `measurement_time` sensor attribute name and entity identifiers are preserved; do not rename them (`tests/README.md`).
- The tests use real AES and a loopback aiohttp server; HTTP and crypto are not mocked. Keep it that way, and keep response-encoding coverage (gzip, deflate, raw deflate, zstd, unlabelled zstd, plain JSON mislabelled as zstd).
- The `tests` job in CI is pinned to `ubuntu-24.04` because `setup-python` has no Ubuntu 26.04 build of the pinned interpreters (commit b096a48). Move the runner and the matrix together.
- The `.github/workflows/checks.yml` action references are pinned to commit SHAs; keep them pinned.
- The version in `manifest.json` is the release version. Do not bump it unless the task is a release.
- Local checks do not prove acceptance by a live Renpho account or a running Home Assistant. Say so rather than claiming it. Full HACS catalog eligibility is blocked on a Home Assistant brands entry (`README.md`); do not add a failing or `continue-on-error` HACS job.

## Definition of done

- Both lanes pass: `pytest` and `compileall` on 3.11.14 / HA 2024.1.0 and on 3.13.11 / HA 2026.2.3.
- `ruff check`, `mypy` and `git diff --check` are clean in the modern lane.
- The `Checks` workflow (`tests` matrix and `hassfest`) is green on the PR.
- Behaviour changes come with a test in `tests/`; a bug fix has a test that fails without it.
- README, `hacs.json` and `tests/README.md` still agree with any version or behaviour you changed.

Verify your work. If any command fails or you couldn't run it, say which and why.
