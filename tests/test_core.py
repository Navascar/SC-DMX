import json
import struct

import pytest

from dmxctl.effects import effect_color
from dmxctl.engine import STROBE_LEVEL, Engine
from dmxctl.fixtures import DEFAULT_PROFILES, FORMER_PROFILES, Fixture, find_overlaps, render_fixture, validate_fixture
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
    render_fixture(uni, fx, FORMER_PROFILES[fx.profile], fx.color(), master=1.0)
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


WASH8 = "Free Color WASH 243 · 8 кан. H001 (Dim, строб, програми, RGB)"
WASH24 = "Free Color WASH 243 · 24 кан. P001 (8 сегментів)"


def test_wash243_profiles():
    from dmxctl.fixtures import MODEL_PROFILES, segment_count
    assert segment_count(MODEL_PROFILES[WASH24]) == 8
    assert len(MODEL_PROFILES[WASH24]) == 24
    assert segment_count(MODEL_PROFILES["Free Color WASH 243 · 6 кан. E001 (2 сегменти)"]) == 2
    assert MODEL_PROFILES["Free Color WASH 243 · 4 кан. d001 (Dim+RGB)"] == ["dim", "r", "g", "b"]
    # WASH 243 — модель бібліотеки, а не загальний профіль
    assert not any(n.startswith("Free Color") for n in DEFAULT_PROFILES)


def test_only_basic_default_profiles():
    # загальні профілі — лише базове RGB-керування; решта — режими моделей бібліотеки
    assert set(DEFAULT_PROFILES) == {"RGB (3 кан.)", "RGBW (4 кан.)", "Dim+RGB (4 кан.)", "RGB+Dim (4 кан.)"}
    for roles in DEFAULT_PROFILES.values():
        assert set(roles) <= {"r", "g", "b", "w", "dim"}
    assert not set(FORMER_PROFILES) & set(DEFAULT_PROFILES)


def test_former_default_profile_migrates(tmp_path):
    import json
    cfg = tmp_path / "cfg.json"
    cfg.write_text(json.dumps({"fixtures": [
        {"id": "a", "name": "PAR", "address": 1, "profile": "RGBWA+UV (6 кан.)"}]}), "utf-8")
    eng = Engine(cfg)
    # профіль приладу на місці, а невикористані колишні профілі в списку не з'являються
    assert eng.profiles["RGBWA+UV (6 кан.)"] == ["r", "g", "b", "w", "a", "uv"]
    assert "Dim+RGB+Strobe (5 кан.)" not in eng.profiles
    eng.save()
    assert "RGBWA+UV (6 кан.)" in json.loads(cfg.read_text("utf-8"))["profiles"]
    # новий прилад із колишнім профілем теж можна додати (напр. зі старої сцени чи копією)
    eng.handle({"cmd": "add_fixture", "profile": "Dim+RGB+Strobe (5 кан.)", "address": 20})
    assert eng.profiles["Dim+RGB+Strobe (5 кан.)"] == ["dim", "r", "g", "b", "strobe"]


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
    from dmxctl.fixtures import PRESET_COUNT, preset_level
    assert PRESET_COUNT == 23
    assert [preset_level(1), preset_level(8), preset_level(23)] == [11, 88, 251]  # червоний, ефект 1, звук
    eng = Engine(tmp_path / "cfg.json")
    eng.handle({"cmd": "add_fixture", "profile": WASH8, "address": 1})
    bar = eng.fixtures[0]
    eng.handle({"cmd": "set_master", "value": 100})
    eng.handle({"cmd": "set_effect", "type": "rainbow", "ids": [bar.id]})
    eng.handle({"cmd": "preset", "ids": [bar.id], "n": 3})
    f = eng.render(0)
    assert f[2] == preset_level(3)                            # програма — у свій канал
    assert eng.effect["type"] == "none"


def test_presets_only_with_program_channel(tmp_path):
    eng = Engine(tmp_path / "cfg.json")
    eng.handle({"cmd": "add_fixture", "profile": WASH8, "address": 1})
    eng.handle({"cmd": "add_fixture", "profile": WASH24, "address": 9})
    eng.handle({"cmd": "add_fixture", "profile": "Dim+RGB (4 кан.)", "address": 40})
    bar, rgb_bar, par = eng.fixtures
    # базові профілі й режими без каналу програми пресетів не мають
    assert eng.state()["preset_fixtures"] == [bar.id]
    eng.handle({"cmd": "preset", "ids": [], "n": 2})
    assert bar.preset == 2 and rgb_bar.preset is None and par.preset is None
    with pytest.raises(ValueError):
        eng.handle({"cmd": "preset", "ids": [par.id], "n": 2})
    # колишня галочка «Вбудовані пресети» більше нічого не вмикає
    eng.handle({"cmd": "update_fixture", "id": par.id, "presets": True})
    with pytest.raises(ValueError):
        eng.handle({"cmd": "preset", "ids": [par.id], "n": 2})


def test_old_presets_on_base_profile_are_dropped(tmp_path):
    p = tmp_path / "cfg.json"
    p.write_text(json.dumps({"fixtures": [{"id": "a", "name": "A", "address": 1, "profile": "RGB (3 кан.)",
                                           "presets": True, "preset": 4}]}), "utf-8")
    eng = Engine(p)
    assert eng.fixtures[0].preset is None and eng.state()["preset_fixtures"] == []


def test_strobe_button_only_for_strobe_channel(tmp_path):
    eng = Engine(tmp_path / "cfg.json")
    eng.handle({"cmd": "add_fixture", "profile": WASH8, "address": 1})       # dim, strobe, …
    eng.handle({"cmd": "add_fixture", "profile": "RGB (3 кан.)", "address": 20})
    bar, par = eng.fixtures
    assert eng.state()["strobe_fixtures"] == [bar.id]
    eng.handle({"cmd": "strobe", "on": True, "ids": []})
    f = eng.render(0)
    assert f[1] == STROBE_LEVEL and eng.state()["strobe"]["on"]
    assert eng.state()["undo"] == "add_fixture"                  # строб не потрапляє в скасування
    eng.handle({"cmd": "strobe", "on": False})
    assert eng.render(0)[1] == 0
    with pytest.raises(ValueError):                              # лише прилади без строба
        eng.handle({"cmd": "strobe", "on": True, "ids": [par.id]})
    eng.handle({"cmd": "strobe", "ids": [bar.id, par.id]})       # без on — перемикає
    assert eng.strobe == {"on": True, "ids": [bar.id]}


def test_hotkeys_saved(tmp_path):
    eng = Engine(tmp_path / "cfg.json")
    eng.handle({"cmd": "set_hotkeys", "hotkeys": {"blackout": ["KeyX"], "strobe": []}})
    eng.save()
    again = Engine(tmp_path / "cfg.json")
    assert again.state()["hotkeys"] == {"blackout": ["KeyX"], "strobe": []}
    with pytest.raises(ValueError):
        eng.handle({"cmd": "set_hotkeys", "hotkeys": {"blackout": "KeyX"}})


def test_wash243_program_modes(tmp_path):
    """A001: CH1 — програма, CH2 — швидкість; H001: CH3 — програма, CH4 — швидкість, CH8 = 0."""
    eng = Engine(tmp_path / "cfg.json")
    eng.handle({"cmd": "add_fixture", "profile": "Free Color WASH 243 · 2 кан. A001 (програми)", "address": 1})
    eng.handle({"cmd": "add_fixture", "profile": "Free Color WASH 243 · 8 кан. H001 (Dim, строб, програми, RGB)", "address": 3})
    a, h = eng.fixtures
    assert eng.state()["preset_fixtures"] == [a.id, h.id]
    assert list(eng.render(0)[0:2]) == [0, 128]               # без програми: 000 = «без ефекту»
    eng.handle({"cmd": "preset", "ids": [a.id, h.id], "n": 9, "speed": 200})   # «Ефект 2» = 094–104
    f = eng.render(0)
    assert list(f[0:2]) == [99, 200]
    assert list(f[2:10]) == [255, 0, 99, 200, 0, 0, 0, 0]
    # лише швидкість — програма не змінюється
    eng.handle({"cmd": "preset", "ids": [a.id], "speed": 10})
    assert a.preset == 9 and eng.render(0)[1] == 10
    # H001 без програми — звичайний RGB з диммером
    eng.handle({"cmd": "static_color", "hex": "#0000ff", "ids": [h.id]})
    assert list(eng.render(0)[2:10]) == [255, 0, 0, 200, 0, 0, 255, 0]  # швидкість лишається
    eng.handle({"cmd": "blackout", "on": True})
    assert not any(eng.render(0)[0:1]) and eng.render(0)[2] == 0


def test_legacy_profile_name_migrates(tmp_path):
    import json
    cfg = tmp_path / "cfg.json"
    cfg.write_text(json.dumps({"fixtures": [{"id": "x", "name": "Бар", "address": 1,
                                             "profile": "Free Color WASH 243 · 24 кан. (8 сегментів)", "preset": 25}]}))
    eng = Engine(cfg)
    assert eng.fixtures[0].profile == WASH24 and eng.fixtures[0].preset is None


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


def test_white_mixes_into_rgb_without_white_channel(tmp_path):
    eng = Engine(tmp_path / "cfg.json")
    eng.handle({"cmd": "add_fixture", "profile": "RGB (3 кан.)", "address": 1})
    eng.handle({"cmd": "add_fixture", "profile": "RGBW (4 кан.)", "address": 4})
    rgb, rgbw = eng.fixtures
    eng.handle({"cmd": "set_color", "ids": [rgb.id, rgbw.id], "r": 200, "g": 0, "b": 50, "w": 100})
    f = eng.render(0)
    assert list(f[0:3]) == [255, 100, 150]       # RGB: білий додано до кожного кольору (з обмеженням 255)
    assert list(f[3:7]) == [200, 0, 50, 100]     # RGBW: білий — у свій канал


def test_fixture_library_modes_are_valid():
    from dmxctl import library
    from dmxctl.fixtures import validate_profile
    lib = library.models()
    assert len(lib) > 1000
    for fx in lib:
        for name, roles, *_ in fx["modes"]:
            validate_profile(roles)   # кожна роль відома програмі
    found = library.search("adj mega bar")
    assert found and all("Mega" in f["n"] for f in found)
    assert len(library.search("", 10)) == 10                 # без запиту — увесь розділ, порціями
    assert all(f["t"] == "bar" for f in library.search("", 50, "bar"))
    assert library.search("", 1)[0]["n"] == "WASH 243"        # вбудовані моделі — першими


def test_library_device_profile_not_in_menu(tmp_path):
    import json
    from dmxctl import library
    cfg = tmp_path / "cfg.json"
    eng = Engine(cfg)
    fx = library.search("adj mega bar 50rgb")[0]
    mode = fx["modes"][0]
    name = library.profile_name(fx, mode)
    eng.handle({"cmd": "add_fixture", "profile": name, "channels": mode[1], "address": 1,
                "model": {"m": fx["m"], "n": fx["n"], "mode": mode[0]}})
    f = eng.fixtures[0]
    assert f.profile == name and eng.profiles[name] == mode[1]
    assert f.model == {"m": fx["m"], "n": fx["n"], "mode": mode[0]}
    # профіль моделі — у приладу, а не в меню профілів
    st = eng.state()
    assert name not in st["menu_profiles"] and set(DEFAULT_PROFILES) <= set(st["menu_profiles"])
    assert st["recent_models"] == [{"m": fx["m"], "n": fx["n"]}]
    assert [r["n"] for r in library.search("", 10, "recent", recent=st["recent_models"])] == [fx["n"]]
    assert library.counts("", st["recent_models"])["recent"] == 1
    # після перезапуску все на місці
    eng.save()
    eng2 = Engine(cfg)
    assert eng2.fixtures[0].model == f.model and name not in eng2.menu_profiles()
    assert eng2.recent_models == st["recent_models"]
    # стандартний профіль відв'язує прилад від моделі; невикористаний профіль моделі не зберігається
    eng2.handle({"cmd": "update_fixture", "id": f.id, "profile": "RGB (3 кан.)"})
    assert eng2.fixtures[0].model is None
    eng2.save()
    saved = json.loads(cfg.read_text("utf-8"))
    assert name not in saved["profiles"] and saved["recent_models"] == st["recent_models"]


def test_recent_models_order_and_mode_change(tmp_path):
    from dmxctl import library
    eng = Engine(tmp_path / "cfg.json")
    a, b = library.search("", 2, "par")
    for fx in (a, b, a):
        mode = fx["modes"][-1]
        eng.handle({"cmd": "add_fixture", "profile": library.profile_name(fx, mode), "channels": mode[1],
                    "address": 1 + 20 * len(eng.fixtures), "model": {"m": fx["m"], "n": fx["n"], "mode": mode[0]}})
    assert [r["n"] for r in eng.recent_models] == [a["n"], b["n"]]   # найновіші першими, без повторів
    # інший режим тієї самої моделі з властивостей приладу
    f = eng.fixtures[1]
    mode = b["modes"][0]
    eng.handle({"cmd": "update_fixture", "id": f.id, "profile": library.profile_name(b, mode), "channels": mode[1],
                "model": {"m": b["m"], "n": b["n"], "mode": mode[0]}})
    assert eng.profiles[f.profile] == mode[1] and f.model["mode"] == mode[0]
    assert eng.recent_models[0]["n"] == b["n"]


def test_old_library_profiles_migrate_to_devices(tmp_path):
    import json
    from dmxctl import library
    fx = library.search("adj mega bar 50rgb")[0]
    mode = fx["modes"][0]
    name = library.profile_name(fx, mode)
    cfg = tmp_path / "cfg.json"
    cfg.write_text(json.dumps({
        "profiles": {name: mode[1], "Мій PAR": ["r", "g", "b", "zero"]},
        "fixtures": [{"id": "a", "name": "Бар", "address": 1, "profile": name},
                     {"id": "b", "name": "WASH", "address": 40, "profile": WASH24}],
    }), "utf-8")
    eng = Engine(cfg)
    menu = eng.menu_profiles()
    assert name not in menu and WASH24 not in menu and "Мій PAR" in menu   # власні профілі лишаються в меню
    assert eng.fixtures[0].model["n"] == fx["n"] and eng.fixtures[1].model["n"] == "WASH 243"
    assert [r["n"] for r in eng.recent_models] == [fx["n"], "WASH 243"]


def _scene_pc(tmp_path, name):
    eng = Engine(tmp_path / f"{name}.json")
    eng.fixtures.clear()
    return eng


def test_scene_file_moves_to_other_computer(tmp_path):
    import json
    from dmxctl import library
    a = _scene_pc(tmp_path, "a")
    a.handle({"cmd": "add_fixture", "profile": "RGBW (4 кан.)", "address": 1, "name": "Ліва"})
    a.handle({"cmd": "add_fixture", "profile": "Dim+RGB (4 кан.)", "address": 10, "name": "Права"})
    wash = library.find("Free Color", "WASH 243")
    mode = wash["modes"][0]
    a.handle({"cmd": "add_fixture", "profile": mode[2], "channels": mode[1], "address": 20, "name": "Бар",
              "model": {"m": "Free Color", "n": "WASH 243", "mode": mode[0]}})
    left, right, bar = a.fixtures
    a.handle({"cmd": "set_color", "ids": [left.id], "r": 255, "g": 10, "b": 0, "w": 40})
    a.handle({"cmd": "set_color", "ids": [f"{bar.id}#2"], "r": 0, "g": 0, "b": 200})
    a.handle({"cmd": "save_scene", "name": "Вечір"})
    data = json.loads(json.dumps(a.export_scene("Вечір")))   # як через файл

    # інший комп'ютер: ті самі прожектори на тих самих адресах, але свої id; бару немає
    b = _scene_pc(tmp_path, "b")
    b.handle({"cmd": "add_fixture", "profile": "RGBW (4 кан.)", "address": 1, "name": "L"})
    b.handle({"cmd": "add_fixture", "profile": "Dim+RGB (4 кан.)", "address": 10, "name": "R"})
    b.handle({"cmd": "import_scene", "data": data})
    note = b.pop_notice()
    assert "Вечір" in note and "додано: 1" in note
    assert len(b.fixtures) == 3
    new_bar = b.fixtures[2]
    assert new_bar.address == 20 and new_bar.model["n"] == "WASH 243"
    assert new_bar.profile not in b.menu_profiles()           # профіль моделі — у приладу
    b.handle({"cmd": "recall_scene", "name": "Вечір"})
    f = b.render(0)
    assert list(f[0:4]) == [255, 10, 0, 40]                   # ліва — за адресою
    assert new_bar.segs[2] == [0, 0, 200]
    # повторне відкриття не перезаписує сцену і не дублює прилади
    b.handle({"cmd": "import_scene", "data": data})
    assert "Вечір (2)" in b.scenes and len(b.fixtures) == 3
    # скасування повертає все як було
    b.handle({"cmd": "undo"})
    assert "Вечір (2)" not in b.scenes


def test_scene_file_busy_addresses_and_bad_file(tmp_path):
    a = _scene_pc(tmp_path, "a")
    a.handle({"cmd": "add_fixture", "profile": "RGB (3 кан.)", "address": 1, "name": "PAR"})
    a.handle({"cmd": "save_scene", "name": "S"})
    data = a.export_scene("S")
    b = _scene_pc(tmp_path, "b")
    b.handle({"cmd": "add_fixture", "profile": "RGBW (4 кан.)", "address": 1, "name": "Інший"})
    with pytest.raises(ValueError, match="зіставити"):
        b.handle({"cmd": "import_scene", "data": data})
    assert "S" not in b.scenes and len(b.fixtures) == 1
    with pytest.raises(ValueError, match="не файл сцени"):
        b.handle({"cmd": "import_scene", "data": {"hello": 1}})
    # власний профіль з іншого комп'ютера приходить разом із приладом
    a.handle({"cmd": "save_profile", "name": "Мій PAR", "channels": ["dim", "r", "g", "b", "zero"]})
    a.handle({"cmd": "add_fixture", "profile": "Мій PAR", "address": 100})
    a.handle({"cmd": "save_scene", "name": "S2"})
    b.handle({"cmd": "import_scene", "data": a.export_scene("S2")})
    added = [f for f in b.fixtures if f.address == 100][0]
    assert b.profiles[added.profile] == ["dim", "r", "g", "b", "zero"] and added.profile in b.menu_profiles()


def test_scene_file_http(tmp_path):
    import asyncio
    from aiohttp.test_utils import TestClient, TestServer
    from dmxctl.server import ENGINE, make_app

    async def run():
        app = make_app(str(tmp_path / "cfg.json"), background=True)
        eng = app[ENGINE]
        eng.fixtures.clear()
        eng.handle({"cmd": "add_fixture", "profile": "RGB (3 кан.)", "address": 1})
        eng.handle({"cmd": "save_scene", "name": "Зелений / сад"})
        async with TestClient(TestServer(app)) as c:
            r = await c.get("/api/scene", params={"name": "Зелений / сад"})
            assert r.status == 200
            assert "filename*=UTF-8''" in r.headers["Content-Disposition"]
            assert "%D0%97%D0%B5%D0%BB%D0%B5%D0%BD%D0%B8%D0%B9%20_%20%D1%81%D0%B0%D0%B4.scdmx" in r.headers["Content-Disposition"]
            assert (await r.json())["format"] == "sc-dmx-scene"
            assert (await c.get("/api/scene", params={"name": "нема"})).status == 404
    asyncio.run(run())


def test_server_rejects_foreign_origin_and_host(tmp_path):
    """Чужий сайт у браузері не може керувати програмою (WebSocket) і не обходить її через DNS rebinding."""
    import asyncio
    from aiohttp import WSServerHandshakeError
    from aiohttp.test_utils import TestClient, TestServer
    from dmxctl.server import host_allowed, make_app, origin_allowed

    names = {"localhost", "studio-pc", "studio-pc.local"}
    assert host_allowed("127.0.0.1:8080", names) and host_allowed("[::1]:8080", names)
    assert host_allowed("192.168.1.20:8080", names) and host_allowed("studio-pc:8080", names)
    assert not host_allowed("evil.example:8080", names) and not host_allowed("", names)
    assert origin_allowed(None, "127.0.0.1:8080")                         # не браузер (інсталятор)
    assert origin_allowed("http://127.0.0.1:8080", "127.0.0.1:8080")
    assert origin_allowed("http://192.168.1.20:8080", "192.168.1.20:8080")  # інший пристрій мережі
    assert not origin_allowed("https://evil.example", "127.0.0.1:8080")
    assert not origin_allowed("null", "127.0.0.1:8080")

    async def run():
        app = make_app(str(tmp_path / "cfg.json"), background=True)
        async with TestClient(TestServer(app)) as c:
            host = f"127.0.0.1:{c.port}"
            ws = await c.ws_connect("/ws", headers={"Origin": f"http://{host}", "Host": host})
            assert (await ws.receive_json())["type"] == "state"
            await ws.close()
            ws = await c.ws_connect("/ws", headers={"Host": host})            # без Origin — дозволено
            await ws.close()
            try:
                await c.ws_connect("/ws", headers={"Origin": "https://evil.example", "Host": host})
                raise AssertionError("чужий Origin мав бути відхилений")
            except WSServerHandshakeError as e:
                assert e.status == 403
            r = await c.get("/api/library", headers={"Host": f"evil.example:{c.port}"})
            assert r.status == 403
            r = await c.get("/", headers={"Host": host})
            assert r.status == 200
    asyncio.run(run())


def test_update_zip_slip_rejected(tmp_path):
    import zipfile
    from dmxctl.updater import install_from_zip
    app = tmp_path / "app"
    (app / "dmxctl").mkdir(parents=True)
    (app / "dmxctl" / "__init__.py").write_text("old")
    z = tmp_path / "u.zip"
    with zipfile.ZipFile(z, "w") as zf:
        zf.writestr("SC-DMX/dmxctl/__init__.py", "new")
        zf.writestr("../sc-dmx-evil/x.txt", "pwn")     # сусідня тека з тим самим префіксом
    with pytest.raises(RuntimeError, match="небезпечний шлях"):
        install_from_zip(z, app)
    assert (app / "dmxctl" / "__init__.py").read_text() == "old"


def test_output_pauses_on_empty_frame():
    """Немає приладів або все вимкнено: кілька порожніх кадрів, далі відправка стоїть до зміни."""
    import time as _t

    from dmxctl.outputs import NullOutput
    out = NullOutput()
    out.refresh_hz, out.idle_tail_s = 200.0, 0.1
    out.start()
    try:
        _t.sleep(0.4)
        assert out.paused and out.info()["paused"]
        n = out.frames_sent
        assert n > 0                                   # порожній кадр усе ж пішов, щоб прилади згасли
        _t.sleep(0.2)
        assert out.frames_sent == n                    # далі — тиша
        out.set_frame(bytes([255]) + bytes(511))
        _t.sleep(0.1)
        assert not out.paused and out.frames_sent > n  # світло ввімкнули — кадри знову йдуть
        n = out.frames_sent
        _t.sleep(0.1)
        assert out.frames_sent > n                     # непорожній кадр шлеться безперервно
    finally:
        out.stop()


def _scene_file(effect, fixtures=None):
    from dmxctl.engine import SCENE_FORMAT
    return {"format": SCENE_FORMAT, "version": 1, "name": "X", "effect": effect,
            "fixtures": fixtures or [{"id": "f1", "address": 1, "channels": ["r", "g", "b"], "name": "A",
                                      "state": {"r": 10}}]}


@pytest.mark.parametrize("effect", [
    {"type": "rainbow", "ids": ["f1"], "colors": ["zz", 5, "#00ff00"]},   # зіпсовані кольори
    {"type": "rainbow", "ids": ["f1"], "speed": "fast", "spread": None},  # нечислові параметри
    {"type": "rainbow"},                                                 # без частини ключів
    {"type": "rainbow", "ids": 5, "speed": float("nan")},
])
def test_scene_file_with_broken_effect_does_not_freeze_light(tmp_path, effect):
    """Сцена з файлу з некоректним ефектом не ламає рендер, а ефект можна зупинити."""
    eng = Engine(tmp_path / "cfg.json")
    eng.handle({"cmd": "add_fixture", "profile": "RGB (3 кан.)", "address": 1})
    eng.handle({"cmd": "import_scene", "data": _scene_file(effect)})
    eng.handle({"cmd": "recall_scene", "name": "X"})
    eng.render(1.0)
    assert all(c == "#00ff00" for c in eng.effect["colors"])
    eng.handle({"cmd": "set_effect", "type": "none"})          # кнопка «Зупинити»
    assert eng.effect["type"] == "none"
    eng.render(2.0)


def test_scene_import_is_all_or_nothing(tmp_path, monkeypatch):
    """Якщо імпорт упав посередині, доданий прилад і профіль прибираються."""
    from dmxctl import engine as engine_mod
    eng = Engine(tmp_path / "cfg.json")

    def boom(*_a, **_k):
        raise ValueError("зіпсований стан")
    monkeypatch.setattr(engine_mod, "_scene_state", boom)
    with pytest.raises(ValueError):
        eng.handle({"cmd": "import_scene", "data": _scene_file(None)})
    assert eng.fixtures == [] and eng.scenes == {}


def test_scene_file_item_without_id_is_skipped(tmp_path):
    eng = Engine(tmp_path / "cfg.json")
    eng.handle({"cmd": "add_fixture", "profile": "RGB (3 кан.)", "address": 1})
    items = [{"address": 1, "channels": ["r", "g", "b"], "state": {"r": 1}},
             {"id": "f1", "address": 1, "channels": ["r", "g", "b"], "state": {"r": 9}}]
    eng.handle({"cmd": "import_scene", "data": _scene_file(None, items)})
    assert "X" in eng.scenes
