#!/usr/bin/env python3
"""Adaptateur minimal vers le transport `serial_485` déjà présent sur la K1.

Ce fichier n'ouvre aucun port, ne se connecte à rien et n'enregistre aucune
commande. Il fixe seulement l'appel exact qualifié par le source officiel
`auto_addr_wrapper.py`: `cmd_send_data_with_response(frame, timeout, False)`.
"""

from __future__ import annotations


class TransportAdapterError(ValueError):
    pass


class StockSerial485Transport:
    def __init__(self, serial_object):
        if serial_object is None or not hasattr(
            serial_object, "cmd_send_data_with_response"
        ):
            raise TransportAdapterError("serial_485_interface_missing")
        self.serial_object = serial_object

    def send(self, frame: bytes, timeout_s: float, retry: bool = False):
        frame = bytes(frame)
        if retry:
            raise TransportAdapterError("transport_retry_forbidden")
        if len(frame) < 4 or frame[1] != len(frame) - 1:
            raise TransportAdapterError("application_frame_invalid")
        timeout_s = float(timeout_s)
        if not 0.05 <= timeout_s <= 150.0:
            raise TransportAdapterError("timeout_out_of_bounds")
        response = self.serial_object.cmd_send_data_with_response(
            frame, timeout_s, False
        )
        if response is None:
            return None
        return bytes(response)
