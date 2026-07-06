"""Liaison Bluetooth (RFCOMM) entre le Raspberry Pi et l'ESP32 qui pilote le gant
pneumatique.

L'ESP32 (hardware + firmware, cablage de la pompe) est gere par Cecile. Notre role
(Fork 1) se limite a envoyer la bonne commande au bon moment.

Protocole propose (a valider avec Cecile) : lignes ASCII terminees par "\n" :
    "FERMER" -> fermer/serrer le gant
    "OUVRIR" -> ouvrir/relacher le gant
    "PING"   -> signal de vie, pour un eventuel watchdog cote ESP32

Avant la premiere utilisation, appairer l'ESP32 avec le Pi (une seule fois) :
    bluetoothctl
    > scan on
    > pair <MAC_ESP32>
    > trust <MAC_ESP32>
    > quit
"""
import socket
import threading
import time

RFCOMM_CHANNEL = 1
KEEPALIVE_INTERVAL_S = 1.0


class GantLink:
    def __init__(self, mac_address):
        self.mac_address = mac_address
        self.sock = None
        self._stop_keepalive = threading.Event()
        self._keepalive_thread = None

    def connect(self):
        self.sock = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_STREAM, socket.BTPROTO_RFCOMM)
        self.sock.connect((self.mac_address, RFCOMM_CHANNEL))
        self._stop_keepalive.clear()
        self._keepalive_thread = threading.Thread(target=self._keepalive_loop, daemon=True)
        self._keepalive_thread.start()
        print(f"[BT] Connecte a l'ESP32 ({self.mac_address})")

    def _send_line(self, line):
        self.sock.send((line + "\n").encode("utf-8"))

    def _keepalive_loop(self):
        while not self._stop_keepalive.is_set():
            try:
                self._send_line("PING")
            except OSError:
                break
            time.sleep(KEEPALIVE_INTERVAL_S)

    def open_glove(self):
        self._send_line("OUVRIR")
        print("[ACTION] Commande envoyee a l'ESP32 : OUVRIR")

    def close_glove(self):
        self._send_line("FERMER")
        print("[ACTION] Commande envoyee a l'ESP32 : FERMER")

    def close(self):
        self._stop_keepalive.set()
        if self._keepalive_thread:
            self._keepalive_thread.join(timeout=2)
        if self.sock:
            self.sock.close()
