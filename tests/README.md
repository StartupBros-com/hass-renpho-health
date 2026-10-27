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
zstd, unlabelled zstd, and plain JSON incorrectly labelled as zstd. Coverage also checks protocol headers,
unchanged login data, large IDs, measurement ordering, stale identity exclusion
on forced login, invalid credentials, missing authentication fields, and bounded
refresh retries. HTTP and cryptography are not mocked; no live credentials or
external network services are used.

These checks do not establish live Renpho account acceptance or operation in a
running Home Assistant UI. The dependency file pins the directly tested packages;
it is not a complete transitive dependency lockfile.

## Minimum compatibility lane

Use a separate environment; do not override the modern dependency set with an
older Home Assistant, because HA pins incompatible aiohttp/dependency versions.

```sh
uv venv --python 3.11.14 .venv-min
uv pip install --python .venv-min/bin/python -r tests/requirements-min.txt
.venv-min/bin/python -m pytest -q
.venv-min/bin/python -m compileall -q custom_components tests
```

The bounded CI matrix covers actual Home Assistant 2024.1.0 / Python 3.11.14 and
Home Assistant 2026.2.3 / Python 3.13.11. Ruff and mypy run in the modern lane.
Config-flow result typing uses a type-checking-only import so the newer
`ConfigFlowResult` name is not required at runtime on HA 2024.1.0.

Maintenance tests add synthetic privacy canaries for successful fetches, raw and
zstd invalid JSON, untrusted provider codes/messages/encoding headers, schema and
transport exceptions, and coordinator/config-flow exceptions. Assertions inspect
captured logs and formatted exception chains. This adapts the privacy-canary idea
from the MIT renpho-mcp-server; no implementation code is copied.

Lifecycle fixtures instantiate real `HomeAssistant`, `ConfigEntries`, and
`ConfigEntry` objects, set the HA entry context/state, and call this integration's
actual `async_setup_entry` / `async_unload_entry` and real coordinator first refresh.
They replace only API results and platform forwarding/unloading collaborators.
They check private-session closure on refresh failure, cancellation and forwarding
failure, preservation of unrelated/replacement/pre-existing state, a usable session
after successful setup, and closure only after successful unload. Fixtures close
sessions and stop their HA instances. These are local fixture tests, not live HA
installations or full platform/UI setup tests.

Timezone tests change the process timezone (restoring it after each case) to UTC,
New York and Kolkata, covering both sides of US DST transitions. They verify the
exact instant, unchanged measurement value and the existing `measurement_time`
sensor attribute's UTC offset. That attribute name is preserved.

## Official integration validators

PR CI runs [official Hassfest](https://developers.home-assistant.io/blog/2020/04/16/hassfest/)
using `home-assistant/actions/hassfest` at action source
`86d4564712fa02543c808e3a693dd04f9d3f8361`. It accepts no inputs. The workflow runs
on public GitHub-hosted Ubuntu with `contents: read`, no custom secrets and no
live Renpho login. Tests are not filtered out on pull requests.

The separate [official HACS action](https://www.hacs.xyz/docs/publish/action/)
can be configured as follows once the external catalog prerequisites are met:

```yaml
- uses: hacs/action@d556e736723344f83838d08488c983a15381059a # 22.5.0
  with:
    category: integration
    comment: "false"
```

The token defaults to `github.token`; no custom secret is needed. Run the complete
validator without ignore flags. There is deliberately no failing or
`continue-on-error` HACS PR job: catalog readiness currently lacks the
`renpho_health` entry in Home Assistant brands. Custom
repository installation does not establish full HACS catalog eligibility.

Both validator wrappers reference mutable Docker images: these are pinned action
sources, not fully reproducible validator runtimes. Local unit checks and
`actionlint .github/workflows/checks.yml` do not establish that a hosted Hassfest
or HACS run has passed. Check the actual PR runs before merging.
