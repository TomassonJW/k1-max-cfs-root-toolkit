"""Le catalogue des bobines vides livré avec le gestionnaire (document 102, lot B).

tares.json vient de SpoolmanDB, sous licence MIT copiée à côté. Le générateur
ne garde que le 1,75 mm et les poids qui donnent une tare, regroupe par
fabricant, net, tare et matière de la bobine, et ne recopie ni couleur ni
adresse. Les deux bobines que Thomas utilise s'y retrouvent.
"""

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "packages" / "k1-control-v1" / "spool-manager-v1"
WWW = ROOT / "packages" / "k1-control-v1" / "spool-choice-gate-v1" / "www" / "bobines"


def load(name):
    spec = importlib.util.spec_from_file_location(name, PACKAGE / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


build_tares = load("build_tares")
model = load("kctrl_spools_model")
CATALOGUE = json.loads((WWW / "tares.json").read_text(encoding="utf-8"))


def entry(key):
    found = [item for item in CATALOGUE["entries"] if item["key"] == key]
    assert len(found) == 1, key
    return found[0]


def test_the_catalogue_names_its_source_commit_and_licence():
    assert CATALOGUE["format"] == "kctrl_spools.tares"
    assert CATALOGUE["source"] == "SpoolmanDB"
    assert len(CATALOGUE["commit"]) == 40 and int(CATALOGUE["commit"], 16) >= 0
    assert CATALOGUE["license"] == "MIT"
    assert CATALOGUE["copyright"] == "Copyright (c) 2024 Donkie"
    licence = (WWW / "LICENSE-SpoolmanDB.txt").read_text(encoding="utf-8")
    assert "MIT License" in licence and "Copyright (c) 2024 Donkie" in licence
    assert "THE SOFTWARE IS PROVIDED \"AS IS\"" in licence


def test_thomas_s_geeetech_and_esun_spools_are_found():
    geeetech = entry("GEEETECH|1000|180|plastique")
    assert (geeetech["net_g"], geeetech["tare_g"], geeetech["spool_material"]) == (1000, 180, "plastique")
    assert {"PLA", "PETG"} <= {line["material"] for line in geeetech["lines"]}
    esun = entry("eSun|1000|170|carton")
    assert (esun["net_g"], esun["tare_g"], esun["spool_material"]) == (1000, 170, "carton")
    assert any(line["material"] == "PLA" for line in esun["lines"])


def test_every_entry_is_usable_by_the_model_as_it_is():
    allowed = set(model.SPOOL_MATERIALS)
    for item in CATALOGUE["entries"]:
        assert item["key"] == "%s|%g|%g|%s" % (item["manufacturer"], item["net_g"], item["tare_g"],
                                              item["spool_material"])
        assert item["manufacturer"].strip() == item["manufacturer"] != ""
        # The model's own bounds for an empty spool and a full spool's net.
        assert 0 < item["tare_g"] <= 2000 and 0 < item["net_g"] <= 10000
        assert item["spool_material"] in allowed
        assert item["lines"]
        for line in item["lines"]:
            assert line["name"] and line["material"]
            assert 0.5 <= line["density"] <= 8.0, (item["key"], line)
        assert len(item["key"]) <= 160


def test_keys_are_unique_and_in_a_stable_order():
    keys = [item["key"] for item in CATALOGUE["entries"]]
    assert len(keys) == len(set(keys))
    order = [(item["manufacturer"].lower(), item["net_g"], item["tare_g"], item["spool_material"])
             for item in CATALOGUE["entries"]]
    assert order == sorted(order)


def test_the_file_carries_no_address_and_no_colour():
    text = (WWW / "tares.json").read_text(encoding="utf-8")
    assert "http" not in text and "://" not in text
    assert "color_hex" not in text and "colors" not in text
    assert text.endswith("\n") and "\r" not in text


def test_spool_materials_match_between_the_generator_and_the_model():
    assert set(build_tares.SPOOL_MATERIALS.values()) | {"inconnue"} == set(model.SPOOL_MATERIALS)


@pytest.mark.parametrize("name, material, expected", [
    ("{color_name}", "PLA", "PLA"),
    ("Matte {color_name}", "PLA", "Matte PLA"),
    ("PLA+ {color_name}", "PLA", "PLA+"),
    ("  Silk  -  ", "PLA", "Silk PLA"),
    ("High  Speed\tPLA", "PLA", "High Speed PLA"),
    ("", "", ""),
])
def test_line_names_drop_the_colour_placeholder_and_keep_the_material(name, material, expected):
    assert build_tares.line_name(name, material) == expected


def write(path, document):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document), encoding="utf-8")


def test_the_generator_keeps_1_75_mm_lines_with_a_tare_and_groups_them(tmp_path):
    write(tmp_path / "filaments" / "acme.json", {"manufacturer": "Acme", "filaments": [
        {"name": "Matte {color_name}", "material": "PLA", "density": 1.24, "diameters": [1.75, 2.85],
         "weights": [{"weight": 1000, "spool_weight": 200, "spool_type": "plastic"},
                     {"weight": 250, "spool_weight": None}]},
        {"name": "Basic {color_name}", "material": "PLA", "density": 1.24, "diameters": [1.75],
         "weights": [{"weight": 1000, "spool_weight": 200, "spool_type": "plastic"}]},
        {"name": "Thick", "material": "PETG", "density": 1.27, "diameters": [2.85],
         "weights": [{"weight": 1000, "spool_weight": 200, "spool_type": "plastic"}]},
        {"name": "Card", "material": "PETG", "density": 1.27,
         "weights": [{"weight": 1000, "spool_weight": 150, "spool_type": "cardboard"},
                     {"weight": 750, "spool_weight": 120, "spool_type": "foam"},
                     {"weight": True, "spool_weight": 120}]},
    ]})
    write(tmp_path / "filaments" / "nobody.json", {"manufacturer": " ", "filaments": [
        {"name": "x", "material": "PLA", "density": 1.2,
         "weights": [{"weight": 1000, "spool_weight": 100}]}]})
    built = build_tares.build(str(tmp_path), "a" * 40)
    keys = [item["key"] for item in built["entries"]]
    assert keys == ["Acme|750|120|inconnue", "Acme|1000|150|carton", "Acme|1000|200|plastique"]
    plastic = built["entries"][2]
    assert [line["name"] for line in plastic["lines"]] == ["Basic PLA", "Matte PLA"]
    assert all(line["density"] == 1.24 for line in plastic["lines"])
    assert built["entries"][1]["lines"] == [{"name": "Card PETG", "material": "PETG", "density": 1.27}]
    assert built["commit"] == "a" * 40 and built["license"] == "MIT"


def test_the_generator_refuses_a_bad_commit_and_writes_lf_with_a_final_newline(tmp_path, capsys):
    write(tmp_path / "filaments" / "acme.json", {"manufacturer": "Acme", "filaments": [
        {"name": "PLA", "material": "PLA", "density": 1.24,
         "weights": [{"weight": 1000, "spool_weight": 200, "spool_type": "plastic"}]}]})
    output = tmp_path / "tares.json"
    assert build_tares.main([str(tmp_path), "main", str(output)]) == 2
    assert build_tares.main([str(tmp_path)]) == 2
    assert not output.exists()
    assert build_tares.main([str(tmp_path), "b" * 40, str(output)]) == 0
    raw = output.read_bytes()
    assert b"\r" not in raw and raw.endswith(b"}\n")
    assert json.loads(raw.decode("utf-8"))["entries"][0]["key"] == "Acme|1000|200|plastique"
    assert "1 entrées, 1 gammes" in capsys.readouterr().out
