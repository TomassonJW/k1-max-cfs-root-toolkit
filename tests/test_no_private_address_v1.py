"""Aucun fichier suivi ne nomme une machine du réseau privé.

Le dépôt est public et AGENTS.md interdit d'y écrire l'adresse de
l'imprimante. Elle y était pourtant entrée par STATE, HANDOFF, GOALS, deux
documents, un README et deux tests : une règle que rien ne vérifie ne tient
pas. Ce module la vérifie à chaque exécution, CI comprise.

Une plage (`192.168.0.0/16`, la liste d'accès de la passerelle) n'est pas une
machine et reste permise. Un test qui a besoin d'une adresse prend une adresse
de documentation (RFC 5737, `192.0.2.0/24`), qui n'est pas privée.
"""

import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

# A private IPv4 host (RFC 1918): not part of a longer dotted number and not
# followed by a prefix length.
PRIVATE_HOST = re.compile(
    r"(?<!\d)(?<!\d\.)"
    r"(?:10\.\d{1,3}|172\.(?:1[6-9]|2\d|3[01])|192\.168)\.\d{1,3}\.\d{1,3}"
    r"(?!\d|\.\d|/\d)"
)

# Installed on the K1 and pinned by hash in the deployment manifests, so they
# change only with the next pose of the start configuration, at rest and with
# Thomas's agreement; the test file reads the first one. Each value is how many
# addresses the file holds. Once a pose removes them this module fails until
# the entry goes: an exception nobody re-examines becomes a blind spot.
KNOWN = {
    "packages/k1-control-v1/owned-start-print-v2/k1-control-owned-start-print-v2.cfg": 1,
    "packages/k1-control-v1/retained-start-v1/k1-control-owned-start-print-v2.cfg": 1,
    "tests/test_kctrl_print_gate_v1.py": 1,
}


def tracked_files():
    try:
        listing = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT,
                                 capture_output=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        pytest.skip("not a git checkout: the tracked files are unknown")
    return [name for name in listing.decode("utf-8").split("\0") if name]


def addresses_in(name):
    try:
        data = (ROOT / name).read_bytes()
    except OSError:
        return 0
    if b"\0" in data:
        return 0
    return len(PRIVATE_HOST.findall(data.decode("utf-8", errors="replace")))


def test_no_tracked_file_names_a_private_host():
    # Counts only: the CI log of a public repository must not print the address.
    found = {}
    for name in tracked_files():
        count = addresses_in(name)
        if count:
            found[name] = count
    assert found == KNOWN


def host(*octets):
    # Built at run time, so this file never holds a private address itself.
    return ".".join(str(octet) for octet in octets)


@pytest.mark.parametrize("text, count", [
    ("http://%s:4409/bobines/" % host(192, 168, 7, 20), 1),
    ("la K1 répond en %s." % host(10, 0, 0, 7), 1),
    ("`%s`" % host(172, 31, 4, 2), 1),
    ("allow %s/16;" % host(192, 168, 0, 0), 0),
    ("http://%s:4409/" % host(192, 0, 2, 10), 0),
    ("%s, hors de 172.16.0.0/12" % host(172, 32, 0, 1), 0),
    ("build %s.4" % host(10, 1, 2, 3), 0),
])
def test_the_pattern_finds_hosts_not_ranges_or_longer_numbers(text, count):
    assert len(PRIVATE_HOST.findall(text)) == count
