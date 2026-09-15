"""Garde du bus RS-485 : 300 ms de silence apres une reponse finie par 0xF7
(document 80, remede 3). Le module est charge avec un faux serial_485_wrapper,
comme Klipper le chargerait dans son paquet extras.
"""

import importlib.util
import sys
import threading
import time
import types
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SHIM = ROOT / "packages" / "k1-control-v1" / "cfs-bus-guard-v1" / "serial_485.py"


class FakeWrapper:
    def __init__(self, config):
        self.config = config
        self.calls = []
        self.responses = []

    def cmd_send_data_with_response(self, data, timeout, flag):
        self.calls.append((time.monotonic(), data, timeout, flag))
        return self.responses.pop(0) if self.responses else None


class FakeReactor:
    def __init__(self):
        self.pauses = []

    def monotonic(self):
        return time.monotonic()

    def pause(self, until):
        self.pauses.append(until)
        wait = until - time.monotonic()
        if wait > 0:
            time.sleep(wait)


class FakePrinter:
    def __init__(self):
        self.reactor = FakeReactor()

    def get_reactor(self):
        return self.reactor


class FakeConfig:
    def __init__(self):
        self.printer = FakePrinter()

    def get_printer(self):
        return self.printer


def load_shim():
    package = types.ModuleType("kctrl_extras")
    package.__path__ = []
    wrapper = types.ModuleType("kctrl_extras.serial_485_wrapper")
    wrapper.Serial_485_Wrapper = FakeWrapper
    sys.modules["kctrl_extras"] = package
    sys.modules["kctrl_extras.serial_485_wrapper"] = wrapper
    spec = importlib.util.spec_from_file_location("kctrl_extras.serial_485", SHIM)
    module = importlib.util.module_from_spec(spec)
    sys.modules["kctrl_extras.serial_485"] = module
    spec.loader.exec_module(module)
    return module


class BusGuardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.shim = load_shim()

    def guard(self):
        return self.shim.load_config_prefix(FakeConfig())

    def test_dernier_octet_quelle_que_soit_la_forme(self):
        last_byte = self.shim.last_byte
        self.assertEqual(last_byte(b"\xf7\x01\x07\x00\x0a\x01\xf7"), 0xF7)
        self.assertEqual(last_byte(bytearray(b"\xf7\x01\xfe")), 0xFE)
        self.assertEqual(last_byte([0xF7, 0x01, 0xCF]), 0xCF)
        self.assertEqual(last_byte({"#msgid": 7, "#msg": b"\xf7\x02\xf7"}), 0xF7)
        self.assertEqual(last_byte(types.SimpleNamespace(msg=[0xF7, 0x01, 0xF7])), 0xF7)
        self.assertIsNone(last_byte(None))
        self.assertIsNone(last_byte(b""))
        self.assertIsNone(last_byte({"autre": 1}))
        self.assertIsNone(last_byte(3.5))

    def test_sans_f7_aucune_garde(self):
        guard = self.guard()
        guard.responses = [b"\xf7\x01\x07\x00\x0a\x00\xfe", b"\xf7\x01\x07\x00\x0a\x00\xcf"]
        guard.cmd_send_data_with_response(b"q1", 1.0, False)
        guard.cmd_send_data_with_response(b"q2", 1.0, False)
        self.assertEqual(guard.kctrl_marked, 0)
        self.assertEqual(guard.kctrl_held, 0)
        self.assertLess(guard.calls[1][0] - guard.calls[0][0], 0.1)

    def test_apres_f7_la_question_suivante_attend_300_ms(self):
        guard = self.guard()
        guard.responses = [b"\xf7\x01\x07\x00\x0a\x01\xf7", None]
        guard.cmd_send_data_with_response(b"q1", 1.0, False)
        guard.cmd_send_data_with_response(b"q2", 1.0, False)
        self.assertEqual(guard.kctrl_marked, 1)
        self.assertEqual(guard.kctrl_held, 1)
        self.assertGreaterEqual(guard.calls[1][0] - guard.calls[0][0], 0.28)
        self.assertLess(guard.calls[1][0] - guard.calls[0][0], 0.6)
        # Fil principal : l'attente passe par le reacteur, pas par time.sleep.
        self.assertEqual(len(guard.config.printer.reactor.pauses), 1)

    def test_la_garde_expire_d_elle_meme(self):
        guard = self.guard()
        guard.responses = [b"\x01\xf7", None]
        guard.cmd_send_data_with_response(b"q1", 1.0, False)
        time.sleep(0.35)
        guard.cmd_send_data_with_response(b"q2", 1.0, False)
        self.assertEqual(guard.kctrl_held, 0)
        self.assertEqual(guard.config.printer.reactor.pauses, [])

    def test_hors_du_fil_principal_l_attente_ne_touche_pas_au_reacteur(self):
        guard = self.guard()
        guard.responses = [b"\x01\xf7", None]
        guard.cmd_send_data_with_response(b"q1", 1.0, False)

        def ask():
            guard.cmd_send_data_with_response(b"q2", 1.0, False)

        worker = threading.Thread(target=ask)
        worker.start()
        worker.join(5)
        self.assertEqual(guard.kctrl_held, 1)
        self.assertEqual(guard.config.printer.reactor.pauses, [])
        self.assertGreaterEqual(guard.calls[1][0] - guard.calls[0][0], 0.28)

    def test_la_trame_passe_telle_quelle(self):
        guard = self.guard()
        guard.responses = [b"\x01\xf7"]
        self.assertEqual(guard.cmd_send_data_with_response(b"q1", 2.5, True), b"\x01\xf7")
        self.assertEqual(guard.calls[0][1:], (b"q1", 2.5, True))


if __name__ == "__main__":
    unittest.main()
