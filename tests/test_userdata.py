import json

from dmxctl import userdata
from dmxctl.engine import Engine

CFG = {
    "output": {"type": "udmx"},
    "master": 200,
    "profiles": {"Мій RGB": ["r", "g", "b"], "Модель X 4ch": ["r", "g", "b", "w"]},
    "device_profiles": ["Модель X 4ch"],
    "recent_models": [{"m": "X", "n": "Модель X"}],
    "fixtures": [{"id": "f1", "name": "Ліво", "address": 1, "profile": "Модель X 4ch"}],
    "scenes": {"Вечір": {"fixtures": {"f1": {"r": 255}}, "effect": None}},
    "static_colors": [{"name": "Червоний", "r": 255, "g": 0, "b": 0}],
}


def _write(tmp_path, cfg=CFG):
    p = tmp_path / "config.json"
    p.write_text(json.dumps(cfg, ensure_ascii=False), "utf-8")
    return p


def test_scenes_only(tmp_path):
    p = _write(tmp_path)
    assert userdata.apply(p, {"scenes"}) is False
    cfg = json.loads(p.read_text("utf-8"))
    assert "scenes" not in cfg
    assert cfg["fixtures"] == CFG["fixtures"] and cfg["profiles"] == CFG["profiles"]


def test_fixtures_take_their_model_profiles(tmp_path):
    p = _write(tmp_path)
    userdata.apply(p, {"fixtures"})
    cfg = json.loads(p.read_text("utf-8"))
    assert "fixtures" not in cfg and "recent_models" not in cfg and "device_profiles" not in cfg
    assert cfg["profiles"] == {"Мій RGB": ["r", "g", "b"]}
    assert cfg["scenes"] == CFG["scenes"]


def test_own_profiles_keep_device_profiles(tmp_path):
    p = _write(tmp_path)
    userdata.apply(p, {"profiles", "colors", "settings"})
    cfg = json.loads(p.read_text("utf-8"))
    assert cfg["profiles"] == {"Модель X 4ch": ["r", "g", "b", "w"]}
    assert "static_colors" not in cfg and "output" not in cfg and "master" not in cfg
    assert cfg["fixtures"] == CFG["fixtures"]


def test_everything_removes_file(tmp_path):
    p = _write(tmp_path)
    assert userdata.apply(p, set(userdata.PARTS)) is True
    assert not p.exists()


def test_nothing_left_removes_file(tmp_path):
    p = _write(tmp_path, {"scenes": {"A": {"fixtures": {}}}, "profiles": {}})
    assert userdata.apply(p, {"scenes"}) is True
    assert not p.exists()


def test_missing_file_is_fine(tmp_path):
    assert userdata.apply(tmp_path / "config.json", {"scenes"}) is True


def test_engine_loads_stripped_config(tmp_path):
    p = _write(tmp_path)
    userdata.apply(p, {"fixtures", "settings"})
    eng = Engine(p)
    assert eng.fixtures == [] and "Вечір" in eng.scenes
    eng.cmd_recall_scene({"name": "Вечір"})   # сцена з видаленим приладом не ламається


def test_cli(tmp_path, capsys):
    p = _write(tmp_path)
    assert userdata.main(["--config", str(p), "scenes", "colors"]) == 0
    assert capsys.readouterr().out.strip() == "kept"
    assert userdata.main(["--config", str(p), "fixtures", "profiles", "settings"]) == 0
    assert capsys.readouterr().out.strip() == "removed"


def test_own_profiles_in_use_stay(tmp_path):
    """«Власні профілі» без «Приладів»: профіль, на якому працює прилад, лишається."""
    cfg = {**CFG, "fixtures": CFG["fixtures"] + [{"id": "f2", "name": "PAR", "address": 9, "profile": "Мій RGB"}],
           "profiles": {**CFG["profiles"], "Зайвий": ["r"]}}
    p = _write(tmp_path, cfg)
    userdata.apply(p, {"profiles"})
    assert set(json.loads(p.read_text("utf-8"))["profiles"]) == {"Мій RGB", "Модель X 4ch"}
