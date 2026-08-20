"use strict";

export class SimulatedMoonrakerAdapter {
  constructor(fetchImplementation = window.fetch.bind(window)) {
    this.fetch = fetchImplementation;
  }

  async connect() {
    const info = await this.#request("/server/info");
    if (info.result?.moonraker_version !== "simulation-k1-control-v1") {
      throw new Error("K1 Control refuse une API qui n'est pas le faux Moonraker local.");
    }
    return this.readState();
  }

  async readState() {
    const payload = await this.#request("/printer/objects/query?k1_control");
    const state = payload.result?.status?.k1_control;
    if (!state?.simulation) {
      throw new Error("Le faux état K1 Control est absent.");
    }
    return state;
  }

  async command(script) {
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
      throw new Error(payload.error?.message ?? `Faux Moonraker indisponible (${response.status}).`);
    }
    return payload;
  }
}
