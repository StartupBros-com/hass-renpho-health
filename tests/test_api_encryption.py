"""Offline characterization tests; point RENPHO_SOURCE_ROOT at a repo snapshot."""
import asyncio
import importlib.util
import json
import os
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import AsyncMock, patch

ROOT = Path(os.environ.get("RENPHO_SOURCE_ROOT", Path(__file__).resolve().parents[1]))
PACKAGE = "_renpho_encryption_under_test"
package = types.ModuleType(PACKAGE)
package.__path__ = [str(ROOT / "custom_components" / "renpho_health")]
sys.modules[PACKAGE] = package
# Load the real API without importing the Home Assistant integration initializer.
spec = importlib.util.spec_from_file_location(
    PACKAGE + ".api", Path(package.__path__[0]) / "api.py"
)
api_module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = api_module
spec.loader.exec_module(api_module)


class EncryptionTests(unittest.TestCase):
    def setUp(self):
        self.api = api_module.RenphoHealthApi("synthetic@example.invalid", "synthetic")
        self.network = patch("socket.socket.connect", side_effect=AssertionError("Network forbidden"))
        self.network.start()
        self.addCleanup(self.network.stop)

    def test_empty_known_ciphertext(self):
        # Independently calculated AES-128-ECB / PKCS#7 public protocol vector.
        self.assertEqual(self.api._encrypt_empty(), "ZtDk/16Qik2UaElz2ZzmEg==")

    def test_empty_equals_normal_encrypt(self):
        self.assertEqual(self.api._encrypt_empty(), self.api._encrypt(""))

    def test_empty_decrypts_to_empty_string(self):
        self.assertEqual(self.api._decrypt(self.api._encrypt_empty()), "")

    def test_repeat_calls_are_identical(self):
        self.assertEqual([self.api._encrypt_empty() for _ in range(4)],
                         ["ZtDk/16Qik2UaElz2ZzmEg=="] * 4)

    def test_regular_encryption_round_trips_and_padding(self):
        from base64 import b64decode
        for text in ["", "a", "a" * 15, "a" * 16, "a" * 17, "a" * 32, "é🙂", "\x00"]:
            with self.subTest(text=text):
                encrypted = self.api._encrypt(text)
                self.assertEqual(self.api._decrypt(encrypted), text)
                expected_size = (len(text.encode("utf-8")) // 16 + 1) * 16
                self.assertEqual(len(b64decode(encrypted)), expected_size)

    def test_device_discovery_preserves_wire_request_and_ids(self):
        class Response:
            status = 200
            headers = {}
            async def __aenter__(self):
                return self
            async def __aexit__(self, *args):
                return False
            async def read(self):
                data = '{"scale":[{"tableName":"synthetic_table","userIds":[9007199254740993]}]}'
                return json.dumps({"code": 101, "data": self.api._encrypt(data)}).encode()

        response = Response()
        response.api = self.api
        calls = []
        class Session:
            def post(self, url, **kwargs):
                calls.append((url, kwargs))
                return response

        self.api._token = "synthetic-token"
        self.api._user_id = "9007199254740995"
        self.api._get_session = AsyncMock(return_value=Session())
        asyncio.run(self.api._get_device_info())
        self.assertEqual(calls, [(api_module.API_BASE + "/renpho-aggregation/device/count", {
            "json": {"encryptData": "ZtDk/16Qik2UaElz2ZzmEg=="},
            "headers": {"Content-Type": "application/json", "token": "synthetic-token",
                        "userId": "9007199254740995", "appVersion": "7.0.0", "platform": "android"}
        })])
        self.assertEqual(self.api._table_name, "synthetic_table")
        self.assertEqual(self.api._scale_user_id, "9007199254740993")


if __name__ == "__main__":
    unittest.main()
