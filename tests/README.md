# Developer checks

From the repository root, create the tested Python 3.13.11 environment with uv:

```sh
uv venv --python 3.13.11 .venv
uv pip install --python .venv/bin/python -r tests/requirements.txt
```

Run the checks:

```sh
.venv/bin/python -m pytest -q
.venv/bin/ruff check custom_components tests
.venv/bin/mypy --follow-imports=silent custom_components/renpho_health
.venv/bin/python -m compileall -q custom_components tests
git diff --check
```

The tests import the actual integration through installed Home Assistant 2026.2.3
and use real AES encryption and an aiohttp server on loopback. All login, device,
and measurement requests exercise plain JSON, gzip, deflate, raw deflate, labelled
zstd, and unlabelled zstd responses. Coverage also checks protocol headers,
unchanged login data, large IDs, measurement ordering, stale identity exclusion
on forced login, invalid credentials, missing authentication fields, and bounded
refresh retries. HTTP and cryptography are not mocked; no live credentials or
external network services are used.

These checks do not establish live Renpho account acceptance or operation in a
running Home Assistant UI. The dependency file pins the directly tested packages;
it is not a complete transitive dependency lockfile.
