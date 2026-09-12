// The stand-alone page at /bobines/: the same interface as the window that
// overlay.js opens inside Mainsail, mounted on the document itself. Useful
// from a phone, from Fluidd, or when Mainsail is not open.
import { mount } from "./bobines.js";

mount(document, { overlay: false });
