#!/usr/bin/env python3
"""Write manifest.json from the candidate, the installer and the live pins.

The pins are those cold-push-guard-v1 checked on the printer on 31 October
2026, idle, before and after its installation. kctrl_end.py leaves them (its own pin is
`before_sha256`) and kctrl_purge_guard.py joins them: after a failed end this
owner relies on its cold push refusal (ADR-076). The flash parade of the same
night changed only /usr/data/creality/userdata/log/log_config.json, which no
pin covers.
"""

import hashlib
import json
from pathlib import Path

PACKAGE = Path(__file__).resolve().parent
ROOT = PACKAGE.parents[2]
SOURCE = 'packages/k1-control-v1/end-no-stock-flush-v5/kctrl_end.py'
KLIPPY = '/usr/share/klipper/klippy/'
EXTRAS = KLIPPY + 'extras/'
CONFIG = '/usr/data/printer_data/config/'
PROTECTED = {
    EXTRAS + 'kctrl_start.py': 'd112cf29c7a215eb50068488b54a4fbf85386788a093901fa45d34223d964d8c',
    EXTRAS + 'kctrl_purge_guard.py': '8c637cc4bf5724c4fb589c7e91ef0e5fc53f700934de0284fc1db20a3f7e1e9a',
    EXTRAS + 'kctrl_tool_change.py': '2e33eb3793ef70a5c1603742aa2e0104f2036ed029511f63ecb96bf1ee2154c2',
    EXTRAS + 'kctrl_slot_map.py': '041de62865702148ec796ea9a502a9067bf11252ffd678ea8886732c48e8c134',
    EXTRAS + 'kctrl_start_policy.py': '27ab49cccc78f0b335d133dd77eee2a92c6c8f9667e0f05f99075d0f691d264f',
    EXTRAS + 'kctrl_start_context.py': '8b6896eb7bea4b4e157441539eb497ef18f4ea1ea640041e54e4d0581c05d273',
    EXTRAS + 'kctrl_bin_motion.py': '2f388f0ffcfaf7be3b1bf3f49f3da5045a0dc4baedd4823e60aa26354e98a8a8',
    EXTRAS + 'kctrl_print_gate.py': '69578e579409b7c4d253acb8c680ceaeb25b60b40502732530a4a786e0966516',
    EXTRAS + 'virtual_sdcard.py': 'e1354dac12671983af1c12bed2b0d70762237d041f0e74c51a173a5adc47c86f',
    EXTRAS + 'pause_resume.py': 'fcb0964da497d0be25dbbd85af98846fe1f226b8d6a4049ada8e53951134e45b',
    EXTRAS + 'filament_switch_sensor.py': 'cc2fa8c08c67b1d8461df803b5fdb8ac07c32a954a52b85b9b3ed72168b26066',
    EXTRAS + 'box.py': '6d7486e1a15cde03f3152eef0d771d0bdd4a90df9b5ef7ecb88bc5d944f20ac4',
    EXTRAS + 'box_wrapper.cpython-38-mipsel-linux-gnu.so':
        'af630c02ccdb51b57585114e5be2be7fcf91fdb10d88872eb6a0c65f048de777',
    EXTRAS + 'heaters.py': '45a7c35c51b019530dda6ef3cbfaab980fe5573839861b2f4460fd7adb9cf3ed',
    EXTRAS + 'gcode_move.py': 'cc0a501eec173e7e3fe6d1592a947889a60d958f875de7875d9e39eb75de4327',
    KLIPPY + 'toolhead.py': '6abeaca5ca4503ff4f360dc84332af5206b1ccf48a961f90ccbe82f653afc9b6',
    KLIPPY + 'kinematics/extruder.py': 'f33b4cd8f9bbd401a5c9500d0a69d66333a2ff1205fabde275b9b1d3f0d5f0fa',
    KLIPPY + 'gcode.py': '20d21ace63ac249c5e38d237898ff18d924047d4532a917124cb92eaed24cde7',
    CONFIG + 'printer.cfg': '07864b095b39ef6d74e5b857567938fc85564146ffb604e5793cf0605cd9a45b',
    CONFIG + 'box.cfg': '8bb0416d9c7a6c46792e1ac2497849befb371bc73ac9864d946ad5b588930194',
    CONFIG + 'gcode_macro.cfg': '864fedde88fbb345c220ae5658f7b04779b3981bd78d68eda6fa63c59c79a04f',
    CONFIG + 'k1-control-owned-start-print-v2.cfg':
        '61bd5f6519a5387eb233a30de6ee9a84d86de7ea88593d5c9cc35b288215d6e9',
    CONFIG + 'k1-control-owned-end-candidate.cfg':
        'c3f2d83e6acd8f48ee28869d6e13975bb289f7fbebe46955f582f5bd1bfadaf3',
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest = {
        'schema': 1,
        'name': 'end-no-stock-flush-v5',
        'adr': 'ADR-076',
        'source': SOURCE,
        'destination': EXTRAS + 'kctrl_end.py',
        'before_sha256': 'f3656210863d57b479ac9bc46dfd55852688233fc3e015838db5c23eee716c86',
        'sha256': sha(ROOT / SOURCE),
        'installer_sha256': sha(PACKAGE / 'remote_install.py'),
        'backup': '/usr/data/k1-control-v1/backups/end-no-stock-flush-v5',
        'effects': {'klipper_restart_idle_only': True, 'heating': False, 'motion': False,
                    'filament': False, 'config_change': False},
        'protected': PROTECTED,
    }
    (PACKAGE / 'manifest.json').write_bytes(
        (json.dumps(manifest, indent=2, sort_keys=False) + '\n').encode('utf-8'))
    print(manifest['sha256'], manifest['installer_sha256'])


if __name__ == '__main__':
    main()
