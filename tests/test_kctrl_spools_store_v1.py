"""Le socle de stockage des bobines (document 102, lot A).

Une coupure à n'importe quelle étape d'écriture laisse l'ancienne
bibliothèque ou la nouvelle, jamais un mélange ; un fichier abîmé cède la
place à la copie intacte la plus récente ; sans copie intacte, rien n'est
effacé ; le point de reprise garde sa taille ; le journal reste borné et une
ligne coupée n'emporte pas la suivante.
"""

import importlib.util
import json
import os
from pathlib import Path

import pytest

PACKAGE = Path(__file__).resolve().parents[1] / "packages" / "k1-control-v1" / "spool-manager-v1"


def load(name):
    spec = importlib.util.spec_from_file_location(name, PACKAGE / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


store = load("kctrl_spools_store")


class Cut(Exception):
    """The power goes off: nothing after this step runs."""


class Store(store.SpoolStore):
    def __init__(self, directory, cut_at=None, **options):
        options.setdefault("clock", lambda: 1_790_000_000)
        super().__init__(str(directory), **options)
        self.cut_at = cut_at
        self.steps = []

    def _step(self, name):
        self.steps.append(name)
        if name == self.cut_at:
            raise Cut(name)


def library(n):
    return {"schema": 1, "spools": {"B%03d" % i: {"note": "bobine é %d" % i} for i in range(n)}}


def files(directory):
    return sorted(name for name in os.listdir(str(directory)))


def test_a_fresh_directory_loads_nothing_then_counts_revisions(tmp_path):
    folder = tmp_path / "spools"
    value, report = Store(folder).load_library()
    assert value is None and report["fresh"] and not report["damaged"]
    first = Store(folder)
    assert first.save_library(library(1)) == 1
    assert first.save_library(library(2)) == 2
    value, report = Store(folder).load_library()
    assert value == library(2)
    assert report["source"] == "library.json" and report["revision"] == 2
    assert not report["fallback"]


def test_four_revisions_are_kept_and_never_more(tmp_path):
    keeper = Store(tmp_path)
    for n in range(1, 8):
        keeper.save_library(library(n))
    assert files(tmp_path) == ["library.json", "library.json.1", "library.json.2",
                               "library.json.3"]
    for name, n in (("library.json", 7), ("library.json.1", 6), ("library.json.2", 5),
                    ("library.json.3", 4)):
        header, value, reason = store.parse((tmp_path / name).read_bytes(), store.LIBRARY_FORMAT)
        assert reason == "" and value == library(n) and header["revision"] == n


def all_save_steps(tmp_path):
    probe = Store(tmp_path / "probe")
    for n in range(1, 5):
        probe.save_library(library(n))
    probe.steps.clear()
    probe.save_library(library(5))
    return list(probe.steps)


def test_a_cut_at_any_step_of_a_save_leaves_the_old_or_the_new_library(tmp_path):
    steps = all_save_steps(tmp_path)
    assert steps == ["library:write", "library:half", "library:rotate-3", "library:rotate-2",
                     "library:rotate-1", "library:replace", "library:directory"]
    for step in steps:
        folder = tmp_path / step.replace(":", "-")
        keeper = Store(folder)
        for n in range(1, 5):
            keeper.save_library(library(n))
        cutting = Store(folder, cut_at=step)
        with pytest.raises(Cut):
            cutting.save_library(library(5))
        after = Store(folder)
        value, report = after.load_library()
        assert value in (library(4), library(5)), step
        assert not report["damaged"], (step, report)
        # Up to the last rename the old library is what comes back.
        if step != "library:directory":
            assert value == library(4), step
        assert "library.json.tmp" not in files(folder)
        # The next save after the cut works and wins.
        revision = after.save_library(library(6))
        value, report = Store(folder).load_library()
        assert value == library(6) and report["revision"] == revision


@pytest.mark.parametrize("damage", ["zeroed", "truncated", "flipped", "empty", "garbage"])
def test_a_damaged_library_falls_back_to_the_newest_intact_copy(tmp_path, damage):
    keeper = Store(tmp_path)
    for n in range(1, 4):
        keeper.save_library(library(n))
    path = tmp_path / "library.json"
    data = path.read_bytes()
    if damage == "zeroed":
        path.write_bytes(b"\0" * len(data))
    elif damage == "truncated":
        path.write_bytes(data[:len(data) - 7])
    elif damage == "flipped":
        middle = len(data) - 10
        path.write_bytes(data[:middle] + bytes([data[middle] ^ 0x01]) + data[middle + 1:])
    elif damage == "empty":
        path.write_bytes(b"")
    else:
        path.write_bytes(b"{not json at all\n")
    after = Store(tmp_path)
    value, report = after.load_library()
    assert value == library(2)
    assert report["source"] == "library.json.1" and report["fallback"]
    assert report["damaged"][0]["file"] == "library.json"
    # A later save goes above every revision still readable in a header,
    # and loads cleanly.
    revision = after.save_library(library(9))
    assert revision == (4 if damage in ("truncated", "flipped") else 3)
    value, report = Store(tmp_path).load_library()
    assert value == library(9) and not report["fallback"]


def test_no_intact_copy_puts_the_damaged_files_aside_and_starts_empty(tmp_path):
    keeper = Store(tmp_path)
    keeper.save_library(library(1))
    keeper.save_library(library(2))
    for name in ("library.json", "library.json.1"):
        (tmp_path / name).write_bytes(b"\0" * 64)
    after = Store(tmp_path)
    value, report = after.load_library()
    assert value is None and report["fresh"]
    folder = report["quarantined"]
    assert folder.startswith("quarantine-")
    assert sorted(os.listdir(str(tmp_path / folder))) == ["library.json", "library.json.1"]
    # Saving now never touches the files put aside.
    after.save_library(library(3))
    assert sorted(os.listdir(str(tmp_path / folder))) == ["library.json", "library.json.1"]
    assert Store(tmp_path).load_library()[0] == library(3)


def test_a_newer_schema_locks_the_store_and_nothing_is_rewritten(tmp_path):
    keeper = Store(tmp_path)
    keeper.save_library(library(1))
    body = store.encode(library(2))
    header = {"format": store.LIBRARY_FORMAT, "schema": 2, "revision": 2, "saved": 0,
              "bytes": len(body), "sha256": store.digest(body)}
    newer = store.encode(header) + b"\n" + body + b"\n"
    (tmp_path / "library.json").write_bytes(newer)
    after = Store(tmp_path)
    value, report = after.load_library()
    assert value is None and "plus récente" in report["locked"]
    with pytest.raises(store.StoreError, match="plus récente"):
        after.save_library(library(3))
    assert (tmp_path / "library.json").read_bytes() == newer


def test_the_highest_revision_wins_whatever_the_file(tmp_path):
    keeper = Store(tmp_path)
    for n in range(1, 4):
        keeper.save_library(library(n))
    # A copy moved by hand above the current one is still the newest.
    os.replace(str(tmp_path / "library.json"), str(tmp_path / "library.json.3"))
    value, report = Store(tmp_path).load_library()
    assert value == library(3) and report["source"] == "library.json.3"


def test_a_library_over_the_limit_is_refused_before_any_write(tmp_path):
    keeper = Store(tmp_path, max_library_bytes=200)
    keeper.save_library(library(1))
    with pytest.raises(store.StoreError, match="trop grande"):
        keeper.save_library(library(40))
    assert Store(tmp_path, max_library_bytes=200).load_library()[0] == library(1)


def test_not_a_number_is_refused(tmp_path):
    with pytest.raises(store.StoreError):
        Store(tmp_path).save_library({"weight": float("nan")})


def test_the_checkpoint_keeps_its_size_and_alternates_slots(tmp_path):
    keeper = Store(tmp_path)
    assert keeper.load_checkpoint()[0] is None
    for n in range(1, 6):
        assert keeper.save_checkpoint({"n": n, "totals": {"T1A": 12.5 * n}}) == n
        for name in store.CHECKPOINTS:
            if (tmp_path / name).exists():
                assert (tmp_path / name).stat().st_size == store.CHECKPOINT_BYTES
    state, report = Store(tmp_path).load_checkpoint()
    assert state == {"n": 5, "totals": {"T1A": 62.5}} and report["seq"] == 5
    # Odd numbers went to one slot, even ones to the other.
    _, a, _ = store.parse((tmp_path / "checkpoint.a").read_bytes(), store.CHECKPOINT_FORMAT)
    _, b, _ = store.parse((tmp_path / "checkpoint.b").read_bytes(), store.CHECKPOINT_FORMAT)
    assert {a["n"], b["n"]} == {4, 5}


@pytest.mark.parametrize("step", ["checkpoint:write", "checkpoint:half"])
def test_a_cut_while_writing_the_checkpoint_keeps_the_previous_one(tmp_path, step):
    keeper = Store(tmp_path)
    for n in range(1, 4):
        keeper.save_checkpoint({"n": n})
    with pytest.raises(Cut):
        Store(tmp_path, cut_at=step).save_checkpoint({"n": 99})
    after = Store(tmp_path)
    state, report = after.load_checkpoint()
    assert state == {"n": 3}
    # The torn slot is the one rewritten next; the intact one is never touched.
    intact = report["source"]
    before = (tmp_path / intact).read_bytes()
    after.save_checkpoint({"n": 4})
    assert (tmp_path / intact).read_bytes() == before
    assert Store(tmp_path).load_checkpoint()[0] == {"n": 4}


def test_a_zeroed_checkpoint_slot_is_ignored(tmp_path):
    keeper = Store(tmp_path)
    keeper.save_checkpoint({"n": 1})
    keeper.save_checkpoint({"n": 2})
    newest = Store(tmp_path).load_checkpoint()[1]["source"]
    (tmp_path / newest).write_bytes(b"\0" * store.CHECKPOINT_BYTES)
    state, report = Store(tmp_path).load_checkpoint()
    assert state == {"n": 1} and report["damaged"][0]["file"] == newest


def test_a_checkpoint_too_big_is_refused(tmp_path):
    with pytest.raises(store.StoreError, match="trop grand"):
        Store(tmp_path).save_checkpoint({"blob": "x" * 5000})
    assert not list(tmp_path.iterdir())


def test_clearing_the_checkpoint_removes_both_slots(tmp_path):
    keeper = Store(tmp_path)
    keeper.save_checkpoint({"n": 1})
    keeper.save_checkpoint({"n": 2})
    keeper.clear_checkpoint()
    assert not any((tmp_path / name).exists() for name in store.CHECKPOINTS)
    assert Store(tmp_path).load_checkpoint()[0] is None
    keeper.clear_checkpoint()
    assert keeper.save_checkpoint({"n": 3}) == 3


def test_the_journal_rotates_and_never_holds_more_than_two_limits(tmp_path):
    keeper = Store(tmp_path, journal_limit=2048)
    for n in range(200):
        keeper.append_journal({"n": n, "what": "retrait de la bobine B-%03d" % n})
        for name in ("journal.jsonl", "journal.1.jsonl"):
            if (tmp_path / name).exists():
                assert (tmp_path / name).stat().st_size <= 2048
    entries = keeper.read_journal(limit=1000)
    numbers = [entry["n"] for entry in entries]
    assert numbers[0] == 199
    assert numbers == sorted(numbers, reverse=True)
    assert len(numbers) == len(set(numbers)) < 200
    assert [entry["n"] for entry in keeper.read_journal(limit=3)] == [199, 198, 197]


def test_a_torn_journal_line_is_skipped_and_does_not_swallow_the_next(tmp_path):
    keeper = Store(tmp_path)
    keeper.append_journal({"n": 1})
    with pytest.raises(Cut):
        Store(tmp_path, cut_at="journal:half").append_journal({"n": 2, "pad": "x" * 40})
    raw = (tmp_path / "journal.jsonl").read_bytes()
    assert not raw.endswith(b"\n")
    keeper.append_journal({"n": 3})
    assert [entry["n"] for entry in Store(tmp_path).read_journal()] == [3, 1]


def test_a_journal_line_over_the_limit_is_refused(tmp_path):
    with pytest.raises(store.StoreError, match="trop longue"):
        Store(tmp_path).append_journal({"blob": "x" * (store.JOURNAL_LINE_LIMIT + 1)})


def test_the_files_written_are_canonical_json(tmp_path):
    keeper = Store(tmp_path)
    keeper.save_library({"b": 1, "a": "é"})
    header_line, body = (tmp_path / "library.json").read_bytes().split(b"\n", 1)
    header = json.loads(header_line)
    assert body == b'{"a":"\xc3\xa9","b":1}\n'
    assert header["bytes"] == len(body) - 1 and header["schema"] == store.SCHEMA
