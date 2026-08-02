import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(__file__))
from cleanup_appwrite import cleanup


class FakeRemote:
    def __init__(self, files, manifests):
        self.files = files
        self.manifests = manifests
        self.deleted = []

    def list_files(self):
        return list(self.files)

    def download(self, file_id):
        return json.dumps(self.manifests[file_id]).encode()

    def delete(self, file_id):
        self.deleted.append(file_id)


class CleanupTests(unittest.TestCase):
    def test_keeps_newest_complete_manifest_and_unknown_files(self):
        files = [
            {"id": "o_live", "name": "AAA.json.gz", "createdAt": "2026-08-02T02:00:00Z", "bytes": 10},
            {"id": "o_old", "name": "AAA.json.gz", "createdAt": "2026-08-02T01:00:00Z", "bytes": 9},
            {"id": "o_manifest_old", "name": "manifest.json", "createdAt": "2026-08-02T01:00:00Z", "bytes": 5},
            {"id": "o_manifest_new", "name": "manifest.json", "createdAt": "2026-08-02T03:00:00Z", "bytes": 5},
            {"id": "manual", "name": "notes.txt", "createdAt": "2026-08-02T00:00:00Z", "bytes": 4},
        ]
        manifests = {"o_manifest_new": {"schemaVersion": 1, "tickers": {"AAA": {"fileId": "o_live"}}}}
        remote = FakeRemote(files, manifests)
        report = cleanup(remote, apply=True)
        self.assertEqual(set(remote.deleted), {"o_old", "o_manifest_old"})
        self.assertEqual(report["deleted"], 2)

    def test_refuses_when_manifest_reference_is_missing(self):
        files = [{"id": "o_manifest", "name": "manifest.json", "createdAt": "2026-08-02T03:00:00Z", "bytes": 5}]
        manifests = {"o_manifest": {"schemaVersion": 1, "tickers": {"AAA": {"fileId": "o_missing"}}}}
        with self.assertRaisesRegex(RuntimeError, "missing objects"):
            cleanup(FakeRemote(files, manifests))

    def test_accepts_sdk_json_dict_download(self):
        files = [
            {"id": "o_live", "name": "AAA.json.gz", "createdAt": "2026-08-02T02:00:00Z", "bytes": 10},
            {"id": "o_manifest", "name": "manifest.json", "createdAt": "2026-08-02T03:00:00Z", "bytes": 5},
        ]

        class DictRemote(FakeRemote):
            def download(self, file_id):
                return self.manifests[file_id]

        manifest = {"schemaVersion": 1, "tickers": {"AAA": {"fileId": "o_live"}}}
        report = cleanup(DictRemote(files, {"o_manifest": manifest}))
        self.assertEqual(report["keep"], 2)
        self.assertEqual(report["orphans"], 0)


if __name__ == "__main__":
    unittest.main()
