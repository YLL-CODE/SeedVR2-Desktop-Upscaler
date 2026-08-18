from __future__ import annotations

import contextlib
import io
import json
import unittest
from unittest.mock import patch

from app import worker


class ProtocolTests(unittest.TestCase):
    def test_emit_ignores_global_stdout_redirect(self) -> None:
        protocol = io.StringIO()
        redirected = io.StringIO()
        with patch.object(worker, "PROTOCOL_OUTPUT", protocol):
            with contextlib.redirect_stdout(redirected):
                worker.emit("cancel_requested", message="stop")
        self.assertEqual(redirected.getvalue(), "")
        self.assertEqual(json.loads(protocol.getvalue())["event"], "cancel_requested")


if __name__ == "__main__":
    unittest.main()
