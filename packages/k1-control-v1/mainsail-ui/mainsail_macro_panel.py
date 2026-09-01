# Give Mainsail a dashboard panel that holds only the macros Thomas uses, and
# hide the catch-all Macros panel that lists every stock Creality step.
#
# This writes Mainsail's own preference store through Moonraker, so nothing
# about the printer configuration changes. Undo is one DELETE on the same keys.
import json
import urllib.request

BASE = "http://127.0.0.1:7125/server/database/item"
GROUP_ID = "k1control"          # no underscore: the panel name splits on "_"
PANEL = "macrogroup_" + GROUP_ID

# name, showInStandby, showInPrinting, showInPause
MACROS = [
    ("KCTRL_MESH_CALIBRATE",  True,  False, False),
    ("KCTRL_MESH_REF_SHOW",   True,  True,  True),
    ("KCTRL_PROFILE_NAME",    True,  True,  True),
    ("KCTRL_Z_SAVE",          True,  True,  True),
    ("KCTRL_Z_LIST",          True,  True,  True),
    ("KCTRL_MESH_ACQUIRE",    True,  False, False),
    ("KCTRL_MESH_SAVE_AS_REF", True, False, False),
]

LAYOUTS = {
    "mobileLayout": ["webcam:0", "toolhead-control:1", "extruder-control:1",
                     "macros:1", "machine-settings:1", "miscellaneous:1",
                     "temperature:1", "miniconsole:0"],
    "tabletLayout1": ["webcam:1", "toolhead-control:1", "extruder-control:1",
                      "macros:1", "machine-settings:1", "miscellaneous:1"],
    "desktopLayout1": ["webcam:1", "toolhead-control:1", "extruder-control:1",
                       "macros:1", "machine-settings:1", "miscellaneous:1"],
    "widescreenLayout1": ["toolhead-control:1", "extruder-control:1",
                          "macros:1", "miscellaneous:1"],
}


def post(key, value):
    body = json.dumps({"namespace": "mainsail", "key": key,
                       "value": value}).encode()
    req = urllib.request.Request(BASE, data=body, method="POST",
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode())


group = {
    "name": "K1 Control",
    "color": "primary",
    "showInStandby": True,
    "showInPrinting": True,
    "showInPause": True,
    "macros": [
        {"pos": i + 1, "name": n, "color": "group",
         "showInStandby": sb, "showInPrinting": pr, "showInPause": pa}
        for i, (n, sb, pr, pa) in enumerate(MACROS)
    ],
}
post("macrogroups." + GROUP_ID, group)
print("groupe K1 Control cree avec %d macros" % len(MACROS))

for layout, spec in LAYOUTS.items():
    panels = []
    for item in spec:
        name, vis = item.rsplit(":", 1)
        if name == "macros":
            # The dedicated panel takes the place of the catch-all one, which
            # stays in the layout so Thomas can switch it back on in two clicks.
            panels.append({"name": PANEL, "visible": True})
            panels.append({"name": "macros", "visible": False})
        else:
            panels.append({"name": name, "visible": vis == "1"})
    post(layout, panels)
    print("%-20s panneau dedie place, fourre-tout masque" % layout)
