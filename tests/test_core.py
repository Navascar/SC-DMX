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
    assert eng.fixtures == []  # перший запуск — без приладів
    eng.handle({"cmd": "add_fixture", "profile": "Dim+RGB (4 кан.)", "address": 1, "count": 4})
    ids = [f.id for f in eng.fixtures]
    assert len(ids) == 4
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
    eng.handle({"cmd": "add_fixture", "profile": "Dim+RGB (4 кан.)", "address": 1})
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


WASH24 = "Free Color WASH 243 · 24 кан. (8 сегментів)"


def test_wash243_profiles():
    from dmxctl.fixtures import segment_count
    assert segment_count(DEFAULT_PROFILES[WASH24]) == 8
    assert len(DEFAULT_PROFILES[WASH24]) == 24
    assert segment_count(DEFAULT_PROFILES["Free Color WASH 243 · 6 кан. E001 (2 сегменти)"]) == 2
    assert DEFAULT_PROFILES["Free Color WASH 243 · 4 кан. d001 (Dim+RGB)"] == ["dim", "r", "g", "b"]


def test_segment_colors_and_clear(tmp_path):
    eng = Engine(tmp_path / "cfg.json")
    eng.fixtures.clear()
    eng.handle({"cmd": "add_fixture", "profile": WASH24, "address": 1, "name": "Бар"})
    fx = eng.fixtures[0]
    # увесь бар синім, третій сегмент червоним
    eng.handle({"cmd": "set_color", "ids": [fx.id], "hex": "#0000ff"})
    eng.handle({"cmd": "set_color", "ids": [f"{fx.id}#2"], "hex": "#ff0000"})
    frame = eng.render(0)
    assert list(frame[0:3]) == [0, 0, 255]
    assert list(frame[6:9]) == [255, 0, 0]
    assert list(frame[21:24]) == [0, 0, 255]
    assert len(eng.live[fx.id]) == 8

    # очищення одного сегмента
    eng.handle({"cmd": "clear", "ids": [f"{fx.id}#0"]})
    frame = eng.render(0)
    assert list(frame[0:3]) == [0, 0, 0] and list(frame[3:6]) == [0, 0, 255]

    # колір на весь прилад скидає сегменти
    eng.handle({"cmd": "set_color", "ids": [fx.id], "hex": "#00ff00"})
    assert fx.segs is None

    # «Очистити все» без вибору — гасить усе і зупиняє ефект
    eng.handle({"cmd": "set_effect", "type": "rainbow", "ids": [fx.id]})
    eng.handle({"cmd": "clear", "ids": []})
    assert eng.effect["type"] == "none"
    assert not any(eng.render(0))


def test_effect_runs_along_segments(tmp_path):
    eng = Engine(tmp_path / "cfg.json")
    eng.fixtures.clear()
    eng.handle({"cmd": "add_fixture", "profile": WASH24, "address": 1})
    fid = eng.fixtures[0].id
    eng.handle({"cmd": "set_effect", "type": "rainbow", "ids": [fid], "spread": 1.0, "by_segment": True})
    frame = eng.render(0)
    segs = {bytes(frame[i:i + 3]) for i in range(0, 24, 3)}
    assert len(segs) > 4                      # веселка розкладена по сегментах
    eng.handle({"cmd": "set_effect", "by_segment": False})
    frame = eng.render(0)
    assert len({bytes(frame[i:i + 3]) for i in range(0, 24, 3)}) == 1  # увесь бар одним кольором


def test_scene_restores_segments(tmp_path):
    eng = Engine(tmp_path / "cfg.json")
    eng.fixtures.clear()
    eng.handle({"cmd": "add_fixture", "profile": WASH24, "address": 1})
    fx = eng.fixtures[0]
    eng.handle({"cmd": "set_color", "ids": [f"{fx.id}#7"], "hex": "#ffffff"})
    eng.handle({"cmd": "save_scene", "name": "s"})
    eng.handle({"cmd": "clear", "ids": []})
    eng.handle({"cmd": "recall_scene", "name": "s", "fade": 1})
    start = eng._fade["start"]
    eng.render(start + 0.5)
    assert 120 <= fx.segs[7][0] <= 135
    eng.render(start + 2)
    assert fx.segs[7] == [255, 255, 255]


def test_udmx_streams_frames_continuously():
    """Кадр має йти безперервно, навіть якщо він не змінюється (інакше бари не реагують)."""
    import time
    from dmxctl.outputs import UDmxOutput

    sent = []

    class FakeDev:
        def ctrl_transfer(self, bm, req, value, index, data, timeout):
            sent.append(bytes(data[:3]))
            return len(data)

    out = UDmxOutput()
    out.open = lambda: setattr(out, "dev", FakeDev())
    out.close = lambda: None
    out.start()
    out.set_frame(bytes([10, 20, 30]) + bytes(509))
    time.sleep(0.5)
    out.stop()
    same = [s for s in sent if s == bytes([10, 20, 30])]
    assert len(same) >= 8, f"за 0.5 с надіслано лише {len(same)} кадрів"


def test_fixed_roles_and_raw_channel_test(tmp_path):
    from dmxctl.fixtures import validate_profile
    validate_profile(["=10", "r", "g", "b"])
    with pytest.raises(ValueError):
        validate_profile(["=300", "r"])
    eng = Engine(tmp_path / "cfg.json")
    eng.handle({"cmd": "add_fixture", "profile": "RGB (3 кан.)", "address": 1})
    fx = eng.fixtures[0]
    # власний профіль: канал режиму на 10, потім RGB — і одразу призначити приладу
    eng.handle({"cmd": "save_profile", "name": "Мій бар", "channels": ["=10", "r", "g", "b"], "assign_to": fx.id})
    assert fx.profile == "Мій бар"
    eng.handle({"cmd": "set_color", "ids": [fx.id], "hex": "#ff8000"})
    assert list(eng.render(0)[0:4]) == [10, 255, 128, 0]
    # тест каналів перекриває вивід і не зберігається
    eng.handle({"cmd": "raw_set", "address": 2, "value": 7})
    assert eng.render(0)[1] == 7 and eng.state()["raw"] == {"2": 7}
    eng.handle({"cmd": "raw_clear"})
    assert eng.render(0)[1] == 255
    with pytest.raises(ValueError):
        eng.handle({"cmd": "save_profile", "name": "RGB (3 кан.)", "channels": ["r"]})


def test_presets_switch_brightness_levels(tmp_path):
    from dmxctl.fixtures import preset_level
    assert [preset_level(1), preset_level(2), preset_level(25)] == [15, 25, 255]
    eng = Engine(tmp_path / "cfg.json")
    eng.handle({"cmd": "add_fixture", "profile": "Free Color WASH 243 · 24 кан. (8 сегментів)", "address": 1})
    eng.handle({"cmd": "add_fixture", "profile": "Dim+RGB (4 кан.)", "address": 25})
    bar, par = eng.fixtures
    eng.handle({"cmd": "set_master", "value": 100})          # майстер не зсуває пресет
    eng.handle({"cmd": "set_effect", "type": "rainbow", "ids": [bar.id, par.id]})
    eng.handle({"cmd": "preset", "ids": [bar.id, par.id], "n": 3})
    f = eng.render(0)
    assert list(f[0:6]) == [35, 0, 0, 35, 0, 0]               # без диммера: червоний = рівень
    assert list(f[24:28]) == [35, 255, 0, 0]                  # з диммером: dim = рівень, червоний 255
    assert eng.effect["type"] == "none"
    eng.handle({"cmd": "blackout", "on": True})
    assert not any(eng.render(0))
    eng.handle({"cmd": "blackout", "on": False})
    # звичайний колір вимикає пресет
    eng.handle({"cmd": "static_color", "hex": "#00ff00", "ids": [bar.id]})
    assert bar.preset is None and par.preset == 3
    # сцена зберігає пресет
    eng.handle({"cmd": "save_scene", "name": "p"})
    eng.handle({"cmd": "clear", "ids": []})
    assert par.preset is None
    eng.handle({"cmd": "recall_scene", "name": "p", "fade": 0})
    assert par.preset == 3
    with pytest.raises(ValueError):
        eng.handle({"cmd": "preset", "ids": [par.id], "n": 26})


def test_undo_redo(tmp_path, monkeypatch):
    import dmxctl.engine as engmod
    eng = Engine(tmp_path / "cfg.json")
    eng.handle({"cmd": "add_fixture", "profile": "RGB (3 кан.)", "address": 1})
    fx_id = eng.fixtures[0].id
    eng.handle({"cmd": "static_color", "hex": "#ff0000", "ids": [fx_id]})
    # серія рухів повзунка — один крок
    for v in (10, 50, 120):
        eng.handle({"cmd": "set_color", "ids": [fx_id], "g": v})
    assert eng.fixtures[0].g == 120 and eng.state()["undo"] == "set_color"
    eng.handle({"cmd": "undo"})
    assert (eng.fixtures[0].r, eng.fixtures[0].g) == (255, 0)
    eng.handle({"cmd": "undo"})
    assert eng.fixtures[0].r == 0
    eng.handle({"cmd": "redo"})
    assert eng.fixtures[0].r == 255
    eng.handle({"cmd": "undo"}); eng.handle({"cmd": "undo"})
    assert eng.fixtures == []                     # скасовано і додавання приладу
    with pytest.raises(ValueError):
        eng.handle({"cmd": "undo"})
    # невдала команда не створює кроку
    with pytest.raises(ValueError):
        eng.handle({"cmd": "set_master", "value": 999})
    assert eng.state()["undo"] is None
    # нова дія очищає «повторити»
    eng.handle({"cmd": "redo"})
    eng.handle({"cmd": "set_master", "value": 10})
    assert eng.state()["redo"] is None
