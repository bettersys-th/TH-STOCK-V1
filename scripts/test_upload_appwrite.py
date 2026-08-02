import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))
from cloud_export import build_cloud_export
from upload_appwrite import load_upload_plan, object_id, remote_manifest, upload


class FakeStorage:
    def __init__(self):
        self.files = {}

    def exists(self, file_id):
        return file_id in self.files

    def upload_path(self, file_id, path):
        self.files[file_id] = path.read_bytes()

    def upload_bytes(self, file_id, content, filename):
        self.files[file_id] = content


class UploadAppwriteTests(unittest.TestCase):
    def make_export(self, root):
        data = Path(root) / "data"
        data.mkdir()
        prices = {"AAA": {"d": [20260102], "c": [10.0], "v": [100]}}
        build_cloud_export(prices, data)
        return data / "cloud_market"

    def test_dry_run_has_no_remote_dependency(self):
        with tempfile.TemporaryDirectory() as temp:
            report = upload(self.make_export(temp))
            self.assertEqual(report["objects"], 1)
            self.assertEqual(report["uploaded"], 0)

    def test_apply_is_immutable_and_idempotent(self):
        with tempfile.TemporaryDirectory() as temp:
            export = self.make_export(temp)
            storage = FakeStorage()
            first = upload(export, storage=storage, apply=True)
            second = upload(export, storage=storage, apply=True)
            self.assertEqual(first["uploaded"], 2)  # ticker plus manifest
            self.assertEqual(second["uploaded"], 0)
            self.assertEqual(second["skipped"], 2)
            self.assertEqual(len(first["manifestFileId"]), 34)

    def test_remote_manifest_contains_content_addressed_file_ids(self):
        with tempfile.TemporaryDirectory() as temp:
            export = self.make_export(temp)
            manifest, objects = load_upload_plan(export)
            remote = json.loads(remote_manifest(manifest, objects))
            expected = object_id(manifest["tickers"]["AAA"]["sha256"])
            self.assertEqual(remote["tickers"]["AAA"]["fileId"], expected)


if __name__ == "__main__":
    unittest.main()
