"""Exercise the Renpho protocol over local HTTP with real AES encryption."""

from __future__ import annotations

import gzip
import json
import zlib
from base64 import b64decode, b64encode
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

import pytest
import pytest_asyncio
import zstandard as zstd
from aiohttp import web
from aiohttp.test_utils import TestServer
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad

from custom_components.renpho_health import api as api_module
from custom_components.renpho_health.api import (
    RenphoApiError,
    RenphoAuthError,
    RenphoHealthApi,
)
from custom_components.renpho_health.const import ENCRYPTION_SECRET

LOGIN = "/renpho-aggregation/user/login"
DEVICES = "/renpho-aggregation/device/count"
MEASUREMENTS = "/RenphoHealth/scale/queryAllMeasureDataList"
USER_ID = 1234567890123456789
SCALE_USER_ID = 9876543210987654321


def encrypt(value: Any) -> str:
    """Build a server response without replacing the client's crypto methods."""
    cipher = AES.new(ENCRYPTION_SECRET.encode(), AES.MODE_ECB)
    return b64encode(
        cipher.encrypt(pad(json.dumps(value).encode(), AES.block_size))
    ).decode()


@dataclass
class RenphoServer:
    """A local protocol fixture, not evidence of live Renpho acceptance."""

    requests: list[tuple[str, dict[str, str], Any]] = field(default_factory=list)
    login_count: int = 0
    measurement_count: int = 0
    reject_login: bool = False
    expire_measurements: int = 0
    encoding: str = "plain"

    async def handle(self, request: web.Request) -> web.Response:
        envelope = await request.json()
        assert set(envelope) == {"encryptData"}
        cipher = AES.new(ENCRYPTION_SECRET.encode(), AES.MODE_ECB)
        plaintext = unpad(
            cipher.decrypt(b64decode(envelope["encryptData"])), AES.block_size
        )
        payload = json.loads(plaintext) if plaintext else None
        self.requests.append((request.path, dict(request.headers), payload))

        # The error reported in issue #3 and the upstream header comparison.
        if (
            request.headers.get("appVersion") != "7.0.0"
            or request.headers.get("platform") != "android"
        ):
            return web.json_response(
                {"code": -114, "message": "Decryption failed", "data": None}
            )

        if request.path == LOGIN:
            self.login_count += 1
            assert "token" not in request.headers
            assert "userId" not in request.headers
            if self.reject_login:
                return web.json_response({"code": 106, "msg": "Invalid credentials"})
            data: Any = {
                "login": {
                    "id": USER_ID,
                    "token": f"token-{self.login_count}",
                    "email": "test@example.invalid",
                }
            }
        else:
            assert request.headers["token"] == f"token-{self.login_count}"
            assert request.headers["userId"] == str(USER_ID)
            if request.path == DEVICES:
                assert plaintext == b""
                data = {
                    "scale": [{"tableName": "scale_test", "userIds": [SCALE_USER_ID]}]
                }
            else:
                assert request.path == MEASUREMENTS
                self.measurement_count += 1
                if self.measurement_count <= self.expire_measurements:
                    return web.json_response({"code": 401, "msg": "Token expired"})
                data = [
                    {"id": "older", "timeStamp": 100, "weight": 70.0},
                    {"id": "newer", "timeStamp": 200, "weight": 71.0},
                ]

        result = {"code": 101, "data": encrypt(data)}
        body = json.dumps(result).encode()
        headers = {}
        if self.encoding == "gzip":
            body = gzip.compress(body)
        elif self.encoding == "deflate":
            body = zlib.compress(body)
        elif self.encoding == "raw-deflate":
            compressor = zlib.compressobj(wbits=-zlib.MAX_WBITS)
            body = compressor.compress(body) + compressor.flush()
        elif self.encoding in {"zstd", "unlabelled-zstd"}:
            body = zstd.ZstdCompressor().compress(body)
        if self.encoding not in {"plain", "unlabelled-zstd"}:
            headers["Content-Encoding"] = (
                "deflate"
                if self.encoding == "raw-deflate"
                else "zstd" if self.encoding == "mislabelled-zstd" else self.encoding
            )
        return web.Response(body=body, headers=headers, content_type="application/json")


@pytest_asyncio.fixture
async def client(
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncIterator[tuple[RenphoHealthApi, RenphoServer]]:
    """Keep every request on loopback, including forced reauthentication."""
    service = RenphoServer()
    app = web.Application()
    app.router.add_post("/{path:.*}", service.handle)
    async with TestServer(app) as server:
        monkeypatch.setattr(api_module, "API_BASE", str(server.make_url("")))
        api = RenphoHealthApi("test@example.invalid", "test-password")
        try:
            yield api, service
        finally:
            await api.close()


@pytest.mark.asyncio
async def test_setup_validation_sends_protocol_headers_and_unchanged_payload(client):
    api, service = client
    assert await api.validate_credentials() is True
    assert [request[0] for request in service.requests] == [LOGIN, DEVICES]
    _, headers, payload = service.requests[0]
    assert headers["Content-Type"] == "application/json"
    assert payload == {
        "questionnaire": {},
        "login": {
            "password": "test-password",
            "areaCode": "US",
            "appRevision": "7.0.0",
            "cellphoneType": "HomeAssistant",
            "systemType": "11",
            "email": "test@example.invalid",
            "platform": "android",
        },
        "bindingList": {"deviceTypes": ["2"]},
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "encoding",
    ["plain", "gzip", "deflate", "raw-deflate", "zstd", "unlabelled-zstd", "mislabelled-zstd"],
)
async def test_initial_refresh_authenticates_and_loads_latest_measurement(
    client, encoding
):
    api, service = client
    service.encoding = encoding
    user = await api.get_user()
    measurement = await api.get_latest_measurement()
    assert user.user_id == str(USER_ID)
    assert measurement is not None
    assert (measurement.id, measurement.weight) == ("newer", 71.0)
    assert service.login_count == 1
    assert [request[0] for request in service.requests] == [
        LOGIN,
        DEVICES,
        MEASUREMENTS,
    ]
    assert all(
        request[1]["Accept-Encoding"] == "gzip, deflate" for request in service.requests
    )
    assert service.requests[-1][2] == {
        "pageNum": 1,
        "pageSize": 1000,
        "userIds": [str(SCALE_USER_ID)],
        "tableName": "scale_test",
    }


@pytest.mark.asyncio
async def test_expired_token_reauthenticates_without_stale_session_headers(client):
    api, service = client
    service.expire_measurements = 1
    measurements = await api.get_measurements(limit=7)
    assert [item.id for item in measurements] == ["newer", "older"]
    assert [request[0] for request in service.requests] == [
        LOGIN,
        DEVICES,
        MEASUREMENTS,
        LOGIN,
        DEVICES,
        MEASUREMENTS,
    ]
    assert service.login_count == 2
    assert service.requests[-1][1]["token"] == "token-2"
    assert service.requests[-1][2]["pageSize"] == 7


@pytest.mark.asyncio
async def test_measurement_retry_remains_bounded(client):
    api, service = client
    service.expire_measurements = 2
    with pytest.raises(RenphoApiError, match="Failed to get measurements"):
        await api.get_measurements()
    assert service.login_count == 2
    assert service.measurement_count == 2


@pytest.mark.asyncio
async def test_invalid_credentials_remain_invalid(client):
    api, service = client
    service.reject_login = True
    assert await api.validate_credentials() is False
    assert service.login_count == 1
    assert len(service.requests) == 1


@pytest.mark.asyncio
async def test_failed_refresh_authentication_does_not_retry_measurements(client):
    api, service = client
    await api.authenticate()
    service.reject_login = True
    service.expire_measurements = 1
    with pytest.raises(RenphoAuthError, match="Invalid credentials"):
        await api.get_measurements()
    assert service.login_count == 2
    assert service.measurement_count == 1


@pytest.mark.parametrize(
    "token,user_id", [(None, None), ("token", None), (None, "user")]
)
def test_authenticated_headers_require_session_fields(token, user_id):
    api = RenphoHealthApi("test@example.invalid", "test-password")
    api._token = token
    api._user_id = user_id
    with pytest.raises(RenphoAuthError, match="Authentication required"):
        api._request_headers(authenticated=True)


@pytest.mark.asyncio
@pytest.mark.parametrize("encoding", ["plain", "zstd"])
async def test_successful_api_fetch_does_not_log_account_or_health_data(
    monkeypatch, caplog, encoding
):
    """Canary strategy adapted conceptually from MIT renpho-mcp-server."""
    import logging

    secret = "CANARY_SUCCESS_3b8c_account_health"
    api = RenphoHealthApi("fixture", "fixture")
    caplog.set_level(logging.DEBUG, logger="custom_components.renpho_health")

    async def handle(request):
        if request.path == LOGIN:
            data = {
                "login": {
                    "id": secret,
                    "token": secret,
                    "email": secret,
                    "birthday": secret,
                }
            }
        elif request.path == DEVICES:
            data = {"scale": [{"tableName": secret, "userIds": [secret]}]}
        else:
            assert request.path == MEASUREMENTS
            data = [{"id": secret, "timeStamp": 1710054000, "weight": 71.125}]
        body = json.dumps({"code": 101, "data": encrypt(data)}).encode()
        headers = {}
        if encoding == "zstd":
            body = zstd.ZstdCompressor().compress(body)
            headers["Content-Encoding"] = "zstd"
        return web.Response(body=body, headers=headers)

    app = web.Application()
    app.router.add_post("/{path:.*}", handle)
    try:
        async with TestServer(app) as server:
            monkeypatch.setattr(api_module, "API_BASE", str(server.make_url("")))
            user = await api.get_user()
            measurement = await api.get_latest_measurement()
        assert user.email == secret
        assert measurement is not None
        assert (measurement.id, measurement.weight) == (secret, 71.125)
        assert secret not in caplog.text
        assert '"timeStamp"' not in caplog.text
        assert '"weight"' not in caplog.text
    finally:
        await api.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["device", "measurement", "schema", "transport"])
async def test_api_boundary_sanitizes_untrusted_errors(monkeypatch, caplog, operation):
    import logging
    import traceback

    secret = "CANARY_PROVIDER_ae09_account_health"
    api = RenphoHealthApi("fixture", "fixture")
    caplog.set_level(logging.DEBUG, logger="custom_components.renpho_health")

    async def handle(request):
        if operation == "schema":
            # Missing protocol fields can cause exceptions naming untrusted keys.
            return web.json_response({"code": 101, "data": encrypt({"login": secret})})
        return web.json_response({"code": {"private": secret}, "msg": secret})

    app = web.Application()
    app.router.add_post("/{path:.*}", handle)
    try:
        async with TestServer(app) as server:
            monkeypatch.setattr(api_module, "API_BASE", str(server.make_url("")))
            if operation == "transport":
                from unittest.mock import AsyncMock

                monkeypatch.setattr(
                    api, "_get_session", AsyncMock(side_effect=RuntimeError(secret))
                )
                action = api.authenticate()
            elif operation == "device":
                api._token, api._user_id = "fixture", "fixture"
                action = api._get_device_info()
            elif operation == "measurement":
                api._token, api._user_id = "fixture", "fixture"
                action = api.get_measurements(_retry=False)
            else:
                action = api.authenticate()
            with pytest.raises(RenphoApiError) as caught:
                await action
        assert secret not in caplog.text + "".join(
            traceback.format_exception(caught.value)
        )
    finally:
        await api.close()
