"""Renpho Health API client."""
from __future__ import annotations

import hashlib
import re
from base64 import b64decode, b64encode
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
import aiohttp

from .const import API_BASE, ENCRYPTION_SECRET


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

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def close(self) -> None:
        """Close the API client session."""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None

    async def authenticate(self) -> None:
        """Authenticate with Renpho Health API."""
        import json

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
            headers={"Content-Type": "application/json"},
        ) as response:
            result = await response.json()

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
        import json

        session = await self._get_session()

        async with session.post(
            f"{API_BASE}/renpho-aggregation/device/count",
            json={"encryptData": self._encrypt_empty()},
            headers={
                "Content-Type": "application/json",
                "token": self._token,
                "userId": self._user_id,
                "appVersion": "7.0.0",
                "platform": "android",
            },
        ) as response:
            result = await response.json()

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

    async def _ensure_authenticated(self) -> None:
        """Ensure we have valid authentication."""
        if not self._token:
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

    async def get_measurements(self, limit: int = 100) -> list[RenphoMeasurement]:
        """Get measurements from the API."""
        import json

        await self._ensure_authenticated()
        session = await self._get_session()

        request_data = {
            "pageNum": 1,
            "pageSize": limit,
            "userIds": [self._scale_user_id],
            "tableName": self._table_name,
        }

        async with session.post(
            f"{API_BASE}/RenphoHealth/scale/queryAllMeasureDataList",
            json={"encryptData": self._encrypt(json.dumps(request_data))},
            headers={
                "Content-Type": "application/json",
                "token": self._token,
                "userId": self._user_id,
                "appVersion": "7.0.0",
                "platform": "android",
            },
        ) as response:
            result = await response.json()

        if result.get("code") != 101:
            raise RenphoApiError(f"Failed to get measurements: {result.get('msg')}")

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
