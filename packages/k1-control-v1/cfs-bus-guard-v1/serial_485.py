# K1 Control - garde du bus RS-485 des CFS (document 80, remede 3).
#
# Remplace /usr/share/klipper/klippy/extras/serial_485.py, dont le corps stock
# tient en deux lignes :
#
#   from .serial_485_wrapper import Serial_485_Wrapper
#   def load_config_prefix(config): return(Serial_485_Wrapper(config))
#
# Ce que le journal montre (document 80, 15 septembre 2026) : le CFS 2 n'entend
# pas une question partie moins de 100 ms apres une reponse du CFS 1 dont le
# dernier octet vaut 0xF7, l'octet qui ouvre toute trame (139 questions sur 139
# perdues dans ce cas, aucune apres une autre trame). Cinq questions de suite
# sans reponse : key831, pause de l'impression.
#
# Le remede : apres toute reponse finie par 0xF7, retenir la question suivante
# 300 ms. Rien d'autre ne change ; la trame, son adresse, son delai d'attente
# restent ceux du module. Le module compile fait ses questions par
# cmd_send_data_with_response (auto_addr_wrapper.py, lisible, s'en sert
# ainsi) ; la forme exacte de la reponse retournee n'est pas documentee, donc
# last_byte accepte octets, liste d'entiers, dictionnaire portant '#msg' ou
# objet portant msg, et ne retient rien s'il ne reconnait pas la forme.
#
# L'attente respecte le fil : depuis le fil principal de Klipper, c'est
# reactor.pause (les minuteries tournent pendant ce temps) ; depuis un autre
# fil, time.sleep. Compteurs kctrl_held et kctrl_marked pour le controle.
#
# Pas installe. Installation, machine a l'arret, apres accord de Thomas :
#   cp .../serial_485.py .../serial_485.py.bak-<date> ; cat | ssh ... ;
#   /etc/init.d/S55klipper_service restart ; puis silences_cfs.py avant/apres.

import logging
import threading
import time

from .serial_485_wrapper import Serial_485_Wrapper

HOLD_S = 0.3
TAIL = 0xF7


def last_byte(response):
    """Dernier octet d'une reponse, quelle que soit sa forme, sinon None."""
    for _ in range(4):
        if response is None:
            return None
        if isinstance(response, (bytes, bytearray)):
            return response[-1] if response else None
        if isinstance(response, str):
            return ord(response[-1]) & 0xFF if response else None
        if isinstance(response, (list, tuple)):
            if not response:
                return None
            tail = response[-1]
            if isinstance(tail, int):
                return tail & 0xFF
            response = tail
            continue
        if isinstance(response, dict):
            for key in ("#msg", "msg", "data", "response"):
                if key in response:
                    response = response[key]
                    break
            else:
                return None
            continue
        message = getattr(response, "msg", None)
        if message is None:
            return None
        response = message
    return None


class KctrlSerial485(Serial_485_Wrapper):
    def __init__(self, config):
        Serial_485_Wrapper.__init__(self, config)
        self.kctrl_reactor = config.get_printer().get_reactor()
        self.kctrl_hold_until = 0.0
        self.kctrl_held = 0
        self.kctrl_marked = 0
        logging.info("kctrl serial_485: garde de %d ms apres une reponse finie par 0x%02X",
                     int(HOLD_S * 1000), TAIL)

    def kctrl_wait(self):
        """Attend la fin de la garde en cours ; rend le temps attendu."""
        wait = self.kctrl_hold_until - time.monotonic()
        if wait <= 0.0:
            return 0.0
        wait = min(wait, HOLD_S)
        self.kctrl_held += 1
        if threading.current_thread() is threading.main_thread():
            now = self.kctrl_reactor.monotonic()
            self.kctrl_reactor.pause(now + wait)
        else:
            time.sleep(wait)
        return wait

    def kctrl_note(self, response):
        """Ouvre une garde si la reponse finit par l'octet d'ouverture de trame."""
        if last_byte(response) == TAIL:
            self.kctrl_marked += 1
            self.kctrl_hold_until = time.monotonic() + HOLD_S

    def cmd_send_data_with_response(self, *args, **kwargs):
        self.kctrl_wait()
        response = Serial_485_Wrapper.cmd_send_data_with_response(self, *args, **kwargs)
        self.kctrl_note(response)
        return response


def load_config_prefix(config):
    return KctrlSerial485(config)
