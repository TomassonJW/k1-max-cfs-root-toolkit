import importlib.util
import json
import pathlib
import tempfile
import unittest
from unittest import mock


ROOT = pathlib.Path(__file__).resolve().parents[1]
MODULE_PATH = (
    ROOT
    / "packages"
    / "k1-control-v1"
    / "z-mesh-runtime-v1"
    / "k1_control_store.py"
)
SPEC = importlib.util.spec_from_file_location("k1_control_store_candidate", MODULE_PATH)
store = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(store)


def record(z=0.125, plate=1, accepted_at=1):
    return [1, 1, z, plate, 60, 1, 1, 1234, accepted_at, 0, 0.0, 0, 0, 0, 0, 0, 0]


class K1ControlAtomicStoreTests(unittest.TestCase):
    def test_round_trip_has_checksum_and_restrictive_record_validation(self):
        payload = store.encode_record(record())
        envelope = json.loads(payload)
        self.assertEqual(len(envelope["sha256"]), 64)
        self.assertEqual(store.decode_record(payload), record())
        with self.assertRaises(store.StateStoreError):
            store.encode_record([1, 1, 9.0])

    def test_second_commit_keeps_a_valid_file_level_previous_copy(self):
        with tempfile.TemporaryDirectory() as directory:
            path = str(pathlib.Path(directory) / "state.json")
            first = record(z=0.1, accepted_at=10)
            second = record(z=0.2, accepted_at=20)
            store.persist_state(path, first)
            store.persist_state(path, second)
            self.assertEqual(store.read_file(path)[0], second)
            self.assertEqual(store.read_file(path + ".previous")[0], first)

    def test_failed_final_replace_leaves_the_old_current_record_readable(self):
        with tempfile.TemporaryDirectory() as directory:
            path = str(pathlib.Path(directory) / "state.json")
            first = record(z=0.1, accepted_at=10)
            second = record(z=0.2, accepted_at=20)
            store.persist_state(path, first)
            real_replace = store.os.replace

            def fail_current_replace(source, destination):
                if destination == path:
                    raise OSError("injected replacement failure")
                return real_replace(source, destination)

            with mock.patch.object(store.os, "replace", side_effect=fail_current_replace):
                with self.assertRaises(OSError):
                    store.persist_state(path, second)
            self.assertEqual(store.read_file(path)[0], first)

    def test_corrupt_current_state_blocks_instead_of_silently_loading_previous(self):
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "state.json"
            store.persist_state(str(path), record(z=0.1, accepted_at=10))
            store.persist_state(str(path), record(z=0.2, accepted_at=20))
            path.write_bytes(b"corrupt")
            with self.assertLogs(level="ERROR"):
                loaded, integrity, recovery_available = store.load_state(str(path))
            self.assertEqual(loaded, store.EMPTY_RECORD)
            self.assertEqual(integrity, "invalid")
            self.assertTrue(recovery_available)

    def test_first_boot_is_empty_and_fail_closed_without_creating_a_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "state.json"
            loaded, integrity, recovery_available = store.load_state(str(path))
            self.assertEqual(loaded, store.EMPTY_RECORD)
            self.assertEqual(integrity, "empty")
            self.assertFalse(recovery_available)
            self.assertFalse(path.exists())


if __name__ == "__main__":
    unittest.main()
