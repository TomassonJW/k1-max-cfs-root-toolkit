# Z-offset diagnostic protocol

## Question

Is the bad first layer caused primarily by:

1. poor measurement repeatability;
2. a deterministic software reset or recalculation after a good measurement;
3. thermal state differences;
4. nozzle contamination or contact conditions;
5. a combination of these mechanisms?

The bed springs are not the default hypothesis: the same defect existed before and after their installation.

## Phase A — Static evidence from configuration

Without modifying the printer, identify every occurrence and caller of mechanisms such as:

- `SET_GCODE_OFFSET`;
- `G92` involving Z;
- `G28` and proprietary rough/accurate homing wrappers;
- probe or pressure-touch configuration;
- bed levelling and mesh commands;
- mesh load, clear and save operations;
- persistent variable reads/writes;
- `SAVE_CONFIG` or generated configuration;
- startup macros and Creality service-triggered calibration;
- commands that run after the slicer's visible `START_PRINT` call.

Produce:

- include graph;
- macro call graph;
- timeline of all potential Z-reference writers;
- list of values that persist across restart and those that do not.

## Phase B — Compare identical executions

Use one unchanged G-code file known to exhibit the issue.

For each run record:

- printer boot state and elapsed uptime;
- plate identity and whether it was moved;
- nozzle state and cleaning method;
- bed and nozzle target/actual temperatures at each calibration stage;
- mesh generated or loaded;
- homing/calibration sequence and timestamps;
- any displayed or logged Z correction;
- first-layer result;
- manual intervention, if any.

The best evidence is two runs of the identical file with different first-layer outcomes and complete logs covering launch through the first layer.

## Phase C — Repeatability experiment

Only after the command path is understood and an operational test is explicitly approved:

- hold plate, nozzle cleanliness and thermal state constant;
- repeat the same Z measurement enough times to estimate spread;
- repeat at selected bed temperatures after thermal stabilisation;
- avoid mixing mesh regeneration, nozzle changes or mechanical work into the same series;
- record raw values rather than only pass/fail impressions.

## Interpretation

- **Tight measurement spread but changing effective offset:** prioritise software reset/order-of-operations.
- **Wide spread under constant conditions:** prioritise sensor/contact/mechanical repeatability.
- **Stable at one temperature and shifted at another:** prioritise thermal compensation and calibration temperature.
- **Shift correlated with later macro calls:** place the persistent fine correction after the final resetting operation.
- **Different result with contaminated nozzle:** treat cleaning and nozzle thermal state as part of the measurement protocol.

## Success criterion for diagnosis

The project can name the final operation that establishes effective Z, quantify repeatability under defined conditions, and explain why an adjustment is or is not preserved until the first layer.
