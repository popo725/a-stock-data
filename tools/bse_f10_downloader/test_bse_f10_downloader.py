# -*- coding: utf-8 -*-
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import bse_f10_api as API  # noqa: E402
import bse_f10_downloader as MODULE  # noqa: E402


class BseF10DownloaderTests(unittest.TestCase):
    def test_extract_json_array(self):
        payload = 'callback([{"totalPages":1,"content":[]}]);'
        result = API.extract_json_array(payload)
        self.assertEqual(result[0]["totalPages"], 1)

    def test_normalize_list_row(self):
        row = [None] * 41
        row[0] = "2021-11-15"
        row[11] = 100
        row[17] = "软件"
        row[29] = "北京"
        row[35] = "某券商"
        row[36] = 200
        row[38] = "920002"
        row[40] = "万达轴承"
        result = API.normalize_bse_row(row)
        self.assertEqual(result["security_code"], "920002")
        self.assertEqual(result["security_name"], "万达轴承")
        self.assertEqual(result["total_shares"], 200)

    def test_quarter_ends(self):
        result = list(API.quarter_ends(2024, date(2024, 8, 1)))
        self.assertEqual(result, ["20240331", "20240630"])

    def test_jsonl_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sample.jsonl"
            MODULE.write_jsonl(path, [{"a": 1}, {"a": 2}])
            frame = MODULE.read_jsonl_files([path])
            self.assertEqual(frame["a"].tolist(), [1, 2])


if __name__ == "__main__":
    unittest.main()
