"""Prepare an inspectable K1-CONTROL-V1 bundle on the local workstation only.

The script has no SSH code and no printer destination option. It verifies the
pinned third-party artefacts, copies them into a local staging directory, adds
the original project files, and writes a complete SHA-256 inventory.
"""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import shutil
import sys
from typing import Any
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "packages" / "k1-control-v1" / "foundation-manifest.json"


class PreparationError(RuntimeError):
    pass


def file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_artifact(path: Path, component: dict[str, Any]) -> None:
    if not path.is_file():
        raise PreparationError(f"missing artefact for {component['id']}: {path}")
    size = path.stat().st_size
    if size != int(component["size_bytes"]):
        raise PreparationError(
            f"size mismatch for {component['id']}: expected {component['size_bytes']}, got {size}"
        )
    actual = file_sha256(path)
    expected = str(component["sha256"]).lower()
    if actual != expected:
        raise PreparationError(
            f"SHA-256 mismatch for {component['id']}: expected {expected}, got {actual}"
        )


def download_pinned_asset(component: dict[str, Any], destination: Path) -> Path:
    url = component.get("release_asset")
    if not url:
        raise PreparationError(f"component {component['id']} has no pinned release asset")
    destination.parent.mkdir(parents=True, exist_ok=True)
    request = Request(str(url), headers={"User-Agent": "k1-control-offline-preparer/1"})
    with urlopen(request, timeout=60) as response, destination.open("wb") as stream:
        shutil.copyfileobj(response, stream)
    verify_artifact(destination, component)
    return destination


def parse_artifacts(values: list[str]) -> dict[str, Path]:
    result = {}
    for value in values:
        if "=" not in value:
            raise PreparationError("--artifact must use COMPONENT_ID=PATH")
        component_id, raw_path = value.split("=", 1)
        result[component_id] = Path(raw_path).resolve()
    return result


def ensure_local_output(output: Path) -> Path:
    resolved = output.resolve()
    workspace = ROOT.resolve()
    try:
        resolved.relative_to(workspace)
    except ValueError as exc:
        raise PreparationError("output must stay inside the local workspace") from exc
    if resolved == workspace:
        raise PreparationError("workspace root cannot be used as bundle output")
    return resolved


def prepare_bundle(manifest_path: Path, artifacts: dict[str, Path], output: Path) -> dict[str, Any]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("printer_mutation_authorized") is not False:
        raise PreparationError("manifest must explicitly forbid printer mutation")
    output = ensure_local_output(output)
    if output.exists() and any(output.iterdir()):
        raise PreparationError(f"output directory is not empty: {output}")
    output.mkdir(parents=True, exist_ok=True)

    binary_components = [component for component in manifest["components"] if component.get("sha256")]
    for component in binary_components:
        component_id = component["id"]
        source = artifacts.get(component_id)
        if source is None:
            raise PreparationError(f"no local artefact supplied for {component_id}")
        verify_artifact(source, component)
        suffix = ".zip" if component_id == "mainsail" else ".tar.gz"
        destination = output / "artifacts" / f"{component_id}{suffix}"
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)

    shutil.copy2(manifest_path, output / "foundation-manifest.json")
    shutil.copytree(manifest_path.parent / "config", output / "config", dirs_exist_ok=True)
    shutil.copytree(manifest_path.parent / "services", output / "services", dirs_exist_ok=True)
    plan = {
        "status": "offline_plan_only",
        "printer_mutation_authorized": False,
        "release_root": manifest["future_paths"]["release_root"],
        "operations": [
            "verify every archive against foundation-manifest.json",
            "extract moonraker-mips-bundle under the new versioned release root",
            "extract nginx-mips-bundle under the new versioned release root",
            "extract mainsail under www/mainsail",
            "copy config and services from this bundle",
            "create the current link only after all local and remote hashes match",
            "install only the two new service files after a named G4 GO",
        ],
        "forbidden_future_writes": manifest["forbidden_future_writes"],
    }
    (output / "release-plan.json").write_text(
        json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    inventory = {}
    for path in sorted(output.rglob("*")):
        if path.is_file() and path.name != "checksums.sha256":
            inventory[path.relative_to(output).as_posix()] = file_sha256(path)
    checksum_text = "".join(f"{digest}  {path}\n" for path, digest in inventory.items())
    (output / "checksums.sha256").write_text(checksum_text, encoding="utf-8", newline="\n")
    return {"output": str(output), "files": len(inventory), "status": "OK"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--artifact", action="append", default=[], metavar="ID=PATH")
    parser.add_argument("--download-mainsail", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
        artifacts = parse_artifacts(args.artifact)
        if args.download_mainsail:
            mainsail = next(item for item in manifest["components"] if item["id"] == "mainsail")
            artifacts["mainsail"] = download_pinned_asset(mainsail, args.download_mainsail.resolve())
        if args.output is None:
            if args.download_mainsail:
                print(json.dumps({"status": "OK", "mainsail": str(artifacts["mainsail"])}))
                return 0
            raise PreparationError("--output is required unless only --download-mainsail is used")
        result = prepare_bundle(args.manifest.resolve(), artifacts, args.output)
    except (OSError, ValueError, KeyError, PreparationError) as exc:
        print(f"KO: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
