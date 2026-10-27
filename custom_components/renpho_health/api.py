"""Renpho Health API client."""
from __future__ import annotations

import gzip
import io
import json
import logging
import re
import zlib
from base64 import b64decode, b64encode
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import aiohttp
import zstandard as zstd
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad

from .const import API_BASE, ENCRYPTION_SECRET

_LOGGER = logging.getLogger(__name__)


@dataclass
class RenphoUser:
    """Renpho user data."""

    user_id: str
    email: str
    account_name: str | None = None
    gender: int | None = None
    height: float | None = None
    birthday: str | None = None


@dataclass
class RenphoMeasurement:
    """Renpho measurement data."""

    id: str
    timestamp: int
    weight: float | None = None
    bmi: float | None = None
    bodyfat: float | None = None
    water: float | None = None
    muscle: float | None = None
    bone: float | None = None
    bmr: int | None = None
    visceral_fat: int | None = None
    body_age: int | None = None
    protein: float | None = None
    subcutaneous_fat: float | None = None
    skeletal_muscle: float | None = None
    heart_rate: int | None = None

    @property
    def datetime(self) -> datetime:
        """Return measurement datetime."""
        return datetime.fromtimestamp(self.timestamp)


class RenphoApiError(Exception):
    """Renpho API error."""


class RenphoAuthError(RenphoApiError):
    """Renpho authentication error."""


class RenphoHealthApi:
    """Renpho Health API client.

    Uses the Renpho Health API (cloud.renpho.com) with AES-128-ECB encryption.
    """

    def __init__(self, email: str, password: str) -> None:
        """Initialize the API client."""
        self._email = email
        self._password = password
        self._session: aiohttp.ClientSession | None = None
        self._token: str | None = None
        self._user_id: str | None = None
        self._scale_user_id: str | None = None
        self._table_name: str | None = None
        self._user: RenphoUser | None = None

    def _encrypt(self, content: str) -> str:
        """Encrypt content using AES-128-ECB."""
        cipher = AES.new(
            ENCRYPTION_SECRET.encode("utf-8"),
            AES.MODE_ECB
        )
        padded = pad(content.encode("utf-8"), AES.block_size)
        encrypted = cipher.encrypt(padded)
        return b64encode(encrypted).decode("utf-8")

    def _encrypt_empty(self) -> str:
        """Encrypt empty bytes for endpoints that require it."""
        cipher = AES.new(
            ENCRYPTION_SECRET.encode("utf-8"),
            AES.MODE_ECB
        )
        encrypted = cipher.encrypt(pad(b"", AES.block_size))
        return b64encode(encrypted).decode("utf-8")

    def _decrypt(self, encrypted_content: str) -> str:
        """Decrypt content using AES-128-ECB."""
        cipher = AES.new(
            ENCRYPTION_SECRET.encode("utf-8"),
            AES.MODE_ECB
        )
        decrypted = cipher.decrypt(b64decode(encrypted_content))
        return unpad(decrypted, AES.block_size).decode("utf-8")

    def _extract_id(self, json_str: str, key: str) -> str | None:
        """Extract large integer ID as string to avoid precision loss."""
        match = re.search(rf'"{key}":(\d+)', json_str)
        return match.group(1) if match else None

    def _extract_user_ids(self, json_str: str) -> list[str]:
        """Extract userIds array as strings to avoid precision loss."""
        match = re.search(r'"userIds":\[(\d+(?:,\d+)*)\]', json_str)
        return match.group(1).split(",") if match else []

    def _request_headers(self, *, authenticated: bool = False) -> dict[str, str]:
        """Build protocol headers, validating identity for authenticated requests."""
        headers = {
            "Content-Type": "application/json",
            "appVersion": "7.0.0",
            "platform": "android",
        }
        if authenticated:
            if self._token is None or self._user_id is None:
                raise RenphoAuthError("Authentication required for request headers")
            headers["token"] = self._token
            headers["userId"] = self._user_id
        return headers

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self._session is None or self._session.closed:
            # Advertise gzip/deflate; the parser also handles unsolicited zstd.
            headers = {"Accept-Encoding": "gzip, deflate"}
            self._session = aiohttp.ClientSession(headers=headers, auto_decompress=False)
        return self._session

    async def _parse_response(self, response: aiohttp.ClientResponse) -> dict[str, Any]:
        """Parse raw response bytes, owning all advertised decompression."""
        content_encoding = response.headers.get("Content-Encoding", "").lower()
        raw_data = await response.read()

        _LOGGER.debug(
            "Response status=%d, encoding='%s', size=%d, first_bytes=%s",
            response.status,
            content_encoding,
            len(raw_data),
            raw_data[:20].hex() if raw_data else "empty",
        )

        if content_encoding == "gzip":
            raw_data = gzip.decompress(raw_data)
        elif content_encoding == "deflate":
            try:
                raw_data = zlib.decompress(raw_data)
            except zlib.error:
                raw_data = zlib.decompress(raw_data, -zlib.MAX_WBITS)

        # Check for zstd magic bytes (0x28, 0xB5, 0x2F, 0xFD)
        is_zstd_data = len(raw_data) >= 4 and raw_data[:4] == b'\x28\xb5\x2f\xfd'

        if content_encoding == "zstd" or is_zstd_data:
            try:
                # Use streaming decompression to handle all frames
                decompressor = zstd.ZstdDecompressor()
                with decompressor.stream_reader(io.BytesIO(raw_data)) as reader:
                    decompressed = reader.read()
                decoded = decompressed.decode("utf-8")
                _LOGGER.debug("zstd decompression successful, size: %d, content: %.200s", len(decoded), decoded)
                return json.loads(decoded)
            except zstd.ZstdError as err:
                _LOGGER.warning("zstd decompression failed: %s", err)
                # Fall through to try raw JSON
            except json.JSONDecodeError as err:
                _LOGGER.error("zstd decompressed but invalid JSON: %s, content: %.500s", err, decoded[:500])
                raise

        # Try parsing as regular JSON
        try:
            return json.loads(raw_data.decode("utf-8"))
        except json.JSONDecodeError:
            _LOGGER.error(
                "Failed to parse response (status %d, encoding=%s): %s",
                response.status,
                content_encoding,
                raw_data[:500],
            )
            raise

    async def close(self) -> None:
        """Close the API client session."""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None

    async def authenticate(self) -> None:
        """Authenticate with Renpho Health API."""
        session = await self._get_session()

        login_data = {
            "questionnaire": {},
            "login": {
                "password": self._password,
                "areaCode": "US",
                "appRevision": "7.0.0",
                "cellphoneType": "HomeAssistant",
                "systemType": "11",
                "email": self._email,
                "platform": "android",
            },
            "bindingList": {"deviceTypes": ["2"]},
        }

        async with session.post(
            f"{API_BASE}/renpho-aggregation/user/login",
            json={"encryptData": self._encrypt(json.dumps(login_data))},
            headers=self._request_headers(),
        ) as response:
            result = await self._parse_response(response)

        if result.get("code") != 101:
            raise RenphoAuthError(f"Authentication failed: {result.get('msg', 'Unknown error')}")

        raw_data = self._decrypt(result["data"])
        data = json.loads(raw_data)
        login = data["login"]

        # Extract user ID as string to preserve precision
        self._user_id = self._extract_id(raw_data, "id") or str(login["id"])
        self._token = login["token"]

        self._user = RenphoUser(
            user_id=self._user_id,
            email=login["email"],
            account_name=login.get("accountName"),
            gender=login.get("gender"),
            height=login.get("height"),
            birthday=login.get("birthday"),
        )

        # Get device info for table name
        await self._get_device_info()

    async def _get_device_info(self) -> None:
        """Get device info to determine measurement table."""
        session = await self._get_session()

        async with session.post(
            f"{API_BASE}/renpho-aggregation/device/count",
            json={"encryptData": self._encrypt_empty()},
            headers=self._request_headers(authenticated=True),
        ) as response:
            result = await self._parse_response(response)

        if result.get("code") != 101:
            raise RenphoApiError(f"Failed to get device info: {result.get('msg')}")

        raw_data = self._decrypt(result["data"])
        data = json.loads(raw_data)

        if not data.get("scale"):
            raise RenphoApiError("No scale devices found")

        scale_info = data["scale"][0]
        self._table_name = scale_info["tableName"]

        # Extract scale user ID as string
        user_ids = self._extract_user_ids(raw_data)
        self._scale_user_id = user_ids[0] if user_ids else str(scale_info["userIds"][0])

    async def _ensure_authenticated(self, force: bool = False) -> None:
        """Ensure we have valid authentication."""
        if force or not self._token:
            await self.authenticate()

    async def get_user(self) -> RenphoUser:
        """Get the current user."""
        await self._ensure_authenticated()
        if not self._user:
            raise RenphoApiError("User not available")
        return self._user

    async def get_latest_measurement(self) -> RenphoMeasurement | None:
        """Get the most recent measurement."""
        measurements = await self.get_measurements(limit=1000)
        return measurements[0] if measurements else None

    async def get_measurements(self, limit: int = 100, _retry: bool = True) -> list[RenphoMeasurement]:
        """Get measurements from the API."""
        await self._ensure_authenticated()
        session = await self._get_session()

        request_data = {
            "pageNum": 1,
            "pageSize": limit,
            "userIds": [self._scale_user_id],
            "tableName": self._table_name,
        }
        _LOGGER.debug(
            "Requesting measurements: userId=%s, scaleUserId=%s, tableName=%s",
            self._user_id, self._scale_user_id, self._table_name
        )

        async with session.post(
            f"{API_BASE}/RenphoHealth/scale/queryAllMeasureDataList",
            json={"encryptData": self._encrypt(json.dumps(request_data))},
            headers=self._request_headers(authenticated=True),
        ) as response:
            result = await self._parse_response(response)

        _LOGGER.debug("Measurements API response: code=%s, msg=%s", result.get("code"), result.get("msg"))
        if result.get("code") != 101:
            # Token may have expired - try re-authenticating once
            if _retry:
                _LOGGER.warning("Measurements request failed (code=%s), re-authenticating and retrying", result.get("code"))
                await self._ensure_authenticated(force=True)
                return await self.get_measurements(limit=limit, _retry=False)
            raise RenphoApiError(f"Failed to get measurements: code={result.get('code')}, msg={result.get('msg')}")

        raw_measurements = json.loads(self._decrypt(result["data"]))

        # Sort by timestamp descending (most recent first)
        raw_measurements.sort(key=lambda m: m.get("timeStamp", 0), reverse=True)

        measurements = []
        for m in raw_measurements:
            measurements.append(
                RenphoMeasurement(
                    id=str(m.get("id", "")),
                    timestamp=m.get("timeStamp", 0),
                    weight=m.get("weight"),
                    bmi=m.get("bmi"),
                    bodyfat=m.get("bodyfat"),
                    water=m.get("water"),
                    muscle=m.get("muscle"),
                    bone=m.get("bone"),
                    bmr=m.get("bmr"),
                    visceral_fat=m.get("visfat"),
                    body_age=m.get("bodyage"),
                    protein=m.get("protein"),
                    subcutaneous_fat=m.get("subfat"),
                    skeletal_muscle=m.get("sinew"),
                    heart_rate=m.get("heartRate"),
                )
            )

        return measurements

    async def validate_credentials(self) -> bool:
        """Validate credentials by attempting to authenticate."""
        try:
            await self.authenticate()
            return True
        except RenphoAuthError:
            return False
