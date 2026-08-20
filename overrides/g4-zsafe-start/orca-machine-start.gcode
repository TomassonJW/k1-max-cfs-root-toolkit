START_PRINT EXTRUDER_TEMP=[nozzle_temperature_initial_layer] BED_TEMP=[bed_temperature_initial_layer_single] INITIAL_TOOL=[initial_no_support_extruder] Z_CORRECTION=0.27
M104 S[nozzle_temperature_initial_layer]
M109 S[nozzle_temperature_initial_layer]
M204 S2000
G1 Z3 F600
M83
G92 E0
G1 Z1 F600
