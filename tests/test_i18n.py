from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.i18n import LANG_EN, LANG_ZH, get_language, load_language, set_language, tr


class I18nTests(unittest.TestCase):
    def setUp(self) -> None:
        self.previous_language = get_language()

    def tearDown(self) -> None:
        set_language(self.previous_language, persist=False)

    def test_language_switch_changes_core_copy(self) -> None:
        set_language(LANG_ZH, persist=False)
        self.assertEqual(tr("action.view_log"), "查看日志")
        set_language(LANG_EN, persist=False)
        self.assertEqual(tr("action.view_log"), "View Log")
        self.assertEqual(tr("action.start", scale=8), "Start 8× Upscale")

    def test_language_preference_is_saved_outside_install_directory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "settings.json"
            with patch.dict(os.environ, {"SEEDVR2_SETTINGS_PATH": str(target)}, clear=False):
                set_language(LANG_EN, persist=True)
                self.assertEqual(json.loads(target.read_text(encoding="utf-8"))["language"], LANG_EN)
                self.assertEqual(load_language(), LANG_EN)

    def test_corrupt_or_unknown_setting_falls_back_to_system_language(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "settings.json"
            target.write_text("{broken", encoding="utf-8")
            with (
                patch.dict(os.environ, {"SEEDVR2_SETTINGS_PATH": str(target)}, clear=False),
                patch("app.i18n.system_language", return_value=LANG_ZH),
            ):
                self.assertEqual(load_language(), LANG_ZH)


if __name__ == "__main__":
    unittest.main()
