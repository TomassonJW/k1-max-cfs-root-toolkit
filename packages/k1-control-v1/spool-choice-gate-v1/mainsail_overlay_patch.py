#!/usr/bin/env python3
"""Add (or remove) the Bobines window to Mainsail's index.html.

One script tag before </body>; the tag loads /bobines/overlay.js from the
K1 Control gateway, which opens the spool choice inside Mainsail whenever
Klipper holds a start. Runs on the machine with its python3:

    python3 mainsail_overlay_patch.py /usr/data/k1-control-v1/current/www/mainsail/index.html
    python3 mainsail_overlay_patch.py --remove /usr/data/k1-control-v1/current/www/mainsail/index.html

Idempotent: a file that already carries the tag is left alone. Every change
first writes a dated copy next to the file (index.html.bak-YYYYmmdd-HHMMSS).
A Mainsail update that rewrites index.html drops the tag: run again.
"""
import os
import sys
import time

TAG = '<script type="module" src="/bobines/overlay.js"></script>'
MARK = "<!-- k1-control: bobines -->"
LINE = "        %s %s\n" % (MARK, TAG)


def patched(text):
    return TAG in text


def add(text):
    """The text with the tag before </body>; None when there is no </body>."""
    if patched(text):
        return text
    cut = text.rfind("</body>")
    if cut < 0:
        return None
    # A line of its own, above the line that holds </body>, so that line
    # keeps its indentation and a removal gives the file back byte for byte.
    cut = text.rfind("\n", 0, cut) + 1
    return text[:cut] + LINE + text[cut:]


def remove(text):
    if not patched(text):
        return text
    lines = text.splitlines(True)
    return "".join(line for line in lines if TAG not in line)


def backup(path):
    stamp = time.strftime("%Y%m%d-%H%M%S")
    target = "%s.bak-%s" % (path, stamp)
    serial = 1
    while os.path.exists(target):
        serial += 1
        target = "%s.bak-%s-%d" % (path, stamp, serial)
    with open(path, "rb") as source, open(target, "wb") as copy:
        copy.write(source.read())
    return target


def apply(path, removing=False):
    """(changed, message). Writes only when the text changes."""
    with open(path, "r", encoding="utf-8") as handle:
        before = handle.read()
    after = remove(before) if removing else add(before)
    if after is None:
        return False, "pas de </body> dans %s, rien fait" % path
    if after == before:
        return False, ("balise deja absente" if removing else "balise deja en place") + ": " + path
    saved = backup(path)
    with open(path, "w", encoding="utf-8", newline="") as handle:
        handle.write(after)
    os.chmod(path, 0o644)
    return True, "%s (copie: %s)" % ("balise retiree" if removing else "balise ajoutee", saved)


def main(argv):
    removing = "--remove" in argv
    paths = [item for item in argv if not item.startswith("--")]
    if len(paths) != 1:
        print(__doc__)
        return 2
    changed, message = apply(paths[0], removing)
    print(message)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
