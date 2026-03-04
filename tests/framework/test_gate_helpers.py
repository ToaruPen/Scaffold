from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from framework.scripts.lib import gate_helpers


class GateHelpersTests(unittest.TestCase):
    def test_error_dict_builds_expected_shape(self) -> None:
        result = gate_helpers.error_dict("E_INPUT_INVALID", "bad input", "vcs")
        self.assertEqual(result["code"], "E_INPUT_INVALID")
        self.assertEqual(result["message"], "bad input")
        self.assertEqual(result["retryable"], False)
        self.assertEqual(result["provider"], "vcs")

    def test_read_json_returns_dict(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            input_path = Path(tmp) / "input.json"
            input_path.write_text(json.dumps({"k": "v"}), encoding="utf-8")
            payload = gate_helpers.read_json(input_path)
            self.assertEqual(payload, {"k": "v"})

    def test_read_json_rejects_non_object(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            input_path = Path(tmp) / "input.json"
            input_path.write_text(json.dumps(["not", "object"]), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "input must be a JSON object"):
                gate_helpers.read_json(input_path)

    def test_require_text_and_optional_text(self) -> None:
        payload = {"name": "  value  ", "none": None}
        self.assertEqual(gate_helpers.require_text(payload, "name"), "value")
        self.assertEqual(gate_helpers.optional_text(payload, "name"), "value")
        self.assertIsNone(gate_helpers.optional_text(payload, "none"))
        with self.assertRaisesRegex(ValueError, "missing or invalid string"):
            gate_helpers.require_text(payload, "missing")

    def test_require_object(self) -> None:
        payload = {"child": {"k": "v"}}
        self.assertEqual(gate_helpers.require_object(payload, "child"), {"k": "v"})
        with self.assertRaisesRegex(ValueError, "missing or invalid object"):
            gate_helpers.require_object(payload, "missing")

    def test_require_list_of_texts(self) -> None:
        payload = {"values": ["a", " b ", "c"]}
        self.assertEqual(gate_helpers.require_list_of_texts(payload, "values"), ["a", "b", "c"])
        with self.assertRaisesRegex(ValueError, "missing or invalid non-empty list"):
            gate_helpers.require_list_of_texts(payload, "missing")

    def test_write_result_prints_and_writes_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out_path = Path(tmp) / "out.json"
            buffer = io.StringIO()
            with redirect_stdout(buffer):
                gate_helpers.write_result({"status": "pass"}, out_path)

            stdout_payload = json.loads(buffer.getvalue())
            file_payload = json.loads(out_path.read_text(encoding="utf-8"))
            self.assertEqual(stdout_payload["status"], "pass")
            self.assertEqual(file_payload["status"], "pass")

    def test_parse_gate_args(self) -> None:
        argv_backup = sys.argv
        try:
            sys.argv = ["prog", "--input", "in.json", "--output", "out.json"]
            args = gate_helpers.parse_gate_args("desc")
        finally:
            sys.argv = argv_backup

        self.assertEqual(args.input, "in.json")
        self.assertEqual(args.output, "out.json")


if __name__ == "__main__":
    unittest.main()
