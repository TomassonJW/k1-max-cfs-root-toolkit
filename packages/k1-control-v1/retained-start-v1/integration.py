"""Pure, exact-anchor integration into the reviewed installed start macro.

No SSH, printer connection, G-code dispatch or deployment entry point.
The caller reviews the returned text before making an installation package.
"""


def render_start(base):
    replacements = (
        ('  BOX_START_PRINT\n  G90\n',
         '  KCTRL_START_PLAN SLOT={tool} INDEX={position - 1} TEMP={nozzle}\n'
         '  BOX_START_PRINT\n  G90\n'),
        ('  _KCTRL_START_VERIFY PROFILE={profile} Z={saved_z|float} STAGE=armed\n',
         '  _KCTRL_START_VERIFY PROFILE={profile} Z={saved_z|float} STAGE=armed\n'
         '  KCTRL_START_REFERENCE_READY\n'),
        ('  {% if printer.box.enable|int == 1 %}\n    T{position - 1}\n'
         '    M400\n  {% endif %}\n',
         '  KCTRL_START_MATERIAL\n'),
        ('  _KCTRL_CFS_LOAD TOOL={tool} ATTEMPT=1\n'
         '  _KCTRL_CFS_LOAD TOOL={tool} ATTEMPT=2\n',
         '  # MATERIAL already required a loaded head. A later sensor loss must\n'
         '  # refuse below, never re-enter a loader on the retained branch.\n'),
        ('  # Thermal state of the reference. Nothing can ooze onto it: the toolhead is\n'
         '  # still empty at this point, the CFS material step comes after the homing.\n',
         '  # Fresh manual nozzle cleaning is required, including with retained filament.\n'
         '  # Probe at the contact temperature before any loading or retained purge.\n'),
    )
    for before, after in replacements:
        if base.count(before) != 1:
            raise ValueError('installed_start_anchor_changed: ' + before.splitlines()[0])
        base = base.replace(before, after)
    return base
