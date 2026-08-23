import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGES = ROOT / "packages" / "k1-control-v1"


def _load(name):
    path = PACKAGES / name / "deployment-manifest.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _map(items):
    return {item["destination"]: item["sha256"] for item in items}


class CalibrationUiDeploymentChainTests(unittest.TestCase):
    def setUp(self):
        self.bedmesh = _load("calibration-ui-prtouch-bed-mesh-v2")
        self.matrix = _load("calibration-ui-matrix-v1")
        self.retry = _load("calibration-ui-retry-safety-v1")
        self.presets = _load("calibration-ui-prtouch-presets-v1")
        self.composite = _load("composite-subgrid-v1")

    def test_every_payload_hash_matches_its_local_file(self):
        package_names = (
            "calibration-ui-prtouch-bed-mesh-v2",
            "calibration-ui-matrix-v1",
            "calibration-ui-prtouch-presets-v1",
            "composite-subgrid-v1",
        )
        for package_name in package_names:
            manifest = _load(package_name)
            package = PACKAGES / package_name
            for item in manifest["files"]:
                source = package / item["source"]
                self.assertEqual(
                    hashlib.sha256(source.read_bytes()).hexdigest(),
                    item["sha256"],
                    "%s:%s" % (package_name, item["source"]),
                )
        retry_source = PACKAGES / "calibration-ui-retry-safety-v1" / self.retry["file"]["source"]
        self.assertEqual(
            hashlib.sha256(retry_source.read_bytes()).hexdigest(),
            self.retry["file"]["sha256"],
        )

    def test_four_safe_steps_form_one_exact_remote_hash_chain(self):
        remote = {}
        remote.update(_map(self.bedmesh["unchanged"]["files"]))
        remote["/usr/data/printer_data/config/printer.cfg"] = self.bedmesh[
            "baseline"
        ]["printer_cfg_sha256"]
        component_path = self.bedmesh["files"][0]["destination"]
        remote[component_path] = self.bedmesh["baseline"]["component_sha256"]
        remote.update(_map(self.matrix["baseline"]["files"]))

        self.assertEqual(
            remote[component_path], self.bedmesh["baseline"]["component_sha256"]
        )
        for path, expected in _map(self.bedmesh["unchanged"]["files"]).items():
            self.assertEqual(remote[path], expected)
        remote.update(_map(self.bedmesh["files"]))

        for path, expected in _map(self.matrix["baseline"]["files"]).items():
            self.assertEqual(remote[path], expected)
        for path, expected in _map(self.matrix["unchanged"]["files"]).items():
            self.assertEqual(remote[path], expected)
        remote.update(_map(self.matrix["files"]))

        self.assertEqual(
            remote[self.retry["baseline"]["destination"]],
            self.retry["baseline"]["sha256"],
        )
        for path, expected in _map(self.retry["unchanged"]["files"]).items():
            self.assertEqual(remote[path], expected)
        remote[self.retry["file"]["destination"]] = self.retry["file"]["sha256"]

        preset_baseline = {
            self.presets["files"][0]["destination"]: self.presets["baseline"]["index_html_sha256"],
            self.presets["files"][1]["destination"]: self.presets["baseline"]["app_js_sha256"],
        }
        for path, expected in preset_baseline.items():
            self.assertEqual(remote[path], expected)
        for path, expected in _map(self.presets["unchanged"]["files"]).items():
            self.assertEqual(remote[path], expected)

        preset_output = _map(self.presets["files"])
        self.assertEqual(preset_output, preset_baseline)
        remote.update(preset_output)

        for path, expected in _map(self.composite["unchanged"]["files"]).items():
            self.assertEqual(remote[path], expected)
        config_path = self.composite["files"][0]["destination"]
        self.assertEqual(
            remote[config_path], self.composite["baseline"]["moonraker_conf_sha256"]
        )

    def test_presets_is_a_proven_noop_after_matrix_and_retry(self):
        output = _map(self.presets["files"])
        self.assertEqual(
            output[self.presets["files"][0]["destination"]],
            self.presets["baseline"]["index_html_sha256"],
        )
        self.assertEqual(
            output[self.presets["files"][1]["destination"]],
            self.presets["baseline"]["app_js_sha256"],
        )


if __name__ == "__main__":
    unittest.main()
