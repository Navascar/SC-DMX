"""DMX-виходи: Enttec DMX USB Pro, Open DMX (FTDI/RS-485), Art-Net, sACN (E1.31).

Кожен вихід працює у власному потоці й безперервно (або за зміною + keepalive)
відправляє останній кадр із 512 каналів.
"""
from __future__ import annotations

import logging
import socket
import struct
import threading
import time
import uuid

log = logging.getLogger(__name__)

DMX_CHANNELS = 512


# ---------------------------------------------------------------- пакети ----

def enttec_pro_packet(data: bytes) -> bytes:
    """Кадр "Output Only Send DMX" (label 6) для Enttec DMX USB Pro."""
    payload = b"\x00" + bytes(data[:DMX_CHANNELS])  # start code 0
    n = len(payload)
    return bytes([0x7E, 6, n & 0xFF, n >> 8]) + payload + b"\xE7"


def artnet_packet(data: bytes, universe: int, sequence: int = 0) -> bytes:
    """Пакет ArtDmx. universe — 15-бітна Port-Address (Net:SubNet:Universe)."""
    payload = bytes(data[:DMX_CHANNELS])
    if len(payload) % 2:
        payload += b"\x00"  # довжина має бути парною
    return (
        b"Art-Net\x00"
        + struct.pack("<H", 0x5000)          # OpCode ArtDmx
        + struct.pack(">H", 14)              # ProtVer
        + bytes([sequence & 0xFF, 0])        # Sequence, Physical
        + bytes([universe & 0xFF, (universe >> 8) & 0x7F])  # SubUni, Net
        + struct.pack(">H", len(payload))
        + payload
    )


def sacn_packet(data: bytes, universe: int, sequence: int, cid: bytes,
                source_name: str = "DMX RGB Controller", priority: int = 100) -> bytes:
    """Пакет даних E1.31 (sACN) з повним набором із 512 слотів."""
    slots = b"\x00" + bytes(data[:DMX_CHANNELS]).ljust(DMX_CHANNELS, b"\x00")
    dmp = (
        struct.pack(">H", 0x7000 | (10 + len(slots)))
        + b"\x02\xa1"
        + struct.pack(">HHH", 0, 1, len(slots))
        + slots
    )
    name = source_name.encode("utf-8")[:63].ljust(64, b"\x00")
    framing_body = (
        struct.pack(">I", 0x00000002)
        + name
        + bytes([priority & 0xFF])
        + struct.pack(">H", 0)                # synchronization address
        + bytes([sequence & 0xFF, 0])         # sequence, options
        + struct.pack(">H", universe)
    )
    framing = struct.pack(">H", 0x7000 | (2 + len(framing_body) + len(dmp))) + framing_body + dmp
    root_body = struct.pack(">I", 0x00000004) + cid
    root = struct.pack(">H", 0x7000 | (2 + len(root_body) + len(framing))) + root_body + framing
    return struct.pack(">HH", 0x0010, 0x0000) + b"ASC-E1.17\x00\x00\x00" + root


def sacn_multicast_address(universe: int) -> str:
    return f"239.255.{(universe >> 8) & 0xFF}.{universe & 0xFF}"


# ---------------------------------------------------------------- виходи ----

class Output:
    """Базовий вихід. Тримає поточний кадр і крутить потік відправки."""

    kind = "none"
    refresh_hz = 40.0
    keepalive_s: float | None = None  # None — слати кожен такт

    def __init__(self, **params):
        self.params = params
        self._frame = bytes(DMX_CHANNELS)
        self._lock = threading.Lock()
        self._changed = threading.Event()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.status = "зупинено"
        self.ok = False
        self.frames_sent = 0

    # --- API для рушія
    def set_frame(self, frame: bytes) -> None:
        with self._lock:
            if frame != self._frame:
                self._frame = bytes(frame)
                self._changed.set()

    def start(self) -> None:
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name=f"dmx-{self.kind}", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._changed.set()
        if self._thread:
            self._thread.join(timeout=2)
        self.close()
        self.ok = False
        self.status = "зупинено"

    def info(self) -> dict:
        return {"type": self.kind, "ok": self.ok, "status": self.status,
                "frames": self.frames_sent, "params": self.params}

    # --- для нащадків
    def open(self) -> None:
        pass

    def close(self) -> None:
        pass

    def send(self, frame: bytes) -> None:
        pass

    # --- потік
    def _run(self) -> None:
        period = 1.0 / self.refresh_hz
        last_send = 0.0
        while not self._stop.is_set():
            if not self.ok:
                try:
                    self.open()
                    self.ok = True
                    self.status = "працює"
                    log.info("Вихід %s відкрито", self.kind)
                except Exception as exc:  # noqa: BLE001
                    status = f"помилка: {exc}"
                    if status != self.status:  # не засмічуємо журнал однаковими повідомленнями
                        log.warning("Не вдалося відкрити %s: %s", self.kind, exc)
                    self.status = status
                    self._stop.wait(2.0)
                    continue
            if self.keepalive_s is None:
                self._stop.wait(period)
            else:
                self._changed.wait(self.keepalive_s)
                time.sleep(max(0.0, period - (time.monotonic() - last_send)))
            self._changed.clear()
            with self._lock:
                frame = self._frame
            try:
                self.send(frame)
                self.frames_sent += 1
                last_send = time.monotonic()
            except Exception as exc:  # noqa: BLE001
                self.status = f"помилка: {exc}"
                log.warning("Помилка відправки %s: %s", self.kind, exc)
                self.ok = False
                try:
                    self.close()
                except Exception:  # noqa: BLE001
                    pass


class NullOutput(Output):
    """Симулятор: нічого нікуди не шле, корисно для налаштування без обладнання."""
    kind = "none"

    def open(self) -> None:
        self.status = "симуляція"

    def info(self) -> dict:
        d = super().info()
        if self.ok:
            d["status"] = "симуляція (без обладнання)"
        return d


class EnttecProOutput(Output):
    kind = "enttec_pro"

    def open(self) -> None:
        import serial
        self.ser = serial.Serial(self.params.get("port", ""), baudrate=57600, timeout=1)

    def close(self) -> None:
        ser = getattr(self, "ser", None)
        if ser:
            ser.close()
            self.ser = None

    def send(self, frame: bytes) -> None:
        self.ser.write(enttec_pro_packet(frame))


class OpenDmxOutput(Output):
    """Enttec Open DMX / будь-який USB-RS485 адаптер (FTDI). Break формується програмно."""
    kind = "open_dmx"
    refresh_hz = 30.0

    def open(self) -> None:
        import serial
        self.ser = serial.Serial(self.params.get("port", ""), baudrate=250000,
                                 bytesize=8, parity="N", stopbits=2, timeout=1)

    def close(self) -> None:
        ser = getattr(self, "ser", None)
        if ser:
            ser.close()
            self.ser = None

    def send(self, frame: bytes) -> None:
        self.ser.break_condition = True
        time.sleep(0.000176)   # break ≥ 88 мкс
        self.ser.break_condition = False
        time.sleep(0.000012)   # MAB ≥ 8 мкс
        self.ser.write(b"\x00" + bytes(frame))
        self.ser.flush()


class ArtNetOutput(Output):
    kind = "artnet"
    keepalive_s = 1.0

    def open(self) -> None:
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self.addr = (self.params.get("host") or "255.255.255.255", int(self.params.get("port", 6454)))
        self.seq = 0

    def close(self) -> None:
        sock = getattr(self, "sock", None)
        if sock:
            sock.close()
            self.sock = None

    def send(self, frame: bytes) -> None:
        self.seq = self.seq % 255 + 1  # 0 вимикає перевірку послідовності, тому 1..255
        self.sock.sendto(artnet_packet(frame, int(self.params.get("universe", 0)), self.seq), self.addr)


class SacnOutput(Output):
    kind = "sacn"
    keepalive_s = 1.0

    def open(self) -> None:
        universe = int(self.params.get("universe", 1))
        if not 1 <= universe <= 63999:
            raise ValueError("всесвіт sACN має бути 1..63999")
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 8)
        host = self.params.get("host") or sacn_multicast_address(universe)
        self.addr = (host, 5568)
        self.universe = universe
        self.cid = uuid.uuid4().bytes
        self.seq = 0

    def close(self) -> None:
        sock = getattr(self, "sock", None)
        if sock:
            sock.close()
            self.sock = None

    def send(self, frame: bytes) -> None:
        self.seq = (self.seq + 1) & 0xFF
        self.sock.sendto(sacn_packet(frame, self.universe, self.seq, self.cid), self.addr)


# ------------------------------------------------------------------ uDMX ----
# Anyma uDMX та клони: USB-пристрій без COM-порту, керується vendor control
# transfer-ами через libusb (як у QLC+ та офіційній утиліті uDMX).
UDMX_VID = 0x16C0
UDMX_PID = 0x05DC
UDMX_SET_CHANNEL_RANGE = 2   # bRequest: wValue = к-сть каналів, wIndex = перший канал (з 0)
UDMX_REQUEST_TYPE = 0x40     # vendor | device | host-to-device


def _usb_backends() -> list:
    """Доступні бекенди libusb: вбудований у libusb-package, потім системні."""
    backends = []
    try:
        import libusb_package
        be = libusb_package.get_libusb1_backend()
        if be is not None:
            backends.append(("libusb-1.0 (вбудований)", be))
    except Exception:  # noqa: BLE001
        pass
    try:
        import usb.backend.libusb1 as l1
        be = l1.get_backend()
        if be is not None:
            backends.append(("libusb-1.0 (системний)", be))
    except Exception:  # noqa: BLE001
        pass
    try:
        import usb.backend.libusb0 as l0
        be = l0.get_backend()
        if be is not None:
            backends.append(("libusb-win32 / libusb0", be))
    except Exception:  # noqa: BLE001
        pass
    return backends


def _usb_string(dev, attr: str) -> str:
    try:
        return getattr(dev, attr) or ""
    except Exception:  # noqa: BLE001 — без прав/драйвера рядок не прочитати
        return ""


def find_udmx_devices() -> list[dict]:
    """Список знайдених uDMX: [{backend, bus, address, product, serial, dev}]."""
    try:
        import usb.core
    except ImportError as exc:
        raise RuntimeError("не встановлено pyusb (pip install -r requirements.txt)") from exc
    found, seen = [], set()
    for name, backend in _usb_backends():
        try:
            devices = list(usb.core.find(find_all=True, idVendor=UDMX_VID,
                                         idProduct=UDMX_PID, backend=backend))
        except Exception:  # noqa: BLE001
            continue
        for dev in devices:
            key = (dev.bus, dev.address)
            if key in seen:
                continue
            product = _usb_string(dev, "product")
            # VID/PID 16C0:05DC спільний для багатьох саморобних пристроїв V-USB
            if product and "udmx" not in product.lower():
                continue
            seen.add(key)
            found.append({"backend": name, "bus": dev.bus, "address": dev.address,
                          "product": product or "uDMX", "serial": _usb_string(dev, "serial_number"),
                          "dev": dev})
    return found


class UDmxOutput(Output):
    kind = "udmx"
    refresh_hz = 30.0
    # Шлемо кадр безперервно (~30/с), як QLC+. Багато клонів uDMX передають DMX лише
    # після запису по USB, а дешеві прилади (зокрема LED-бари) ігнорують одиночні
    # кадри й рідкий сигнал — колір тоді змінювався лише під час руху повзунка.
    keepalive_s = None

    def open(self) -> None:
        if not _usb_backends():
            raise RuntimeError("не знайдено бібліотеку libusb (pip install libusb-package)")
        devices = find_udmx_devices()
        if not devices:
            raise RuntimeError("uDMX не знайдено — перевірте підключення і драйвер (Zadig → WinUSB)")
        idx = int(self.params.get("index", 0) or 0)
        info = devices[min(idx, len(devices) - 1)]
        self.dev = info["dev"]
        try:
            self.dev.set_configuration()
        except Exception:  # noqa: BLE001 — на деяких драйверах вже налаштовано
            pass
        # пробна відправка: якщо драйвер не той, помилка буде тут, а не в циклі
        self.send(bytes(DMX_CHANNELS))
        self.device_name = f"{info['product']} (USB {info['bus']}:{info['address']}, {info['backend']})"

    def close(self) -> None:
        dev = getattr(self, "dev", None)
        if dev is not None:
            try:
                import usb.util
                usb.util.dispose_resources(dev)
            except Exception:  # noqa: BLE001
                pass
            self.dev = None

    def send(self, frame: bytes) -> None:
        data = bytes(frame[:DMX_CHANNELS]).ljust(DMX_CHANNELS, b"\x00")
        written = self.dev.ctrl_transfer(UDMX_REQUEST_TYPE, UDMX_SET_CHANNEL_RANGE,
                                         len(data), 0, data, timeout=500)
        if written != len(data):
            raise IOError(f"uDMX прийняв {written} з {len(data)} байт")

    def info(self) -> dict:
        d = super().info()
        if self.ok and getattr(self, "device_name", None):
            d["status"] = "працює: " + self.device_name
        return d


OUTPUT_TYPES = {cls.kind: cls for cls in
                (UDmxOutput, EnttecProOutput, OpenDmxOutput, ArtNetOutput, SacnOutput, NullOutput)}


def create_output(cfg: dict) -> Output:
    cfg = dict(cfg or {})
    kind = cfg.pop("type", "none")
    cls = OUTPUT_TYPES.get(kind, NullOutput)
    return cls(**cfg)


def list_serial_ports() -> list[dict]:
    try:
        from serial.tools import list_ports
    except ImportError:
        return []
    return [{"device": p.device, "description": p.description or ""} for p in list_ports.comports()]
