; K1-CONTROL-V1 CONTRACT=1
; The begin/end pair owns the requested target around the stock CFS boundary.
KCTRL_TOOL_CHANGE_BEGIN CONTRACT=1 PREVIOUS={previous_extruder} NEXT={next_extruder} OLD_TARGET={old_filament_temp} NEXT_TARGET={new_filament_temp} FLUSH_MM={flush_length} Z={toolchange_z}
T{next_extruder}
KCTRL_TOOL_CHANGE_END CONTRACT=1 NEXT={next_extruder} NEXT_TARGET={new_filament_temp}
