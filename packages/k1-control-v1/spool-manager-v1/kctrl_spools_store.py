"""Durable storage of the spool library, its journal and the print checkpoint.

Document 102, lot A. Everything lives in one directory of the K1 Control
state folder, `state/spools/`:

- `library.json` holds the whole library. It is rewritten only when Thomas
  acts, when a slot's content changes and at the end of a print, never on a
  timer. Its first line is a header carrying the schema, a revision number and
  the sha256 of the body that follows. A new revision is written to a
  temporary file and flushed to the medium before it is put in place; the
  three previous revisions stay as `library.json.1` to `.3`. Loading takes the
  highest intact revision, so a cut at any step leaves the old library or the
  new one, never a mixture.
- `journal.jsonl` gets one line per event, flushed as it is written. Past its
  limit it becomes `journal.1.jsonl` and a new one starts: the journal never
  holds more than two limits.
- `checkpoint.a` and `checkpoint.b` carry the counter's state during a print:
  a fixed size, rewritten in place, each write going to the slot that does not
  hold the newest intact state. A print never grows a file, and a cut in the
  middle of a write leaves the previous checkpoint readable.

Every public method takes the same lock: the component calls them from worker
threads. Nothing here knows what a spool is.
"""

from __future__ import annotations

import hashlib
import json
import os
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

LIBRARY = "library.json"
JOURNAL = "journal.jsonl"
JOURNAL_OLD = "journal.1.jsonl"
CHECKPOINTS = ("checkpoint.a", "checkpoint.b")
TEMPORARY = LIBRARY + ".tmp"
LIBRARY_FORMAT = "kctrl_spools.library"
CHECKPOINT_FORMAT = "kctrl_spools.checkpoint"
SCHEMA = 1
COPIES = 3
MAX_LIBRARY_BYTES = 4 << 20
JOURNAL_LIMIT = 256 << 10
JOURNAL_LINE_LIMIT = 8 << 10
CHECKPOINT_BYTES = 4096


class StoreError(RuntimeError):
    pass


def encode(value: Any) -> bytes:
    """Canonical JSON: sorted keys, no spaces, UTF-8, no NaN."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def parse(data: bytes, expected: str) -> Tuple[Optional[Dict[str, Any]], Any, str]:
    """(header, value, reason) of a header line followed by its body.

    The header names the format, the body's length and its sha256; anything
    after the body (a newline, the checkpoint's padding) is ignored. A torn,
    truncated or zeroed file gives no value and the reason why.
    """
    newline = data.find(b"\n")
    if newline <= 0:
        return None, None, "en-tête absent"
    try:
        header = json.loads(data[:newline].decode("ascii"))
    except (UnicodeDecodeError, ValueError):
        return None, None, "en-tête illisible"
    if not isinstance(header, dict) or header.get("format") != expected:
        return None, None, "format inconnu"
    size = header.get("bytes")
    if not isinstance(size, int) or isinstance(size, bool) or size < 2:
        return header, None, "taille absente"
    body = data[newline + 1:newline + 1 + size]
    if len(body) != size:
        return header, None, "fichier tronqué"
    if digest(body) != header.get("sha256"):
        return header, None, "empreinte fausse"
    try:
        value = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return header, None, "contenu illisible"
    if not isinstance(value, dict):
        return header, None, "contenu inattendu"
    return header, value, ""


def _number(header: Optional[Dict[str, Any]], key: str) -> int:
    value = (header or {}).get(key)
    if isinstance(value, int) and not isinstance(value, bool) and value > 0:
        return value
    return 0


def _size(path: str) -> int:
    try:
        return os.path.getsize(path)
    except OSError:
        return -1


class SpoolStore:
    """The files of one directory, behind one lock."""

    def __init__(self, directory: str, journal_limit: int = JOURNAL_LIMIT,
                 checkpoint_bytes: int = CHECKPOINT_BYTES, copies: int = COPIES,
                 max_library_bytes: int = MAX_LIBRARY_BYTES,
                 clock: Callable[[], float] = time.time) -> None:
        self.directory = directory
        self.journal_limit = journal_limit
        self.line_limit = min(JOURNAL_LINE_LIMIT, journal_limit)
        self.checkpoint_bytes = checkpoint_bytes
        self.copies = copies
        self.max_library_bytes = max_library_bytes
        self.clock = clock
        self.lock = threading.RLock()
        self.loaded = False
        # Highest revision any file has carried, intact or not: a new save
        # always goes above every copy it may rotate away.
        self.revision = 0
        # Set when the library cannot be written without destroying data: a
        # copy from a newer schema, or damaged copies that could not be put
        # aside. Every save is refused while it is set.
        self.locked = ""
        self.checkpoint_seq = 0
        self.checkpoint_slot = None  # type: Optional[int]
        self.checkpoint_scanned = False

    def _step(self, name: str) -> None:
        """Called before every write step: the tests cut the power here."""

    def _path(self, name: str) -> str:
        return os.path.join(self.directory, name)

    def _copies(self) -> List[str]:
        return [LIBRARY] + ["%s.%d" % (LIBRARY, index) for index in range(1, self.copies + 1)]

    def _read(self, name: str, limit: int) -> bytes:
        with open(self._path(name), "rb") as stream:
            return stream.read(limit)

    def _sync_directory(self) -> None:
        # A rename is durable once its directory is; Windows has no such
        # call, and a refusal only costs the guarantee, never the data.
        flag = getattr(os, "O_DIRECTORY", None)
        if flag is None:
            return
        try:
            descriptor = os.open(self.directory, os.O_RDONLY | flag)
        except OSError:
            return
        try:
            os.fsync(descriptor)
        except OSError:
            pass
        finally:
            os.close(descriptor)

    def _write(self, stream: Any, data: bytes, half: str, middle: int = -1) -> None:
        # The tests cut the power at `half`: the middle of what matters.
        middle = len(data) // 2 if middle < 0 else middle
        stream.write(data[:middle])
        self._step(half)
        stream.write(data[middle:])
        stream.flush()
        os.fsync(stream.fileno())

    # Library -------------------------------------------------------------

    def load_library(self) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
        """(library or None, report): the highest intact revision.

        The report says which file was loaded, whether it was a fallback,
        which copies are damaged and why, and whether the store is locked.
        With no intact copy at all, the damaged ones are moved to a
        `quarantine-<time>` folder, never rotated away, and the library starts
        empty; if they cannot be moved, the store locks.
        """
        with self.lock:
            return self._load()

    def _load(self) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
        report = {"source": "", "revision": 0, "fallback": False, "damaged": [],
                  "fresh": False, "quarantined": "", "locked": ""}  # type: Dict[str, Any]
        best = None  # type: Optional[Tuple[int, int, str, Dict[str, Any]]]
        highest = 0
        newer = ""
        present = []
        self.locked = ""
        for order, name in enumerate(self._copies()):
            if _size(self._path(name)) < 0:
                continue
            present.append(name)
            try:
                data = self._read(name, self.max_library_bytes + 4096)
            except OSError as exception:
                report["damaged"].append({"file": name, "reason": "illisible : %s" % exception})
                continue
            header, value, reason = parse(data, LIBRARY_FORMAT)
            highest = max(highest, _number(header, "revision"))
            if value is None:
                report["damaged"].append({"file": name, "reason": reason})
                continue
            schema = header.get("schema")
            if not isinstance(schema, int) or isinstance(schema, bool) or schema < 1:
                report["damaged"].append({"file": name, "reason": "schéma absent"})
                continue
            if schema > SCHEMA:
                newer = ("%s vient d'une version plus récente (schéma %d) : rien n'est "
                         "réécrit tant que cette version est installée" % (name, schema))
                continue
            revision = _number(header, "revision")
            if revision == 0:
                report["damaged"].append({"file": name, "reason": "révision absente"})
                continue
            # Highest revision first; between equals, the file nearest the
            # top, which is always the one written last.
            key = (revision, -order, name, value)
            if best is None or key[:2] > best[:2]:
                best = key
        self.revision = max(self.revision, highest)
        self.loaded = True
        if _size(self._path(TEMPORARY)) >= 0:
            # A save cut before its last rename: never acknowledged, never used.
            try:
                os.remove(self._path(TEMPORARY))
            except OSError:
                pass
        if newer:
            self.locked = newer
            report["locked"] = newer
            return None, report
        if best is not None:
            report["source"] = best[2]
            report["revision"] = best[0]
            report["fallback"] = best[2] != LIBRARY
            return best[3], report
        report["fresh"] = True
        if present:
            folder = "quarantine-%d" % int(self.clock())
            try:
                os.makedirs(self._path(folder), exist_ok=True)
                for name in present:
                    os.replace(self._path(name), os.path.join(self._path(folder), name))
                self._sync_directory()
                report["quarantined"] = folder
            except OSError as exception:
                self.locked = ("copies abîmées impossibles à mettre de côté (%s) : "
                               "rien n'est réécrit" % exception)
                report["locked"] = self.locked
        return None, report

    def save_library(self, library: Dict[str, Any]) -> int:
        """Write `library` as the next revision and return its number."""
        with self.lock:
            if not self.loaded:
                self._load()
            if self.locked:
                raise StoreError(self.locked)
            try:
                body = encode(library)
            except (TypeError, ValueError) as exception:
                raise StoreError("bibliothèque impossible à enregistrer : %s" % exception)
            if len(body) > self.max_library_bytes:
                raise StoreError("bibliothèque trop grande : %d octets" % len(body))
            revision = self.revision + 1
            header = {"format": LIBRARY_FORMAT, "schema": SCHEMA, "revision": revision,
                      "saved": int(self.clock()), "bytes": len(body), "sha256": digest(body)}
            data = encode(header) + b"\n" + body + b"\n"
            try:
                os.makedirs(self.directory, exist_ok=True)
                # The number is spent as soon as a file may carry it, so two
                # different libraries never share a revision.
                self.revision = revision
                self._step("library:write")
                with open(self._path(TEMPORARY), "wb") as stream:
                    self._write(stream, data, "library:half")
                for index in range(self.copies, 0, -1):
                    older = LIBRARY if index == 1 else "%s.%d" % (LIBRARY, index - 1)
                    if _size(self._path(older)) >= 0:
                        self._step("library:rotate-%d" % index)
                        os.replace(self._path(older), self._path("%s.%d" % (LIBRARY, index)))
                self._step("library:replace")
                os.replace(self._path(TEMPORARY), self._path(LIBRARY))
                self._step("library:directory")
                self._sync_directory()
            except OSError as exception:
                raise StoreError("écriture de la bibliothèque impossible : %s" % exception)
            return revision

    # Journal -------------------------------------------------------------

    def append_journal(self, entry: Dict[str, Any]) -> None:
        """Add one line; a line left torn by a cut never swallows this one."""
        with self.lock:
            try:
                line = encode(entry)
            except (TypeError, ValueError) as exception:
                raise StoreError("ligne de journal impossible à enregistrer : %s" % exception)
            if len(line) + 1 > self.line_limit:
                raise StoreError("ligne de journal trop longue : %d octets" % len(line))
            path = self._path(JOURNAL)
            try:
                os.makedirs(self.directory, exist_ok=True)
                size = max(0, _size(path))
                if size and size + len(line) + 2 > self.journal_limit:
                    self._step("journal:rotate")
                    os.replace(path, self._path(JOURNAL_OLD))
                    size = 0
                prefix = b""
                if size:
                    with open(path, "rb") as stream:
                        stream.seek(size - 1)
                        if stream.read(1) != b"\n":
                            prefix = b"\n"
                self._step("journal:append")
                with open(path, "ab") as stream:
                    self._write(stream, prefix + line + b"\n", "journal:half")
            except OSError as exception:
                raise StoreError("écriture du journal impossible : %s" % exception)

    def read_journal(self, limit: int = 200) -> List[Dict[str, Any]]:
        """The newest `limit` entries, newest first; unreadable lines skipped."""
        with self.lock:
            entries = []  # type: List[Dict[str, Any]]
            for name in (JOURNAL_OLD, JOURNAL):
                try:
                    data = self._read(name, 2 * self.journal_limit)
                except OSError:
                    continue
                for raw in data.split(b"\n"):
                    if not raw.strip():
                        continue
                    try:
                        entry = json.loads(raw.decode("utf-8"))
                    except (UnicodeDecodeError, ValueError):
                        continue
                    if isinstance(entry, dict):
                        entries.append(entry)
            entries.reverse()
            return entries[:max(0, int(limit))]

    # Checkpoint ----------------------------------------------------------

    def _scan_checkpoints(self) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
        report = {"source": "", "seq": 0, "damaged": []}  # type: Dict[str, Any]
        best = None  # type: Optional[Tuple[int, int, Dict[str, Any]]]
        highest = 0
        for index, name in enumerate(CHECKPOINTS):
            if _size(self._path(name)) < 0:
                continue
            try:
                data = self._read(name, self.checkpoint_bytes)
            except OSError as exception:
                report["damaged"].append({"file": name, "reason": "illisible : %s" % exception})
                continue
            header, value, reason = parse(data, CHECKPOINT_FORMAT)
            seq = _number(header, "seq")
            highest = max(highest, seq)
            if value is None or seq == 0:
                report["damaged"].append({"file": name, "reason": reason or "numéro absent"})
                continue
            if best is None or seq > best[0]:
                best = (seq, index, value)
        self.checkpoint_seq = max(self.checkpoint_seq, highest)
        self.checkpoint_slot = best[1] if best is not None else None
        self.checkpoint_scanned = True
        if best is None:
            return None, report
        report["source"] = CHECKPOINTS[best[1]]
        report["seq"] = best[0]
        return best[2], report

    def load_checkpoint(self) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
        """(state or None, report): the newest intact checkpoint."""
        with self.lock:
            return self._scan_checkpoints()

    def save_checkpoint(self, state: Dict[str, Any]) -> int:
        """Overwrite the slot not holding the newest intact state."""
        with self.lock:
            if not self.checkpoint_scanned:
                self._scan_checkpoints()
            try:
                body = encode(state)
            except (TypeError, ValueError) as exception:
                raise StoreError("point de reprise impossible à enregistrer : %s" % exception)
            seq = self.checkpoint_seq + 1
            header = {"format": CHECKPOINT_FORMAT, "seq": seq, "saved": int(self.clock()),
                      "bytes": len(body), "sha256": digest(body)}
            data = encode(header) + b"\n" + body + b"\n"
            if len(data) > self.checkpoint_bytes:
                raise StoreError("point de reprise trop grand : %d octets sur %d"
                                 % (len(data), self.checkpoint_bytes))
            meaningful = len(data)
            data += b" " * (self.checkpoint_bytes - len(data))
            target = 1 if self.checkpoint_slot == 0 else 0
            path = self._path(CHECKPOINTS[target])
            try:
                os.makedirs(self.directory, exist_ok=True)
                self.checkpoint_seq = seq
                self._step("checkpoint:write")
                # In place when the slot already has its size: no new block,
                # no growth, the same 4 KiB every minute of a print.
                mode = "r+b" if _size(path) == self.checkpoint_bytes else "wb"
                with open(path, mode) as stream:
                    stream.seek(0)
                    self._write(stream, data, "checkpoint:half", meaningful // 2)
            except OSError as exception:
                raise StoreError("écriture du point de reprise impossible : %s" % exception)
            self.checkpoint_slot = target
            return seq

    def clear_checkpoint(self) -> None:
        """Remove both slots once the print's balance is in the library."""
        with self.lock:
            for name in CHECKPOINTS:
                self._step("checkpoint:clear")
                try:
                    os.remove(self._path(name))
                except FileNotFoundError:
                    pass
                except OSError as exception:
                    raise StoreError("point de reprise impossible à effacer : %s" % exception)
            self.checkpoint_slot = None
            self.checkpoint_scanned = True
