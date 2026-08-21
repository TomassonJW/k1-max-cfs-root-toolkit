; K1-CONTROL-V1 CONTRACT=1
; OFFLINE CANDIDATE - NEVER IMPORT WITHOUT THE MATCHING NAMED G4 GO
; plate_name must be a stable token such as PEI_TEXTURED_A.
KCTRL_JOB_BEGIN CONTRACT=1 MODE=PRODUCTION PLATE=[plate_name] BED={bed_temperature_initial_layer_single} INITIAL_TOOL={initial_no_support_extruder} INITIAL_NOZZLE={first_layer_temperature[initial_no_support_extruder]} MESH_POLICY=AUTO MESH_MIN={first_layer_print_min[0]},{first_layer_print_min[1]} MESH_MAX={first_layer_print_max[0]},{first_layer_print_max[1]} CLEANING=AUTO PURGE=AUTO
{if num_extruders > 0 and is_extruder_used[0]}KCTRL_JOB_TOOL_TARGET CONTRACT=1 TOOL=0 TEMP={first_layer_temperature[0]}
{endif}{if num_extruders > 1 and is_extruder_used[1]}KCTRL_JOB_TOOL_TARGET CONTRACT=1 TOOL=1 TEMP={first_layer_temperature[1]}
{endif}{if num_extruders > 2 and is_extruder_used[2]}KCTRL_JOB_TOOL_TARGET CONTRACT=1 TOOL=2 TEMP={first_layer_temperature[2]}
{endif}{if num_extruders > 3 and is_extruder_used[3]}KCTRL_JOB_TOOL_TARGET CONTRACT=1 TOOL=3 TEMP={first_layer_temperature[3]}
{endif}{if num_extruders > 4 and is_extruder_used[4]}KCTRL_JOB_TOOL_TARGET CONTRACT=1 TOOL=4 TEMP={first_layer_temperature[4]}
{endif}{if num_extruders > 5 and is_extruder_used[5]}KCTRL_JOB_TOOL_TARGET CONTRACT=1 TOOL=5 TEMP={first_layer_temperature[5]}
{endif}{if num_extruders > 6 and is_extruder_used[6]}KCTRL_JOB_TOOL_TARGET CONTRACT=1 TOOL=6 TEMP={first_layer_temperature[6]}
{endif}{if num_extruders > 7 and is_extruder_used[7]}KCTRL_JOB_TOOL_TARGET CONTRACT=1 TOOL=7 TEMP={first_layer_temperature[7]}
{endif}KCTRL_JOB_START CONTRACT=1
