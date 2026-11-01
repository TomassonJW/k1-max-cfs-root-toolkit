"""Sort Mainsail's dashboard macros into three panels: Bobines, Plateau, Réglages.

Mainsail keeps its preferences in Moonraker's database, namespace "mainsail";
nothing here touches the printer configuration. In expert mode Mainsail shows
only the macros placed in a group: the stock Creality steps leave the
dashboard and stay callable from the console.

--apply reads the whole namespace, keeps that read as the backup, writes, then
reads back. --rollback puts every key the plan touches back as the backup
holds it, or deletes the key when the backup has none.

    python mainsail_macro_groups.py HOST --dry-run
    python mainsail_macro_groups.py HOST --apply inventory/raw/<capture>/mainsail-before.json
    python mainsail_macro_groups.py HOST --rollback inventory/raw/<capture>/mainsail-before.json
"""
import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

NAMESPACE = 'mainsail'
ALWAYS = (True, True, True)      # standby, printing, pause
STANDBY = (True, False, False)   # idle, complete, cancelled or error only

# Fixed ids, so a rerun finds its own groups instead of adding copies. Never a
# "_" in one: Mainsail cuts the panel name "macrogroup_<id>" on it. Orange
# ("warning") marks the buttons that heat, home or probe the bed.
GROUPS = [
    ('760785a9-1fb2-40ed-a5e3-121d67dd5f74', 'Bobines', 'primary', ALWAYS, [
        ('KCTRL_SLOTS', 'group', ALWAYS),
        ('KCTRL_SLOT', 'group', STANDBY),
        ('KCTRL_FILAMENT', 'group', STANDBY),
    ]),
    ('4fde55fb-10e1-49d4-9028-2be5604a499a', 'Plateau', 'secondary', STANDBY, [
        ('KCTRL_MESH_CALIBRATE', 'warning', STANDBY),
        ('KCTRL_BED_SCREWS', 'warning', STANDBY),
        ('KCTRL_SCREWS_ONLY', 'warning', STANDBY),
        ('KCTRL_MESH_REF_SHOW', 'group', STANDBY),
        ('KCTRL_Z_LIST', 'group', STANDBY),
    ]),
    ('ad739ada-0d31-4c85-8be8-86f95ba9afa6', 'Réglages', 'secondary', STANDBY, [
        ('KCTRL_Z_SAVE', 'group', STANDBY),
        ('KCTRL_Z_REPEAT', 'warning', STANDBY),
        ('KCTRL_PROFILE_NAME', 'group', STANDBY),
    ]),
]
PANELS = ['macrogroup_' + group[0] for group in GROUPS]
# Mainsail's layouts per screen size, columns in order.
VIEWPORTS = [
    ['mobileLayout'],
    ['tabletLayout1', 'tabletLayout2'],
    ['desktopLayout1', 'desktopLayout2'],
    ['widescreenLayout1', 'widescreenLayout2', 'widescreenLayout3'],
]
ABSENT = object()


def shown(flags):
    return dict(zip(('showInStandby', 'showInPrinting', 'showInPause'), flags))


def group_value(name, color, flags, macros):
    """One group as Mainsail's settings page stores it."""
    value = dict(name=name, color=color, colorCustom='#fff', **shown(flags))
    value['macros'] = [dict(pos=pos, name=macro, color=macro_color, **shown(macro_flags))
                       for pos, (macro, macro_color, macro_flags) in enumerate(macros, 1)]
    return value


def macros_value(current):
    """The "macros" key: expert mode and the three groups, other groups kept."""
    value = json.loads(json.dumps(current)) if isinstance(current, dict) else {}
    value['mode'] = 'expert'
    value.setdefault('hiddenMacros', [])
    groups = value['macrogroups'] = dict(value.get('macrogroups') or {})
    for group_id, name, color, flags, macros in GROUPS:
        groups[group_id] = group_value(name, color, flags, macros)
    return value


def placed(dashboard):
    """Layouts to rewrite: the three panels right after the Macros panel.

    The Macros entry stays, so going back to simple mode puts it back where it
    was. A screen size whose layouts are not stored, or hold no Macros panel,
    is left alone: Mainsail adds the missing panels at the end of its first
    column by itself.
    """
    writes = {}
    for columns in VIEWPORTS:
        stored = [name for name in columns if isinstance(dashboard.get(name), list)]
        present = {entry.get('name') for name in stored for entry in dashboard[name]
                   if isinstance(entry, dict)}
        missing = [panel for panel in PANELS if panel not in present]
        target = next((name for name in stored if any(
            isinstance(entry, dict) and entry.get('name') == 'macros'
            for entry in dashboard[name])), None)
        if not missing or target is None:
            continue
        layout = []
        for entry in dashboard[target]:
            layout.append(entry)
            if isinstance(entry, dict) and entry.get('name') == 'macros':
                layout.extend({'name': panel, 'visible': True} for panel in missing)
        writes['dashboard.' + target] = layout
    return writes


def lookup(namespace, key):
    value = namespace
    for part in key.split('.'):
        if not isinstance(value, dict) or part not in value:
            return ABSENT
        value = value[part]
    return value


def plan(namespace):
    """Every key to write, in order, with its new value; empty once applied."""
    writes = {}
    current = lookup(namespace, 'macros')
    wanted = macros_value(None if current is ABSENT else current)
    if current != wanted:
        writes['macros'] = wanted
    dashboard = lookup(namespace, 'dashboard')
    writes.update(placed(dashboard if isinstance(dashboard, dict) else {}))
    return writes


def missing_macros(objects):
    """Group macros absent from Klipper, compared with the exact case."""
    names = {obj[len('gcode_macro '):] for obj in objects if obj.startswith('gcode_macro ')}
    return [macro for group in GROUPS for macro, _, _ in group[4] if macro not in names]


class Moonraker:
    def __init__(self, host, port=4409, timeout=15):
        self.base = 'http://%s:%d/' % (host, port)
        self.timeout = timeout

    def call(self, method, path, body=None):
        data = None if body is None else json.dumps(body).encode()
        request = urllib.request.Request(self.base + path, data=data, method=method,
                                         headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(request, timeout=self.timeout) as reply:
            return json.loads(reply.read().decode())['result']

    def namespace(self):
        try:
            return self.call('GET', 'server/database/item?namespace=' + NAMESPACE)['value']
        except urllib.error.HTTPError as error:
            if error.code == 404:  # nothing stored yet: Mainsail runs on defaults
                return {}
            raise

    def objects(self):
        return self.call('GET', 'printer/objects/list')['objects']

    def state(self):
        status = self.call('GET', 'printer/objects/query?print_stats')['status']
        return status['print_stats']['state']

    def post(self, key, value):
        self.call('POST', 'server/database/item',
                  {'namespace': NAMESPACE, 'key': key, 'value': value})

    def delete(self, key):
        query = urllib.parse.urlencode({'namespace': NAMESPACE, 'key': key})
        self.call('DELETE', 'server/database/item?' + query)


def differences(namespace, expected):
    return [key for key, value in expected.items() if lookup(namespace, key) != value]


def summary(writes, out):
    for key, value in writes.items():
        if key == 'macros':
            groups = value['macrogroups']
            out('write macros: mode %s, %d groups (%s)' % (value['mode'], len(groups), ', '.join(
                '%s %d' % (group['name'], len(group.get('macros') or [])) for group in groups.values())))
        else:
            out('write %s: %s' % (key, ', '.join(entry.get('name', '?') if isinstance(entry, dict)
                                                else '?' for entry in value)))


def rollback(moonraker, backup_path, out):
    """Each key the plan touches goes back to the backup; works mid-print too."""
    with open(backup_path, encoding='utf-8') as handle:
        backup = json.load(handle)
    restore = {key: lookup(backup, key) for key in plan(backup)}
    current = moonraker.namespace()
    for key, value in restore.items():
        if lookup(current, key) == value:
            out('kept %s: already as in the backup' % key)
        elif value is ABSENT:
            moonraker.delete(key)
            out('deleted %s: absent from the backup' % key)
        else:
            moonraker.post(key, value)
            out('restored %s' % key)
    wrong = differences(moonraker.namespace(), restore)
    out('rollback %s' % ('OK' if not wrong else 'differs: ' + ', '.join(wrong)))
    return 1 if wrong else 0


def run(moonraker, mode, backup_path=None, out=print):
    """0 done or nothing to do, 1 refused or not as planned."""
    if mode == 'rollback':
        return rollback(moonraker, backup_path, out)
    state = moonraker.state()
    if mode == 'apply' and state in ('printing', 'paused'):
        out('refused: print_stats %s' % state)
        return 1
    missing = missing_macros(moonraker.objects())
    if missing:
        out('refused: macros absent from Klipper: %s' % ', '.join(missing))
        return 1
    namespace = moonraker.namespace()
    writes = plan(namespace)
    out('print_stats %s; %s' % (state, 'nothing to write' if not writes else
                                '%d keys to write' % len(writes)))
    summary(writes, out)
    if mode == 'dry-run' or not writes:
        return 0
    if os.path.exists(backup_path):
        out('refused: backup %s already exists' % backup_path)
        return 1
    os.makedirs(os.path.dirname(os.path.abspath(backup_path)), exist_ok=True)
    with open(backup_path, 'x', encoding='utf-8') as handle:
        json.dump(namespace, handle, ensure_ascii=False, indent=1, sort_keys=True)
    for key, value in writes.items():
        moonraker.post(key, value)
    after = moonraker.namespace()
    wrong = differences(after, writes)
    others = [key for key in sorted(set(namespace) | set(after))
              if key not in ('macros', 'dashboard') and namespace.get(key) != after.get(key)]
    if others:
        out('note: other keys changed meanwhile: %s' % ', '.join(others))
    out('apply %s' % ('OK' if not wrong else 'differs: ' + ', '.join(wrong)))
    return 1 if wrong else 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0], allow_abbrev=False)
    parser.add_argument('host')
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument('--dry-run', action='store_true')
    action.add_argument('--apply', metavar='BACKUP')
    action.add_argument('--rollback', metavar='BACKUP')
    args = parser.parse_args(argv)
    if args.dry_run:
        return run(Moonraker(args.host), 'dry-run')
    if args.apply:
        return run(Moonraker(args.host), 'apply', args.apply)
    return run(Moonraker(args.host), 'rollback', args.rollback)


if __name__ == '__main__':
    sys.exit(main())
