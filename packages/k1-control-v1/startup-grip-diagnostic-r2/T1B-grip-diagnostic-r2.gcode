; K1 Control - first grip observed; external stop before stock retry required
; No model: existing qualified start/prime only, then lifted pause.
START_PRINT EXTRUDER_TEMP=200 BED_TEMP=55
M400
G91
G1 Z5 F600
G90
G1 X150 Y150 F6000
M400
PAUSE POST_WORK=0
; Operator verifies camera + route; RESUME_BASE returns to this same position.
END_PRINT
; CONFIG_BLOCK_START
; nozzle_temperature = 200
; nozzle_temperature_initial_layer = 200
; filament_type = PLA
; filament_colour = #000000
; filament_settings_id = Generic PLA
; initial_layer_print_height = 0.2
; layer_height = 0.2
; CONFIG_BLOCK_END
