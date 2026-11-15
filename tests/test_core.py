import struct

import pytest

from dmxctl.effects import effect_color
from dmxctl.engine import Engine
from dmxctl.fixtures import DEFAULT_PROFILES, Fixture, find_overlaps, render_fixture, validate_fixture
from dmxctl.outputs import artnet_packet, enttec_pro_packet, sacn_multicast_address, sacn_packet


def test_enttec_pro_packet():
    data = bytes(range(256)) * 2
    p = enttec_pro_packet(data)
    assert p[:4] == bytes([0x7E, 6, 513 & 0xFF, 513 >> 8])
    assert p[4] == 0  # start code
    assert p[5:-1] == data
    assert p[-1] == 0xE7
    assert len(p) == 518


def test_artnet_packet():
    p = artnet_packet(b"\x01\x02\x03", universe=0x123, sequence=7)
    assert p[:8] == b"Art-Net\x00"
    assert struct.unpack("<H", p[8:10])[0] == 0x5000
    assert p[10:12] == b"\x00\x0e"
    assert p[12] == 7
    assert p[14] == 0x23 and p[15] == 0x01   # SubUni, Net
    assert struct.unpack(">H", p[16:18])[0] == 4  # вирівняно до парної довжини
    assert p[18:] == b"\x01\x02\x03\x00"


def test_sacn_packet_layout():
    cid = bytes(range(16))
    p = sacn_packet(bytes([9]) * 512, universe=5, sequence=3, cid=cid)
    assert len(p) == 638
    assert p[4:16] == b"ASC-E1.17\x00\x00\x00"
    assert struct.unpack(">H", p[16:18])[0] == 0x7000 | 622
    assert p[22:38] == cid
    assert struct.unpack(">H", p[38:40])[0] == 0x7000 | 600
    assert p[111] == 3                                   # sequence
    assert struct.unpack(">H", p[113:115])[0] == 5        # universe
    assert struct.unpack(">H", p[115:117])[0] == 0x7000 | 523
    assert struct.unpack(">H", p[123:125])[0] == 513
    assert p[125] == 0 and p[126:] == bytes([9]) * 512
    assert sacn_multicast_address(300) == "239.255.1.44"


def test_render_with_dimmer_channel():
    uni = bytearray(512)
    fx = Fixture(id="a", name="A", address=10, profile="Dim+RGB+Strobe (5 кан.)", r=255, g=128, b=0, dimmer=128)
    render_fixture(uni, fx, DEFAULT_PROFILES[fx.profile], fx.color(), master=1.0)
    assert list(uni[9:14]) == [128, 255, 128, 0, 0]


def test_render_without_dimmer_scales_rgb():
    uni = bytearray(512)
    fx = Fixture(id="a", name="A", address=1, profile="RGBW (4 кан.)", r=200, g=100, b=50, w=255, dimmer=255)
    render_fixture(uni, fx, DEFAULT_PROFILES[fx.profile], fx.color(), master=0.5)
    assert list(uni[0:4]) == [100, 50, 25, 128]


def test_validation_and_overlaps():
    fx = Fixture(id="a", name="A", address=510, profile="RGBW (4 кан.)")
    with pytest.raises(ValueError):
        validate_fixture(fx, DEFAULT_PROFILES)
    a = Fixture(id="a", name="A", address=1, profile="RGB (3 кан.)")
    b = Fixture(id="b", name="B", address=3, profile="RGB (3 кан.)")
    c = Fixture(id="c", name="C", address=6, profile="RGB (3 кан.)")
    assert find_overlaps([a, b, c], DEFAULT_PROFILES) == [("a", "b")]


def test_effects_return_valid_colors():
    base = {"r": 10.0, "g": 20.0, "b": 30.0, "w": 0.0, "a": 0.0, "uv": 0.0}
    for kind in ("rainbow", "fade", "chase", "pulse", "strobe", "random", "fire", "none"):
        for t in (0.0, 0.37, 5.1):
            c = effect_color({"type": kind, "speed": 1.0, "spread": 1.0, "colors": ["#ff0000", "#0000ff"]},
                             1, 4, t, base)
            assert all(0 <= c[k] <= 255.0001 for k in "rgb"), (kind, c)


def test_engine_commands_and_scene_fade(tmp_path):
    eng = Engine(tmp_path / "cfg.json")
    ids = [f.id for f in eng.fixtures]
    assert len(ids) == 4  # демо-патч
    eng.handle({"cmd": "set_color", "ids": ids[:1], "hex": "#00ff00", "dimmer": 255})
    frame = eng.render(0)
    assert list(frame[0:4]) == [255, 0, 255, 0]
    eng.handle({"cmd": "save_scene", "name": "green"})
    eng.handle({"cmd": "set_color", "ids": ids[:1], "hex": "#000000"})
    eng.handle({"cmd": "recall_scene", "name": "green", "fade": 2})
    start = eng._fade["start"]
    eng.render(start + 1)
    assert 120 <= eng.fixtures[0].g <= 135
    eng.render(start + 3)
    assert eng.fixtures[0].g == 255 and eng._fade is None

    eng.handle({"cmd": "blackout", "on": True})
    assert not any(eng.render(10))
    eng.handle({"cmd": "blackout", "on": False})

    eng.handle({"cmd": "add_fixture", "profile": "RGB (3 кан.)", "address": 100, "count": 3})
    assert [f.address for f in eng.fixtures[-3:]] == [100, 103, 106]
    with pytest.raises(ValueError):
        eng.handle({"cmd": "add_fixture", "profile": "RGB (3 кан.)", "address": 511})

    eng.save()
    again = Engine(tmp_path / "cfg.json")
    assert len(again.fixtures) == 7 and "green" in again.scenes


def test_udmx_send_uses_vendor_control_transfer():
    from dmxctl.outputs import UDmxOutput

    class FakeDev:
        calls = []

        def ctrl_transfer(self, bm, req, value, index, data, timeout):
            self.calls.append((bm, req, value, index, bytes(data)))
            return len(data)

    out = UDmxOutput()
    out.dev = FakeDev()
    out.send(bytes([1, 2, 3]))
    bm, req, value, index, data = out.dev.calls[0]
    assert (bm, req, value, index) == (0x40, 2, 512, 0)
    assert data[:3] == b"\x01\x02\x03" and len(data) == 512


def test_udmx_open_without_device_reports_clear_error():
    from dmxctl.outputs import UDmxOutput
    with pytest.raises(RuntimeError, match="uDMX"):
        UDmxOutput().open()


def test_static_color_stops_effect_and_uses_white_channel(tmp_path):
    eng = Engine(tmp_path / "cfg.json")
    eng.handle({"cmd": "add_fixture", "profile": "RGBW (4 кан.)", "address": 100})
    rgb_fx, rgbw_fx = eng.fixtures[0], eng.fixtures[-1]
    all_ids = [f.id for f in eng.fixtures]
    eng.handle({"cmd": "set_effect", "type": "rainbow", "ids": all_ids})

    white = next(i for i, c in enumerate(eng.static_colors) if c["name"] == "Білий")
    eng.handle({"cmd": "static_color", "index": white, "ids": []})   # порожньо — усі прилади
    assert eng.effect["type"] == "none"
    assert (rgb_fx.r, rgb_fx.g, rgb_fx.b, rgb_fx.w) == (255, 255, 255, 0)
    assert (rgbw_fx.r, rgbw_fx.g, rgbw_fx.b, rgbw_fx.w) == (0, 0, 0, 255)

    # статичний колір лише на частину приладів — ефект лишається на інших
    eng.handle({"cmd": "set_effect", "type": "rainbow", "ids": all_ids})
    eng.handle({"cmd": "static_color", "hex": "#ff0000", "ids": [rgb_fx.id]})
    assert rgb_fx.id not in eng.effect["ids"] and eng.effect["type"] == "rainbow"
    assert list(eng.render(0)[0:4]) == [255, 255, 0, 0]

    eng.handle({"cmd": "add_static_color", "name": "Мій", "hex": "#123456", "w": 0})
    eng.save()
    assert Engine(tmp_path / "cfg.json").static_colors[-1] == {"name": "Мій", "hex": "#123456"}
