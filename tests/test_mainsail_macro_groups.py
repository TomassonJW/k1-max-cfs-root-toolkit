"""Mainsail macro panels: plan, apply and rollback on a fake Moonraker, no network."""
import copy
import importlib.util
import io
import json
from pathlib import Path
import re
import urllib.error

import pytest

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / 'packages/k1-control-v1/mainsail-ui'


def load():
    spec = importlib.util.spec_from_file_location('mainsail_macro_groups',
                                                  PACKAGE / 'mainsail_macro_groups.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


mg = load()
GROUP_MACROS = [macro for group in mg.GROUPS for macro, _, _ in group[4]]
OBJECTS = (['toolhead', 'print_stats', 'gcode_macro START_PRINT', 'gcode_macro _KCTRL_START_CONF']
           + ['gcode_macro ' + macro for macro in GROUP_MACROS])


def entry(name, visible=True):
    return {'name': name, 'visible': visible}


# Shaped like the layouts the September attempt found on the K1.
NAMESPACE = {
    'general': {'printername': 'K1 Max'},
    'dashboard': {
        'mobileLayout': [entry('webcam', False), entry('toolhead-control'), entry('macros'),
                         entry('temperature'), entry('miniconsole', False)],
        'desktopLayout1': [entry('webcam'), entry('toolhead-control'), entry('macros'),
                           entry('machine-settings'), entry('miscellaneous')],
        'desktopLayout2': [entry('temperature'), entry('miniconsole')],
        'nonExpandPanels': {'desktop': ['webcam']},
    },
    'view': {'gcodefiles': {'sortBy': 'modified'}},
}


class FakeMoonraker:
    """The four database calls and three reads the tool uses, in memory."""

    def __init__(self, namespace=None, state='standby', objects=OBJECTS, drop=()):
        self.db = copy.deepcopy(NAMESPACE if namespace is None else namespace)
        self.print_state = state
        self.objs = list(objects)
        self.drop = set(drop)
        self.calls = []

    def namespace(self):
        return copy.deepcopy(self.db)

    def objects(self):
        return list(self.objs)

    def state(self):
        return self.print_state

    def post(self, key, value):
        self.calls.append(('post', key))
        if key in self.drop:
            return
        *parents, leaf = key.split('.')
        node = self.db
        for part in parents:
            node = node.setdefault(part, {})
        node[leaf] = json.loads(json.dumps(value))

    def delete(self, key):
        self.calls.append(('delete', key))
        *parents, leaf = key.split('.')
        node = self.db
        for part in parents:
            node = node[part]
        del node[leaf]  # a missing key fails, like Moonraker's 404


def run(fake, mode, backup=None):
    lines = []
    code = mg.run(fake, mode, None if backup is None else str(backup), out=lines.append)
    return code, lines


def names(layout):
    return [item['name'] for item in layout]


def test_ids_are_unique_and_never_hold_an_underscore():
    ids = [group[0] for group in mg.GROUPS]
    assert len(set(ids)) == 3
    assert all('_' not in group_id for group_id in ids)
    assert mg.PANELS == ['macrogroup_' + group_id for group_id in ids]
    # Mainsail reads the id back as the text after "macrogroup_".
    assert [panel[len('macrogroup_'):] for panel in mg.PANELS] == ids


def test_every_macro_is_defined_with_this_exact_case_in_the_packages():
    defined = set()
    for cfg in (ROOT / 'packages/k1-control-v1').rglob('*.cfg'):
        text = cfg.read_text(encoding='utf-8', errors='replace')
        defined.update(re.findall(r'^\[gcode_macro (\S+)\]', text, re.MULTILINE))
    assert [macro for macro in GROUP_MACROS if macro not in defined] == []
    assert len(GROUP_MACROS) == len(set(GROUP_MACROS)) == 11


def test_groups_hold_the_fields_mainsail_settings_page_stores():
    value = mg.macros_value(None)
    assert value['mode'] == 'expert' and value['hiddenMacros'] == []
    for group in value['macrogroups'].values():
        assert set(group) == {'name', 'color', 'colorCustom', 'showInStandby',
                              'showInPrinting', 'showInPause', 'macros'}
        assert group['color'] in {'primary', 'secondary', 'success', 'warning', 'error'}
        assert [macro['pos'] for macro in group['macros']] == list(range(1, len(group['macros']) + 1))
        for macro in group['macros']:
            assert set(macro) == {'pos', 'name', 'color', 'showInStandby',
                                  'showInPrinting', 'showInPause'}
            assert macro['color'] in {'group', 'primary', 'secondary', 'success', 'warning', 'error'}


def test_only_the_slot_list_stays_on_screen_while_printing():
    groups = {group['name']: group for group in mg.macros_value(None)['macrogroups'].values()}
    assert [name for name in groups] == ['Bobines', 'Plateau', 'Réglages']
    for name, group in groups.items():
        assert group['showInStandby']
        assert group['showInPrinting'] == group['showInPause'] == (name == 'Bobines')
        for macro in group['macros']:
            assert macro['showInStandby']
            always = macro['name'] == 'KCTRL_SLOTS'
            assert macro['showInPrinting'] == macro['showInPause'] == always


def test_orange_marks_the_buttons_that_heat_home_or_probe():
    orange = {macro for group in mg.GROUPS for macro, color, _ in group[4] if color == 'warning'}
    assert orange == {'KCTRL_MESH_CALIBRATE', 'KCTRL_BED_SCREWS', 'KCTRL_SCREWS_ONLY',
                      'KCTRL_Z_REPEAT'}


def test_nothing_stored_writes_only_the_macros_key():
    writes = mg.plan({})
    assert list(writes) == ['macros']
    assert list(writes['macros']['macrogroups']) == [group[0] for group in mg.GROUPS]


def test_a_group_thomas_made_and_his_hidden_list_are_kept():
    own = {'name': 'Mes essais', 'color': 'success', 'colorCustom': '#fff', 'showInStandby': True,
           'showInPrinting': True, 'showInPause': True, 'macros': []}
    namespace = {'macros': {'mode': 'simple', 'hiddenMacros': ['BOX_CHECK'],
                            'macrogroups': {'mine': own}}}
    value = mg.plan(namespace)['macros']
    assert value['mode'] == 'expert'
    assert value['hiddenMacros'] == ['BOX_CHECK']
    assert value['macrogroups']['mine'] == own
    assert len(value['macrogroups']) == 4
    assert namespace['macros']['mode'] == 'simple'  # the read itself is never changed


def test_panels_go_right_after_macros_which_stays():
    writes = mg.plan(NAMESPACE)
    assert set(writes) == {'macros', 'dashboard.mobileLayout', 'dashboard.desktopLayout1'}
    assert names(writes['dashboard.desktopLayout1']) == [
        'webcam', 'toolhead-control', 'macros', *mg.PANELS, 'machine-settings', 'miscellaneous']
    assert names(writes['dashboard.mobileLayout']) == [
        'webcam', 'toolhead-control', 'macros', *mg.PANELS, 'temperature', 'miniconsole']
    # Hidden entries keep their visibility; the new panels show.
    assert writes['dashboard.mobileLayout'][0] == entry('webcam', False)
    assert all(item['visible'] for item in writes['dashboard.desktopLayout1'][3:6])


def test_a_screen_without_stored_layout_or_macros_panel_is_left_to_mainsail():
    namespace = {'dashboard': {'tabletLayout1': [entry('webcam')],
                               'tabletLayout2': [entry('temperature')]}}
    assert list(mg.plan(namespace)) == ['macros']


def test_macros_in_a_second_column_takes_the_panels_there():
    namespace = {'dashboard': {'widescreenLayout1': [entry('webcam')],
                               'widescreenLayout2': [entry('macros'), entry('temperature')],
                               'widescreenLayout3': [entry('miniconsole')]}}
    writes = mg.plan(namespace)
    assert set(writes) == {'macros', 'dashboard.widescreenLayout2'}
    assert names(writes['dashboard.widescreenLayout2']) == ['macros', *mg.PANELS, 'temperature']


def test_a_panel_moved_to_another_column_is_not_added_twice():
    namespace = copy.deepcopy(NAMESPACE)
    namespace['dashboard']['desktopLayout2'].append(entry(mg.PANELS[0]))
    layout = mg.plan(namespace)['dashboard.desktopLayout1']
    assert names(layout).count(mg.PANELS[0]) == 0
    assert names(layout)[3:5] == mg.PANELS[1:]


def test_null_entries_mainsail_may_leave_are_tolerated():
    namespace = {'dashboard': {'desktopLayout1': [None, entry('macros')]}}
    layout = mg.plan(namespace)['dashboard.desktopLayout1']
    assert layout[0] is None and names(layout[1:]) == ['macros', *mg.PANELS]


def test_the_plan_is_empty_once_applied():
    fake = FakeMoonraker()
    for key, value in mg.plan(fake.namespace()).items():
        fake.post(key, value)
    assert mg.plan(fake.namespace()) == {}


def test_apply_then_rollback_gives_back_the_exact_namespace(tmp_path):
    fake = FakeMoonraker()
    backup = tmp_path / 'capture' / 'mainsail-before.json'
    code, lines = run(fake, 'apply', backup)
    assert code == 0 and lines[-1] == 'apply OK'
    assert json.loads(backup.read_text(encoding='utf-8')) == NAMESPACE
    assert fake.db['macros']['mode'] == 'expert'
    assert ('post', 'dashboard.desktopLayout2') not in fake.calls
    code, lines = run(fake, 'apply', tmp_path / 'second.json')
    assert code == 0 and 'nothing to write' in lines[0]
    assert not (tmp_path / 'second.json').exists()

    fake.calls.clear()
    code, lines = run(fake, 'rollback', backup)
    assert code == 0 and lines[-1] == 'rollback OK'
    assert fake.db == NAMESPACE
    assert ('delete', 'macros') in fake.calls
    fake.calls.clear()
    code, lines = run(fake, 'rollback', backup)
    assert code == 0 and fake.calls == []


@pytest.mark.parametrize('state', ['printing', 'paused'])
def test_apply_is_refused_during_a_print(tmp_path, state):
    fake = FakeMoonraker(state=state)
    code, lines = run(fake, 'apply', tmp_path / 'backup.json')
    assert code == 1 and lines == ['refused: print_stats %s' % state]
    assert fake.calls == [] and not (tmp_path / 'backup.json').exists()


def test_rollback_still_runs_during_a_print(tmp_path):
    fake = FakeMoonraker()
    backup = tmp_path / 'backup.json'
    assert run(fake, 'apply', backup)[0] == 0
    fake.print_state = 'printing'
    assert run(fake, 'rollback', backup)[0] == 0
    assert fake.db == NAMESPACE


def test_dry_run_writes_nothing_even_during_a_print():
    fake = FakeMoonraker(state='printing')
    code, lines = run(fake, 'dry-run')
    assert code == 0 and fake.calls == []
    assert lines[0] == 'print_stats printing; 3 keys to write'
    assert lines[1] == 'write macros: mode expert, 3 groups (Bobines 3, Plateau 5, Réglages 3)'


@pytest.mark.parametrize('objects', [
    [obj for obj in OBJECTS if obj != 'gcode_macro KCTRL_Z_REPEAT'],
    [obj.replace('KCTRL_SLOTS', 'kctrl_slots') for obj in OBJECTS],
])
def test_a_missing_macro_or_another_case_refuses(tmp_path, objects):
    fake = FakeMoonraker(objects=objects)
    code, lines = run(fake, 'apply', tmp_path / 'backup.json')
    assert code == 1 and lines[0].startswith('refused: macros absent from Klipper: KCTRL_')
    assert fake.calls == []


def test_an_existing_backup_is_never_overwritten(tmp_path):
    backup = tmp_path / 'backup.json'
    backup.write_text('{"kept": true}', encoding='utf-8')
    fake = FakeMoonraker()
    code, lines = run(fake, 'apply', backup)
    assert code == 1 and lines[-1] == 'refused: backup %s already exists' % backup
    assert fake.calls == [] and backup.read_text(encoding='utf-8') == '{"kept": true}'


def test_a_write_that_did_not_land_is_reported(tmp_path):
    fake = FakeMoonraker(drop={'dashboard.mobileLayout'})
    code, lines = run(fake, 'apply', tmp_path / 'backup.json')
    assert code == 1 and lines[-1] == 'apply differs: dashboard.mobileLayout'


def test_other_keys_changed_meanwhile_are_noted(tmp_path):
    fake = FakeMoonraker()
    real_post = fake.post

    def post(key, value):
        real_post(key, value)
        fake.db['view']['gcodefiles']['sortBy'] = 'name'  # an open Mainsail tab saving

    fake.post = post
    code, lines = run(fake, 'apply', tmp_path / 'backup.json')
    assert code == 0 and lines[-2] == 'note: other keys changed meanwhile: view'


class Reply(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_http_calls_and_an_empty_namespace(monkeypatch):
    sent = []

    def urlopen(request, timeout):
        sent.append((request.get_method(), request.full_url, request.data))
        if request.full_url.endswith('namespace=mainsail'):
            raise urllib.error.HTTPError(request.full_url, 404, 'Not Found', {}, None)
        return Reply(json.dumps({'result': {'item': 'ok'}}).encode())

    monkeypatch.setattr(mg.urllib.request, 'urlopen', urlopen)
    moonraker = mg.Moonraker('HOST')
    assert moonraker.namespace() == {}
    moonraker.post('macros', {'mode': 'expert'})
    moonraker.delete('dashboard.desktopLayout1')
    assert sent[0][:2] == ('GET', 'http://HOST:4409/server/database/item?namespace=mainsail')
    assert sent[1][:2] == ('POST', 'http://HOST:4409/server/database/item')
    assert json.loads(sent[1][2]) == {'namespace': 'mainsail', 'key': 'macros',
                                      'value': {'mode': 'expert'}}
    assert sent[2][:2] == ('DELETE', 'http://HOST:4409/server/database/item'
                                     '?namespace=mainsail&key=dashboard.desktopLayout1')


@pytest.mark.parametrize('argv', [[], ['HOST'], ['HOST', '--dry-run', '--apply', 'b.json'],
                                  ['HOST', '--dryrun'], ['HOST', '--dry']])
def test_a_wrong_command_line_exits_2(argv):
    with pytest.raises(SystemExit) as stop:
        mg.main(argv)
    assert stop.value.code == 2
