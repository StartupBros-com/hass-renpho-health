"""Synthetic privacy and HA lifecycle fixtures; no live installation/account."""

from __future__ import annotations

import asyncio
import logging
import os
import time
import traceback
from datetime import UTC
from unittest.mock import AsyncMock, patch

import pytest
import zstandard
from aiohttp import web
from aiohttp.test_utils import TestServer
from homeassistant.config_entries import (
    ConfigEntries,
    ConfigEntry,
    ConfigEntryState,
    current_entry,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import frame

from custom_components.renpho_health import async_setup_entry, async_unload_entry
from custom_components.renpho_health.api import (
    RenphoHealthApi,
    RenphoMeasurement,
    RenphoUser,
)
from custom_components.renpho_health.const import DOMAIN
from custom_components.renpho_health.coordinator import RenphoHealthCoordinator
from custom_components.renpho_health.sensor import (
    SENSOR_DESCRIPTIONS,
    RenphoHealthSensor,
)

SECRET = "CANARY_PRIVATE_97f0_account_health"


def entry():
    """Use actual HA entries across both supported constructor versions."""
    import inspect

    values = {
        "version": 1,
        "minor_version": 1,
        "domain": DOMAIN,
        "title": "fixture",
        "data": {"email": "fixture@example.invalid", "password": "fixture"},
        "source": "user",
        "options": {},
        "unique_id": None,
        "discovery_keys": {},
        "subentries_data": [],
    }
    return ConfigEntry(
        **{
            k: v
            for k, v in values.items()
            if k in inspect.signature(ConfigEntry).parameters
        }
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("encoding", ["plain", "zstd", SECRET])
async def test_invalid_json_privacy(caplog, encoding):
    caplog.set_level(logging.DEBUG, logger="custom_components.renpho_health")
    body = (SECRET + " invalid json").encode()
    if encoding == "zstd":
        body = zstandard.ZstdCompressor().compress(body)

    async def handle(request):
        return web.Response(body=body, headers={"Content-Encoding": encoding})

    app = web.Application()
    app.router.add_get("/", handle)
    api = RenphoHealthApi("fixture", "fixture")
    try:
        async with TestServer(app) as server:
            session = await api._get_session()
            async with session.get(server.make_url("/")) as response:
                with pytest.raises(Exception) as caught:
                    await api._parse_response(response)
        rendered = "".join(traceback.format_exception(caught.value))
        assert SECRET not in caplog.text + rendered
        assert SECRET.encode().hex() not in caplog.text
    finally:
        await api.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", [False, True])
async def test_coordinator_privacy(caplog, failure, tmp_path):
    caplog.set_level(logging.DEBUG, logger="custom_components.renpho_health")
    hass = HomeAssistant(str(tmp_path))
    if hasattr(frame, "async_setup"):
        frame.async_setup(hass)
    api = RenphoHealthApi("fixture", "fixture")
    api.get_user = AsyncMock(return_value=RenphoUser(SECRET, SECRET))
    api.get_latest_measurement = AsyncMock(
        return_value=RenphoMeasurement(SECRET, 1710054000, weight=71.125)
    )
    if failure:
        api.get_latest_measurement.side_effect = ValueError(SECRET)
    coordinator = RenphoHealthCoordinator(hass, api, 3600)
    try:
        if failure:
            with pytest.raises(Exception) as caught:
                await coordinator._async_update_data()
            assert SECRET not in "".join(traceback.format_exception(caught.value))
        else:
            assert (await coordinator._async_update_data())["weight"] == 71.125
        assert SECRET not in caplog.text
    finally:
        await api.close()
        await hass.async_stop()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "failure",
    [
        "refresh",
        "cancel",
        "forward",
        "forward_cancel",
        "replaced",
        "previous",
        "success",
    ],
)
async def test_lifecycle(failure, tmp_path):
    hass = HomeAssistant(str(tmp_path))
    hass.config_entries = ConfigEntries(hass, {})
    if hasattr(frame, "async_setup"):
        frame.async_setup(hass)
    config = entry()
    config._async_set_state(hass, ConfigEntryState.SETUP_IN_PROGRESS, None)
    token = current_entry.set(config)
    api = RenphoHealthApi("fixture", "fixture")
    session = await api._get_session()
    api.get_user = AsyncMock(return_value=RenphoUser("fixture", "fixture"))
    api.get_latest_measurement = AsyncMock(return_value=None)
    if failure in {"refresh", "cancel"}:
        api.get_user.side_effect = (
            asyncio.CancelledError() if failure == "cancel" else ValueError(SECRET)
        )
    unrelated = object()
    hass.data[DOMAIN] = {"other": unrelated}
    previous = object()
    replacement = object()
    if failure == "previous":
        hass.data[DOMAIN][config.entry_id] = previous

    async def forward_failure(*args):
        if failure == "replaced":
            hass.data[DOMAIN][config.entry_id] = replacement
        if failure == "forward_cancel":
            asyncio.current_task().cancel()
            await asyncio.sleep(0)
        if failure in {"forward", "previous", "replaced"}:
            raise RuntimeError("platform")

    forward = AsyncMock(side_effect=forward_failure)
    try:
        with (
            patch("custom_components.renpho_health.RenphoHealthApi", return_value=api),
            patch.object(
                type(hass.config_entries), "async_forward_entry_setups", forward
            ),
        ):
            if failure == "success":
                assert await async_setup_entry(hass, config)
                assert not session.closed
                for result in (False, True):
                    with patch.object(
                        type(hass.config_entries),
                        "async_unload_platforms",
                        AsyncMock(return_value=result),
                    ):
                        assert await async_unload_entry(hass, config) is result
                        assert session.closed is result
            else:
                with pytest.raises((asyncio.CancelledError, Exception)):
                    await async_setup_entry(hass, config)
                assert session.closed
                if failure == "previous":
                    assert hass.data[DOMAIN][config.entry_id] is previous
                elif failure == "replaced":
                    assert hass.data[DOMAIN][config.entry_id] is replacement
                else:
                    assert config.entry_id not in hass.data[DOMAIN]
        assert hass.data[DOMAIN]["other"] is unrelated
    finally:
        current_entry.reset(token)
        await api.close()
        await hass.async_stop()


@pytest.mark.parametrize("zone", ["UTC", "America/New_York", "Asia/Kolkata"])
@pytest.mark.parametrize("epoch", [1710053999, 1710054000, 1730613599, 1730613600])
def test_utc_measurement(zone, epoch):
    previous = os.environ.get("TZ")
    try:
        os.environ["TZ"] = zone
        time.tzset()
        measurement = RenphoMeasurement("fixture", epoch, weight=71.125)
        assert measurement.datetime.tzinfo is UTC
        assert measurement.datetime.timestamp() == epoch
        assert measurement.weight == 71.125
        coordinator = type(
            "Coordinator",
            (),
            {
                "data": {"last_updated": measurement.datetime},
                "async_add_listener": None,
            },
        )()
        sensor = RenphoHealthSensor(coordinator, SENSOR_DESCRIPTIONS[0], entry())
        assert sensor.extra_state_attributes["measurement_time"].endswith("+00:00")
    finally:
        if previous is None:
            os.environ.pop("TZ", None)
        else:
            os.environ["TZ"] = previous
        time.tzset()


@pytest.mark.asyncio
@pytest.mark.parametrize("code", [106, SECRET, {"private": SECRET}])
async def test_provider_rejection_privacy(monkeypatch, caplog, code):
    from custom_components.renpho_health import api as api_module
    from custom_components.renpho_health.api import RenphoAuthError

    caplog.set_level(logging.DEBUG, logger="custom_components.renpho_health")

    async def handle(request):
        return web.json_response({"code": code, "msg": SECRET})

    app = web.Application()
    app.router.add_post("/{path:.*}", handle)
    api = RenphoHealthApi("fixture", "fixture")
    try:
        async with TestServer(app) as server:
            monkeypatch.setattr(api_module, "API_BASE", str(server.make_url("")))
            with pytest.raises(RenphoAuthError) as caught:
                await api.authenticate()
        assert SECRET not in caplog.text + "".join(
            traceback.format_exception(caught.value)
        )
    finally:
        await api.close()


@pytest.mark.asyncio
async def test_config_flow_unexpected_privacy(caplog, tmp_path):
    from custom_components.renpho_health.config_flow import RenphoHealthConfigFlow

    hass = HomeAssistant(str(tmp_path))
    hass.config_entries = ConfigEntries(hass, {})
    flow = RenphoHealthConfigFlow()
    flow.hass = hass
    flow.context = {"source": "user"}
    api = RenphoHealthApi("fixture", "fixture")
    api.validate_credentials = AsyncMock(side_effect=ValueError(SECRET))
    session = await api._get_session()
    try:
        with patch(
            "custom_components.renpho_health.config_flow.RenphoHealthApi",
            return_value=api,
        ):
            result = await flow.async_step_user(
                {"email": "fixture@example.invalid", "password": "fixture"}
            )
        assert result["errors"] == {"base": "unknown"}
        assert session.closed
        assert SECRET not in caplog.text
    finally:
        await api.close()
        await hass.async_stop()
