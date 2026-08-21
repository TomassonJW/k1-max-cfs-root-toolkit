"use strict";

const BASE_OBJECTS = ["bed_mesh", "extruder", "gcode_move", "heater_bed", "print_stats", "toolhead"];
const RUNTIME_OBJECT = "gcode_macro K1_CONTROL_STATE";
const NUMBER = "-?(?:\\d+(?:\\.\\d+)?|\\.\\d+)";
const POSITIVE_INTEGER = "[1-9]\\d*";
const NON_NEGATIVE_INTEGER = "(?:0|[1-9]\\d*)";
const EXACT_COMMANDS = new Set([
  "K1_Z_CANCEL",
  "K1_Z_RESTORE_PREVIOUS",
  "K1_Z_INVALIDATE",
  "K1_CALIBRATION_HOME",
  "K1_MESH_CLEAR_ACTIVE",
]);
const COMMAND_PATTERNS = [
  new RegExp(`^K1_Z_SESSION_START SEED=${NUMBER} PLATE=${POSITIVE_INTEGER} TEMP_BAND=${NON_NEGATIVE_INTEGER} PROBE_REV=${POSITIVE_INTEGER} NOZZLE_ID=${POSITIVE_INTEGER} CONFIG_ID=${POSITIVE_INTEGER}$`),
  new RegExp(`^K1_Z_COMMIT ACCEPTED_AT=${POSITIVE_INTEGER}$`),
  /^K1_Z_ADJUST DELTA=(?:-0\.1|-0\.05|-0\.01|-0\.005|0\.005|0\.01|0\.05|0\.1)$/,
  new RegExp(`^K1_CALIBRATION_PREHEAT BED_TEMP=${NUMBER} NOZZLE_TEMP=${NUMBER} SOAK_SECONDS=${NON_NEGATIVE_INTEGER}$`),
  new RegExp(`^K1_MESH_CALIBRATE X_COUNT=${POSITIVE_INTEGER} Y_COUNT=${POSITIVE_INTEGER} ALGORITHM=(?:lagrange|bicubic)$`),
  new RegExp(`^K1_MESH_COMMIT PLATE=${POSITIVE_INTEGER} TEMP_BAND=${NON_NEGATIVE_INTEGER} PROBE_REV=${POSITIVE_INTEGER} X_COUNT=${POSITIVE_INTEGER} Y_COUNT=${POSITIVE_INTEGER}$`),
];

function finiteNumber(value, fallback = 0) {
  const number = Number(value);
  return Number.isFinite(number) ? number : fallback;
}

function meshQuality(mesh) {
  const matrix = mesh?.probed_matrix;
  if (!Array.isArray(matrix) || matrix.length === 0 || !Array.isArray(matrix[0])) {
    return "Aucune matrice mesurée";
  }
  const values = matrix.flat().map(Number).filter(Number.isFinite);
  if (values.length === 0) return "Matrice illisible";
  const range = Math.max(...values) - Math.min(...values);
  return `${matrix[0].length}×${matrix.length} · amplitude ${range.toFixed(3).replace(".", ",")} mm`;
}

function sequence(armed) {
  const stages = [
    "Contrat du travail",
    "Stabilisation thermique",
    "Référence grossière",
    "Nettoyage contrôlé",
    "Référence Z finale",
    "Mesh qualifié",
    "Correction Z acceptée",
    "Garde mouvements bas",
    "CFS et purge",
    "Impression",
  ];
  return stages.map((label, index) => ({
    id: `stage-${index + 1}`,
    label,
    status: armed ? "done" : "locked",
  }));
}

export class RealMoonrakerAdapter {
  constructor(fetchImplementation = window.fetch.bind(window)) {
    this.fetch = fetchImplementation;
    this.availableObjects = new Set();
    this.runtimeAvailable = false;
  }

  async connect() {
    const info = await this.#request("/server/info");
    if (info.result?.klippy_state !== "ready") {
      throw new Error(`Klipper n'est pas prêt (${info.result?.klippy_state ?? "état inconnu"}).`);
    }
    const objects = await this.#request("/printer/objects/list");
    this.availableObjects = new Set(objects.result?.objects ?? []);
    const missing = BASE_OBJECTS.filter((name) => !this.availableObjects.has(name));
    if (missing.length > 0) {
      throw new Error(`Moonraker ne fournit pas les objets requis : ${missing.join(", ")}.`);
    }
    this.runtimeAvailable = this.availableObjects.has(RUNTIME_OBJECT);
    return this.readState();
  }

  async readState() {
    const objectNames = [...BASE_OBJECTS];
    if (this.runtimeAvailable) objectNames.push(RUNTIME_OBJECT);
    const query = objectNames.map((name) => encodeURIComponent(name)).join("&");
    const payload = await this.#request(`/printer/objects/query?${query}`);
    const status = payload.result?.status ?? {};
    const runtime = status[RUNTIME_OBJECT] ?? {};
    const mesh = status.bed_mesh ?? {};
    const origin = status.gcode_move?.homing_origin ?? [0, 0, 0, 0];
    const sessionActive = finiteNumber(runtime.session_active) === 1;
    const accepted = finiteNumber(runtime.accepted_z_valid) === 1;
    const armed = finiteNumber(runtime.low_moves_armed) === 1;
    const profileName = mesh.profile_name || "Aucun";

    return {
      simulation: false,
      commandsAvailable: this.runtimeAvailable,
      ready: this.runtimeAvailable && finiteNumber(runtime.ready) === 1 && accepted && armed,
      blockReason: this.runtimeAvailable
        ? runtime.block_reason || "Le runtime K1 Control refuse ce contexte."
        : "Runtime K1 Control non installé : observation seulement, commandes bloquées.",
      connection: "Moonraker réel · lecture seule par défaut",
      plate: {
        id: finiteNumber(runtime.plate_id),
        label: runtime.plate_id || "Plaque non sélectionnée",
        temperatureBandC: finiteNumber(runtime.temperature_band_c),
        bedTargetC: finiteNumber(status.heater_bed?.target),
      },
      calibration: {
        offsetMm: accepted ? finiteNumber(runtime.accepted_z_offset) : finiteNumber(origin[2]),
        provisionalSeedMm: accepted ? finiteNumber(runtime.accepted_z_offset) : finiteNumber(origin[2]),
        status: accepted ? "accepted" : "invalid",
        nozzleId: finiteNumber(runtime.nozzle_id),
        nozzle: runtime.nozzle_id || "Buse non qualifiée",
        probeRevision: finiteNumber(runtime.probe_revision),
        configId: finiteNumber(runtime.config_id),
        storeIntegrity: runtime.store_integrity || "unknown",
        recoveryAvailable: finiteNumber(runtime.recovery_available) === 1,
        canRestore: finiteNumber(runtime.previous_z_valid) === 1,
        session: sessionActive
          ? {currentOffsetMm: finiteNumber(runtime.session_z_offset)}
          : null,
      },
      mesh: {
        mode: runtime.mesh_mode || "reference",
        referenceProfile: profileName,
        persistAfterJob: finiteNumber(runtime.mesh_persisted) === 1,
        quality: meshQuality(mesh),
      },
      temperature: {
        owner: runtime.temperature_owner || "Non qualifié",
        expectedNozzleC: finiteNumber(runtime.expected_nozzle_c, finiteNumber(status.extruder?.target)),
        actualNozzleC: finiteNumber(status.extruder?.temperature),
        initialTool: runtime.initial_tool || "—",
        activeCfs: runtime.active_cfs || "—",
        nextToolTargetC: finiteNumber(runtime.next_tool_target_c),
      },
      sequence: sequence(armed),
      events: [
        this.runtimeAvailable
          ? "Runtime K1 Control détecté ; seules les macros autorisées peuvent être appelées."
          : "Fondation détectée, mais macros K1 Control absentes : aucune commande n'est possible.",
        `Mesh actif : ${profileName}.`,
        `État d'impression : ${status.print_stats?.state ?? "inconnu"}.`,
      ],
    };
  }

  async command(script) {
    if (!this.runtimeAvailable) {
      throw new Error("Commande refusée : le runtime K1 Control sécurisé n'est pas installé.");
    }
    if (!EXACT_COMMANDS.has(script) && !COMMAND_PATTERNS.some((pattern) => pattern.test(script))) {
      throw new Error("Commande refusée par la liste blanche K1 Control.");
    }
    await this.#request("/printer/gcode/script", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({script}),
    });
    return this.readState();
  }

  async #request(path, options = {}) {
    const response = await this.fetch(path, {cache: "no-store", ...options});
    const payload = await response.json();
    if (!response.ok || payload.error) {
      throw new Error(payload.error?.message ?? `Moonraker indisponible (${response.status}).`);
    }
    return payload;
  }
}
