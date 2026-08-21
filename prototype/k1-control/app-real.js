"use strict";

import {RealMoonrakerAdapter} from "./real-moonraker-adapter.js";
import {createK1ControlUi} from "./ui-controller.js";

const ui = createK1ControlUi(new RealMoonrakerAdapter());
ui.start().catch((error) => {
  const card = document.getElementById("readiness-card");
  document.getElementById("readiness-title").textContent = "K1 Control indisponible";
  document.getElementById("readiness-detail").textContent = error.message;
  card.classList.add("blocked");
});
