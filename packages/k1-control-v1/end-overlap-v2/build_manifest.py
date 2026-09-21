"""Build exact baseline and one-file successor manifest; no network."""
import ast
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PACKAGE = Path(__file__).resolve().parent

def build():
    old = json.loads((ROOT/'packages/k1-control-v1/end-separated-v1/manifest.json').read_text(encoding='utf-8'))
    before = {p:h for p,h in old['before'].items() if h is not None}
    for f in old['files']:
        before[f['destination']] = f['sha256']
    files=[]
    for name,dest in [('kctrl_end.py','/usr/share/klipper/klippy/extras/kctrl_end.py')]:
        path=PACKAGE/name
        content=path.read_bytes()
        if name.endswith('.py'): ast.parse(content.decode('utf-8-sig'),feature_version=(3,8))
        files.append({'name':name,'source':path.relative_to(ROOT).as_posix(),'destination':dest,
                      'sha256':hashlib.sha256(content).hexdigest(),'before_sha256':before[dest]})
    installer=PACKAGE/'remote_install.py'
    ast.parse(installer.read_text(encoding='utf-8-sig'),feature_version=(3,8))
    return {'schema':1,'name':'cfs-end-overlap-v2','enabled':True,'physical_validation':False,
            'baseline_capture':'20260921-cfs-separated-end-trial-v1/after-power-cycle-user-retract','before':before,'files':files,
            'installer_sha256':hashlib.sha256(installer.read_bytes()).hexdigest(),
            'backup':'/usr/data/k1-control-v1/backups/cfs-end-overlap-v2',
            'install_effects':['replace_one_file','klipper_service_restart','restore_mesh_and_offsets_MOVE_0'],
            'no_effects':['axis_motion','heat','filament_motion','homing','probing','print_start']}

if __name__=='__main__':
    (PACKAGE/'manifest.json').write_bytes((json.dumps(build(),indent=2)+'\n').encode('utf-8'))
    print('SEPARATED_END_MANIFEST_OK')
