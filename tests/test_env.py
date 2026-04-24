import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

SRC_PATH = Path(__file__).resolve().parents[1] / "src"

if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from sonarqube_quality_assistant.utils.env import (
    get_optional_env,
    get_required_env,
    load_env,
)

class EnvTests(unittest.TestCase):
    @patch("sonarqube_quality_assistant.utils.env.load_dotenv")
    def test_load_env_calls_dotenv_loader(self, mock_load_dotenv):
        load_env()

        mock_load_dotenv.assert_called_once_with()

    def test_get_required_env_returns_value_when_present(self):
        with patch.dict(os.environ, {"SONARQUBE_TOKEN": "secret"}, clear=True):
            self.assertEqual(get_required_env("SONARQUBE_TOKEN"), "secret")

    def test_get_required_env_raises_when_missing_or_empty(self):
        with patch.dict(os.environ, {"SONARQUBE_TOKEN": ""}, clear=True):
            with self.assertRaisesRegex(
                RuntimeError, "Missing required environment variable: SONARQUBE_TOKEN"
            ):
                get_required_env("SONARQUBE_TOKEN")

    def test_get_optional_env_uses_default_when_missing(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(
                get_optional_env("SONARQUBE_BASE_URL", "https://default"),
                "https://default",
            )
