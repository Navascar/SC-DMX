"""Рушій: стан шоу, рендер кадрів, сцени з кросфейдом, збереження конфігурації."""
from __future__ import annotations

import asyncio
import copy
import json
import logging
import math
import os
import time
import uuid
from dataclasses import replace
from pathlib import Path

from . import library
from .effects import EFFECTS, effect_color, hex_to_rgb
from .fixtures import (COLOR_KEYS, DEFAULT_PROFILES, LEGACY_PROFILES, MODEL_PROFILES, PRESET_COUNT, PROGRAMS, Fixture, find_overlaps,
                       has_presets, preset_level, render_fixture, segment_count, validate_fixture, validate_profile)
from .outputs import DMX_CHANNELS, OUTPUT_TYPES, create_output

log = logging.getLogger(__name__)

FPS = 40
UNDO_LIMIT = 100
UNDO_MERGE_S = 1.0   # серія однакових команд (рух повзунка) — один крок скасування
MERGEABLE = {"set_color", "set_master", "set_effect", "preset"}   # команди повзунків
NO_UNDO = {"undo", "redo", "raw_set", "raw_clear", "set_output", "strobe", "set_hotkeys"}
STROBE_LEVEL = 200   # значення каналу строба для кнопки «Строб», якщо в приладу строб не задано
SCENE_FORMAT = "nitor-scene"    # файл сцени (.nitor) для перенесення між комп'ютерами
SCENE_EXT = ".nitor"
LEGACY_SCENE_FORMATS = {"sc-dmx-scene"}   # файли сцен з часів, коли програма називалася SC DMX (.scdmx)

# Статичні кольори за замовчуванням. hex — для RGB-приладів; для приладів
# з білим каналом використовується hex_w + w (чистіший білий від W-світлодіода).
DEFAULT_STATIC_COLORS = [
    {"name": "Червоний", "hex": "#ff0000"},
    {"name": "Помаранчевий", "hex": "#ff5000"},
    {"name": "Жовтий", "hex": "#ffb400"},
    {"name": "Зелений", "hex": "#00ff00"},
    {"name": "Бірюзовий", "hex": "#00ffb4"},
    {"name": "Блакитний", "hex": "#00b4ff"},
    {"name": "Синій", "hex": "#0000ff"},
    {"name": "Фіолетовий", "hex": "#8000ff"},
    {"name": "Пурпуровий", "hex": "#ff00ff"},
    {"name": "Рожевий", "hex": "#ff3c78"},
    {"name": "Теплий білий", "hex": "#ffa050", "hex_w": "#783200", "w": 255},
    {"name": "Білий", "hex": "#ffffff", "hex_w": "#000000", "w": 255},
    {"name": "Холодний білий", "hex": "#d2e6ff", "hex_w": "#002878", "w": 255},
]
STATE_KEYS = COLOR_KEYS + ("dimmer",)


_PROGRAM_COLORS = {"Червоний": (255, 0, 0), "Зелений": (0, 255, 0), "Синій": (0, 0, 255),
                   "Жовтий": (255, 200, 0), "Фіолетовий": (170, 0, 255), "Блакитний": (0, 220, 255),
                   "Білий": (255, 255, 255)}


def _program_rgb(n: int) -> tuple[int, int, int]:
    """Приблизний колір програми для превʼю на плитці приладу."""
    name, group, _, _ = PROGRAMS[n - 1]
    for key, rgb in _PROGRAM_COLORS.items():
        if name.startswith(key):
            return rgb
    return (255, 120, 255) if group == "sound" else (200, 200, 200)


def _seg_rgbs(vals: dict, n: int) -> list[list[int]]:
    """Кольори n сегментів зі збереженого стану приладу (для кросфейду)."""
    base = [vals.get("r", 0), vals.get("g", 0), vals.get("b", 0)]
    segs = list(vals.get("segs") or [])
    return [list(segs[k]) if k < len(segs) and segs[k] else base for k in range(n)]


def _model(v) -> dict | None:
    """Модель приладу {"m", "n", "mode"} або None."""
    if not isinstance(v, dict) or not v.get("m") or not v.get("n"):
        return None
    return {"m": str(v["m"]), "n": str(v["n"]), "mode": str(v.get("mode", ""))}


def _clean_effect(eff) -> dict | None:
    """Ефект зі сцени (зокрема з файлу іншого комп'ютера чи старої версії) — лише допустимі значення.

    Невідомий тип — None (без ефекту); некоректні кольори відкидаються, числа обмежуються.
    Інакше один зіпсований ефект ламав би кожен кадр рендеру."""
    if not isinstance(eff, dict) or eff.get("type") not in EFFECTS:
        return None

    def num(key, default, lo, hi):
        try:
            v = float(eff.get(key, default))
        except (TypeError, ValueError):
            return default
        return max(lo, min(hi, v)) if math.isfinite(v) else default

    colors = []
    for c in eff.get("colors") or []:
        try:
            hex_to_rgb(c)
            colors.append(c)
        except (AttributeError, TypeError, ValueError):
            continue
    ids = eff.get("ids")
    return {
        "type": eff["type"],
        "ids": [str(i) for i in ids] if isinstance(ids, list) else [],
        "speed": num("speed", 0.5, 0.01, 20.0),
        "spread": num("spread", 1.0, 0.0, 1.0),
        "colors": colors[:16],
        "by_segment": bool(eff.get("by_segment", True)),
    }


def _scene_state(vals: dict, segments: int) -> dict:
    """Стан приладу в сцені з файлу — лише відомі поля з допустимими значеннями."""
    def b(v, default=0):
        try:
            return max(0, min(255, int(v)))
        except (TypeError, ValueError):
            return default
    out = {k: b(vals.get(k), 255 if k == "dimmer" else 0) for k in STATE_KEYS}
    segs = vals.get("segs")
    if isinstance(segs, list):
        segs = [[b(c) for c in s[:3]] if isinstance(s, list) and len(s) >= 3 else None for s in segs[:segments]]
        out["segs"] = segs if any(segs) else None
    else:
        out["segs"] = None
    preset = vals.get("preset")
    out["preset"] = preset if isinstance(preset, int) and 1 <= preset <= PRESET_COUNT else None
    out["speed"] = b(vals.get("speed"), 128)
    return out


def _byte(v) -> int:
    try:
        v = int(v)
    except (OverflowError, TypeError, ValueError):
        raise ValueError("значення має бути числом 0..255") from None
    if not 0 <= v <= 255:
        raise ValueError("значення має бути 0..255")
    return v


def _hotkeys(raw) -> dict[str, list[str]]:
    """Перевірка гарячих клавіш: {дія: [комбінація, …]}, рядки до 40 символів."""
    if not isinstance(raw, dict):
        raise ValueError("гарячі клавіші — це словник")
    out: dict[str, list[str]] = {}
    for action, keys in list(raw.items())[:64]:
        if not isinstance(action, str) or not isinstance(keys, list) or len(action) > 40:
            raise ValueError("неправильні гарячі клавіші")
        if not all(isinstance(k, str) and 0 < len(k) <= 40 for k in keys):
            raise ValueError("неправильні гарячі клавіші")
        out[action] = keys[:4]
    return out


class Engine:
    def __init__(self, config_path: str | os.PathLike):
        self.config_path = Path(config_path)
        self.profiles: dict[str, list[str]] = dict(DEFAULT_PROFILES)
        # профілі, що належать моделям приладів (обираються разом із приладом, не в меню)
        self.device_profiles: set[str] = set()
        # нещодавно використані моделі бібліотеки: [{"m", "n"}], найновіші першими
        self.recent_models: list[dict] = []
        self.fixtures: list[Fixture] = []
        self.scenes: dict[str, dict] = {}
        self.static_colors: list[dict] = [dict(c) for c in DEFAULT_STATIC_COLORS]
        self.output_cfg: dict = {"type": "udmx"}
        self.master = 255
        self.blackout = False
        # кнопка «Строб»: прилади з каналом строба; не зберігається і не скасовується
        self.strobe: dict = {"on": False, "ids": []}
        # власні гарячі клавіші: {дія: [комбінації]}; стандартні — в інтерфейсі
        self.hotkeys: dict[str, list[str]] = {}
        self.load_warning: str | None = None   # повідомлення для інтерфейсу про проблему з налаштуваннями
        self.effect: dict = {"type": "none", "ids": [], "speed": 0.5, "spread": 1.0, "colors": [],
                             "by_segment": True}
        self.universe = bytearray(DMX_CHANNELS)
        # ручне керування окремими каналами (тест каналів); не зберігається
        self.raw: dict[int, int] = {}
        self.live: dict[str, list[int]] = {}   # реальні кольори приладів для превʼю
        self._fade: dict | None = None
        self._t0 = time.monotonic()
        self._dirty_save = False
        self._listeners: set = set()
        self._undo: list[tuple[str, dict]] = []
        self._redo: list[tuple[str, dict]] = []
        self._undo_key = None
        self._undo_t = 0.0
        self._notice: str | None = None   # повідомлення для клієнта, що надіслав команду
        self.load()
        self.output = create_output(self.output_cfg)

    # ------------------------------------------------------- persistence --
    def load(self) -> None:
        if not self.config_path.exists():
            return  # перший запуск: прилади додає користувач
        fields = ("profiles", "device_profiles", "recent_models", "fixtures", "scenes", "static_colors",
                  "output_cfg", "master", "hotkeys")
        defaults = {k: copy.deepcopy(getattr(self, k)) for k in fields}
        try:
            cfg = json.loads(self.config_path.read_text("utf-8"))
            if not isinstance(cfg, dict):
                raise ValueError("не об'єкт JSON")
            self._apply_config(cfg)
        except (UnicodeDecodeError, ValueError, TypeError, KeyError, AttributeError) as exc:
            # зіпсований файл (збій диска, ручне редагування) — відкладаємо його вбік і стартуємо з
            # чистими налаштуваннями, а не лишаємо програму без запуску
            for k, v in defaults.items():
                setattr(self, k, v)
            broken = self.config_path.with_name(f"config.broken-{time.strftime('%Y%m%d-%H%M%S')}.json")
            self.config_path.replace(broken)
            log.error("Файл налаштувань пошкоджено (%r), його збережено як %s", exc, broken.name)
            self.load_warning = (f"Файл налаштувань був пошкоджений, тож програма почала з чистих налаштувань. "
                                 f"Старий файл збережено як {broken.name} у теці програми.")

    def _apply_config(self, cfg: dict) -> None:
        self.profiles.update(cfg.get("profiles", {}))
        self.device_profiles = set(cfg.get("device_profiles", [])) & set(self.profiles)
        self.recent_models = [{"m": str(r["m"]), "n": str(r["n"])} for r in cfg.get("recent_models", [])
                              if isinstance(r, dict) and "m" in r and "n" in r][:library.RECENT_LIMIT]
        self.fixtures = [Fixture.from_dict(f) for f in cfg.get("fixtures", [])]
        for f in self.fixtures:  # міграція зі старих версій
            f.profile = LEGACY_PROFILES.get(f.profile, f.profile)
            self._ensure_profile(f.profile)
            if f.preset is not None and not 1 <= f.preset <= PRESET_COUNT:
                f.preset = None
            f.model = _model(f.model)
        if "device_profiles" not in cfg:
            self._migrate_device_profiles()
        for f in self.fixtures:  # пресети лишаються тільки в профілів з каналом програми
            if f.preset is not None and not self._has_presets(f):
                f.preset = None
        self.scenes = cfg.get("scenes", {})
        if "static_colors" in cfg:
            self.static_colors = cfg["static_colors"]
        self.output_cfg = cfg.get("output", {"type": "udmx"})
        self.master = int(cfg.get("master", 255))
        self.hotkeys = _hotkeys(cfg.get("hotkeys", {}))

    def _migrate_device_profiles(self) -> None:
        """До 1.20 профілі моделей бібліотеки зберігалися як звичайні — прив'язуємо їх до приладів."""
        for name, channels in list(self.profiles.items()):
            if name in DEFAULT_PROFILES:
                continue
            owner = library.profile_owner(name, channels)
            if owner is None:
                continue
            self.device_profiles.add(name)
            for f in self.fixtures:
                if f.profile == name and f.model is None:
                    f.model = dict(owner)
        for f in self.fixtures:
            if f.model:
                self._remember(f.model, last=True)

    def _is_device(self, name: str) -> bool:
        if name in DEFAULT_PROFILES:
            return False
        return name in self.device_profiles or name in MODEL_PROFILES

    def menu_profiles(self) -> list[str]:
        """Профілі для меню: стандартні та власні. Профілі моделей обираються разом із приладом."""
        return [n for n in self.profiles if not self._is_device(n)]

    def _remember(self, model: dict, last: bool = False) -> None:
        """Додає модель до «Нещодавно використаних»."""
        key = {"m": model["m"], "n": model["n"]}
        if last:
            if key not in self.recent_models and len(self.recent_models) < library.RECENT_LIMIT:
                self.recent_models.append(key)
            return
        self.recent_models = [key] + [r for r in self.recent_models if r != key]
        del self.recent_models[library.RECENT_LIMIT:]

    def save(self) -> None:
        used = {f.profile for f in self.fixtures}
        # профіль моделі зберігається, поки його використовує хоч один прилад
        custom = {k: v for k, v in self.profiles.items()
                  if DEFAULT_PROFILES.get(k) != v and (k in used or not self._is_device(k))}
        cfg = {
            "output": self.output_cfg,
            "master": self.master,
            "profiles": custom,
            "device_profiles": sorted(k for k in custom if self._is_device(k)),
            "recent_models": self.recent_models,
            "fixtures": [f.to_dict() for f in self.fixtures],
            "scenes": self.scenes,
            "static_colors": self.static_colors,
        }
        if self.hotkeys:
            cfg["hotkeys"] = self.hotkeys
        tmp = self.config_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), "utf-8")
        tmp.replace(self.config_path)
        self._dirty_save = False

    # --------------------------------------------------------- helpers ----
    def _ensure_profile(self, name: str) -> str:
        """Профіль моделі з бібліотеки (напр. WASH 243) додається, щойно він потрібен."""
        name = LEGACY_PROFILES.get(name, name)
        if name not in self.profiles and name in MODEL_PROFILES:
            self.profiles[name] = list(MODEL_PROFILES[name])
        return name

    def _fx(self, fid: str) -> Fixture:
        for f in self.fixtures:
            if f.id == fid:
                return f
        raise KeyError(f"прилад {fid} не знайдено")

    def _targets(self, ids) -> list[Fixture]:
        if not ids:
            return []
        wanted = set(ids)
        return [f for f in self.fixtures if f.id in wanted]

    def _has_presets(self, fx: Fixture) -> bool:
        return has_presets(self.profiles.get(fx.profile, []))

    def _segments(self, fx: Fixture) -> int:
        return segment_count(self.profiles.get(fx.profile, []))

    def _resolve(self, ids) -> tuple[list[Fixture], list[tuple[Fixture, int]]]:
        """Розбирає вибір: "id" — увесь прилад, "id#k" — сегмент k приладу."""
        whole_ids, segs = set(), []
        by_id = {f.id: f for f in self.fixtures}
        for item in ids or []:
            fid, _, k = str(item).partition("#")
            if fid not in by_id:
                continue
            if k == "":
                whole_ids.add(fid)
            else:
                fx = by_id[fid]
                k = int(k)
                if 0 <= k < self._segments(fx):
                    segs.append((fx, k))
        whole = [f for f in self.fixtures if f.id in whole_ids]
        segs = [(f, k) for f, k in segs if f.id not in whole_ids]
        return whole, segs

    def _drop_from_effect(self, fids) -> None:
        fids = set(fids)
        self.effect["ids"] = [i for i in self.effect["ids"] if i not in fids]
        if not self.effect["ids"]:
            self.effect["type"] = "none"

    def state(self) -> dict:
        from . import __version__
        return {
            "version": __version__,
            "raw": {str(ch + 1): v for ch, v in sorted(self.raw.items())},
            "fixtures": [f.to_dict() for f in self.fixtures],
            "profiles": self.profiles,
            "menu_profiles": self.menu_profiles(),
            "recent_models": self.recent_models,
            "scenes": {k: {"fixtures": len(v["fixtures"])} for k, v in self.scenes.items()},
            "output": self.output.info(),
            "output_cfg": self.output_cfg,
            "output_types": list(OUTPUT_TYPES),
            "master": self.master,
            "blackout": self.blackout,
            "effect": self.effect,
            "static_colors": self.static_colors,
            "effects": EFFECTS,
            "preset_count": PRESET_COUNT,
            "programs": [{"n": i + 1, "name": name, "group": grp, "range": [lo, hi]}
                         for i, (name, grp, lo, hi) in enumerate(PROGRAMS)],
            "preset_fixtures": [f.id for f in self.fixtures if has_presets(self.profiles.get(f.profile, []))],
            "strobe_fixtures": [f.id for f in self.fixtures if "strobe" in self.profiles.get(f.profile, [])],
            "strobe": self.strobe,
            "hotkeys": self.hotkeys,
            "load_warning": self.load_warning,
            "undo": self._undo[-1][0] if self._undo else None,
            "redo": self._redo[-1][0] if self._redo else None,
            "overlaps": find_overlaps(self.fixtures, self.profiles),
        }

    # -------------------------------------------------------- commands ----
    def handle(self, msg: dict) -> None:
        """Застосовує команду від клієнта. Кидає ValueError/KeyError при помилці."""
        cmd = msg.get("cmd")
        handler = getattr(self, f"cmd_{cmd}", None)
        if handler is None:
            raise ValueError(f"невідома команда {cmd!r}")
        pushed = False
        if cmd not in NO_UNDO:
            ids = msg.get("ids")
            # зливаються лише серії руху повзунка; дискретні дії (додати прилад, вибрати пресет чи
            # тип ефекту) — завжди окремі кроки, навіть якщо зроблені швидко одна за одною
            key = (cmd, tuple(sorted(map(str, ids))) if ids else None,
                   tuple(sorted(k for k in msg if k not in ("cmd", "ids"))),
                   msg.get("index"), msg.get("id"), msg.get("name"), msg.get("n"), msg.get("type"))
            now = time.monotonic()
            if (cmd not in MERGEABLE or key != self._undo_key or now - self._undo_t > UNDO_MERGE_S):
                self._undo.append((cmd, self._snapshot()))
                del self._undo[:-UNDO_LIMIT]
                pushed = True
            self._undo_key, self._undo_t = key, now
        try:
            handler(msg)
        except Exception:
            if pushed:  # команда не виконалась — і кроку скасування немає
                self._undo.pop()
                self._undo_key = None
            raise
        if cmd not in NO_UNDO:
            self._redo.clear()
        self._dirty_save = True

    # ------------------------------------------------------------ undo ----
    def _snapshot(self) -> dict:
        return copy.deepcopy({
            "fixtures": [f.to_dict() for f in self.fixtures],
            "master": self.master, "blackout": self.blackout, "effect": self.effect,
            "scenes": self.scenes, "static_colors": self.static_colors, "profiles": self.profiles,
            "device_profiles": sorted(self.device_profiles),
        })

    def _restore(self, snap: dict) -> None:
        snap = copy.deepcopy(snap)
        self.fixtures = [Fixture.from_dict(f) for f in snap["fixtures"]]
        self.master, self.blackout, self.effect = snap["master"], snap["blackout"], snap["effect"]
        self.scenes, self.static_colors, self.profiles = snap["scenes"], snap["static_colors"], snap["profiles"]
        self.device_profiles = set(snap.get("device_profiles", []))
        self._fade = None
        self._undo_key = None

    def cmd_undo(self, m):
        if not self._undo:
            raise ValueError("Немає дій для скасування")
        cmd, snap = self._undo.pop()
        self._redo.append((cmd, self._snapshot()))
        self._restore(snap)
        self.last_undo = cmd

    def cmd_redo(self, m):
        if not self._redo:
            raise ValueError("Немає дій для повторення")
        cmd, snap = self._redo.pop()
        self._undo.append((cmd, self._snapshot()))
        self._restore(snap)
        self.last_undo = cmd

    def cmd_set_color(self, m):
        self._fade = None
        values = {k: _byte(m[k]) for k in STATE_KEYS + ("strobe",) if k in m}
        if "hex" in m:
            values["r"], values["g"], values["b"] = hex_to_rgb(m["hex"])
        rgb_keys = [k for k in ("r", "g", "b") if k in values]
        whole, segs = self._resolve(m.get("ids"))
        for f in whole:
            for k, v in values.items():
                setattr(f, k, v)
            if rgb_keys:  # колір на весь прилад скидає кольори сегментів і пресет
                f.segs = None
                f.preset = None
        for f, k in segs:
            if rgb_keys:
                f.preset = None
                cur = f.seg_color(k)
                f.set_seg(k, [values.get(c, cur[c]) for c in ("r", "g", "b")], self._segments(f))
            for key, v in values.items():  # диммер, білий тощо — спільні для приладу
                if key not in ("r", "g", "b"):
                    setattr(f, key, v)

    def cmd_preset(self, m):
        """Вбудована програма приладу: n = 1..PRESET_COUNT, 0/None — вимкнути;
        speed (0..255) — швидкість програми. Без "n" змінюється лише швидкість.

        Вибрані сегменти означають їхній прилад; без вибору — усі бари.
        """
        set_n = "n" in m
        n = int(m["n"]) if m.get("n") else None
        if n is not None:
            preset_level(n)  # перевірка діапазону
        speed = _byte(m["speed"]) if "speed" in m else None
        whole, segs = self._resolve(m.get("ids"))
        targets = {f.id: f for f in whole + [f for f, _ in segs] if self._has_presets(f)}
        if not targets and not m.get("ids"):
            targets = {f.id: f for f in self.fixtures if self._has_presets(f)}
        if not targets:
            raise ValueError("Пресети доступні лише приладам з каналом програми")
        self._fade = None
        for f in targets.values():
            if set_n:
                f.preset = n
            if speed is not None:
                f.speed = speed
        if set_n and n is not None:
            self._drop_from_effect(list(targets))

    def cmd_clear(self, m):
        """Очищає кольори: вибрані прилади/сегменти, або всі, якщо нічого не вибрано."""
        self._fade = None
        whole, segs = self._resolve(m.get("ids"))
        if not whole and not segs:
            whole = list(self.fixtures)
        for f in whole:
            f.r = f.g = f.b = f.w = f.a = f.uv = f.strobe = 0
            f.segs = None
            f.preset = None
        for f, k in segs:
            f.preset = None
            f.set_seg(k, (0, 0, 0), self._segments(f))
        self._drop_from_effect([f.id for f in whole] + [f.id for f, _ in segs])

    def cmd_static_color(self, m):
        """Заливає прилади статичним кольором і знімає з них ефект.

        m: {ids (порожньо — усі прилади), index — номер збереженого кольору
        або hex [+ hex_w, w]}.
        """
        if "index" in m:
            preset = self._static(m["index"])
        else:
            preset = {k: m[k] for k in ("hex", "hex_w", "w") if k in m}
        rgb = hex_to_rgb(preset["hex"])
        w = _byte(preset.get("w", 0))
        rgb_w = hex_to_rgb(preset.get("hex_w") or preset["hex"])
        targets, segs = self._resolve(m.get("ids"))
        if not targets and not segs:
            targets = list(self.fixtures)
        self._fade = None
        for f in targets:
            has_w = "w" in self.profiles.get(f.profile, [])
            f.r, f.g, f.b = rgb_w if has_w and w else rgb
            f.w = w if has_w else 0
            f.a = f.uv = 0
            f.segs = None
            f.preset = None
        for f, k in segs:
            f.preset = None
            f.set_seg(k, rgb, self._segments(f))
        self._drop_from_effect([f.id for f in targets] + [f.id for f, _ in segs])

    def cmd_add_static_color(self, m):
        name = str(m.get("name") or "").strip() or m["hex"]
        entry = {"name": name[:40], "hex": m["hex"]}
        hex_to_rgb(entry["hex"])
        if int(m.get("w", 0)):
            entry["w"] = _byte(m["w"])
            entry["hex_w"] = m["hex"]
        if len(self.static_colors) >= 48:
            raise ValueError("забагато статичних кольорів (максимум 48)")
        self.static_colors.append(entry)

    def _static(self, index) -> dict:
        """Збережений колір за номером. Список міг змінитися на іншому пристрої — тоді зрозуміла помилка."""
        try:
            return self.static_colors[int(index)]
        except (IndexError, TypeError, ValueError):
            raise ValueError("цього кольору вже немає — список кольорів змінився") from None

    def cmd_rename_static_color(self, m):
        name = str(m.get("name") or "").strip()
        if not name:
            raise ValueError("назва не може бути порожньою")
        self._static(m["index"])["name"] = name[:40]

    def cmd_delete_static_color(self, m):
        self.static_colors.remove(self._static(m["index"]))

    def cmd_reset_static_colors(self, m):
        self.static_colors = [dict(c) for c in DEFAULT_STATIC_COLORS]

    def cmd_set_master(self, m):
        self.master = _byte(m["value"])

    def cmd_strobe(self, m):
        """Кнопка «Строб»: on — увімкнути/вимкнути (без on — перемкнути);
        ids — прилади (порожньо — усі). Діє лише на прилади з каналом строба."""
        on = m.get("on", not self.strobe["on"])
        if not isinstance(on, bool):
            raise ValueError("on має бути true або false")
        ids = []
        if on:
            whole, segs = self._resolve(m.get("ids"))
            ids = sorted({f.id for f in whole} | {f.id for f, _ in segs})
            able = [f for f in self.fixtures if "strobe" in self.profiles.get(f.profile, [])
                    and (not ids or f.id in ids)]
            if not able:
                raise ValueError("Строб доступний лише приладам з каналом строба")
            ids = [f.id for f in able] if ids else []
        self.strobe = {"on": on, "ids": ids}

    def cmd_set_hotkeys(self, m):
        """Власні гарячі клавіші: {дія: [комбінації]}. Порожньо — усі стандартні."""
        self.hotkeys = _hotkeys(m.get("hotkeys") or {})

    def cmd_blackout(self, m):
        self.blackout = bool(m.get("on", not self.blackout))

    def _profile_from(self, m) -> tuple[str, dict | None]:
        """Профіль і модель приладу з команди.

        Профіль моделі бібліотеки приходить разом із каналами (channels) і моделлю (model);
        він належить приладу і в меню профілів не потрапляє.
        """
        model = _model(m.get("model"))
        if m.get("channels") is None:
            name = self._ensure_profile(str(m.get("profile", "")))
            if name not in self.profiles:
                raise ValueError(f"невідомий профіль «{name}»")
            return name, model if self._is_device(name) else None
        channels = [str(c).strip() for c in m["channels"]]
        validate_profile(channels)
        name = str(m.get("profile") or "").strip()
        if not name and model:
            name = f"{model['m']} {model['n']} · {model['mode']} ({len(channels)} кан.)"
        if not name:
            raise ValueError("вкажіть назву профілю")
        base, k = name, 2
        while name in self.profiles and self.profiles[name] != channels:
            name, k = f"{base} ({k})", k + 1
        if name not in self.profiles:
            self.profiles[name] = channels
            self.device_profiles.add(name)
        return name, model if self._is_device(name) else None

    def cmd_add_fixture(self, m):
        count = max(1, min(64, int(m.get("count", 1))))
        profile, model = self._profile_from(m)
        width = len(self.profiles[profile])
        address = int(m["address"])
        new = []
        for i in range(count):
            name = str(m.get("name") or "Прожектор").strip()[:80] or "Прожектор"
            if count > 1 or not m.get("name"):
                name = f"{name} {len(self.fixtures) + len(new) + 1}"
            fx = Fixture(id=uuid.uuid4().hex[:8], name=name, address=address + i * width,
                         profile=profile, model=dict(model) if model else None)
            validate_fixture(fx, self.profiles)
            new.append(fx)
        self.fixtures.extend(new)
        if model:
            self._remember(model)

    def cmd_update_fixture(self, m):
        fx = self._fx(m["id"])
        changes = {k: m[k] for k in ("name", "address") if k in m}
        if "name" in changes:
            changes["name"] = str(changes["name"]).strip()[:80] or fx.name
        model = fx.model
        if "profile" in m or "channels" in m:
            profile, new_model = self._profile_from(m)
            if profile != fx.profile or "model" in m:
                model = new_model
            changes["profile"] = profile
        trial = Fixture.from_dict({**fx.to_dict(), **changes})
        trial.address = int(trial.address)
        validate_fixture(trial, self.profiles)
        if trial.profile != fx.profile:
            fx.segs = None
        fx.name, fx.address, fx.profile = trial.name, trial.address, trial.profile
        fx.model = dict(model) if model and self._is_device(fx.profile) else None
        if fx.model and "model" in m:
            self._remember(fx.model)
        if not self._has_presets(fx):
            fx.preset = None

    def cmd_delete_fixture(self, m):
        self.fixtures = [f for f in self.fixtures if f.id != m["id"]]
        self.effect["ids"] = [i for i in self.effect["ids"] if i != m["id"]]

    def cmd_move_fixture(self, m):
        fx = self._fx(m["id"])
        i = self.fixtures.index(fx)
        j = max(0, min(len(self.fixtures) - 1, i + int(m.get("delta", 0))))
        self.fixtures.insert(j, self.fixtures.pop(i))

    def cmd_save_profile(self, m):
        name = str(m["name"]).strip()
        if not name:
            raise ValueError("вкажіть назву профілю")
        if name in DEFAULT_PROFILES:
            raise ValueError("вбудований профіль не можна змінити")
        if not isinstance(m["channels"], list):
            raise ValueError("канали профілю — це список")
        channels = [str(c).strip() for c in m["channels"]]
        validate_profile(channels)
        if m.get("assign_to"):  # одразу призначити профіль приладу
            fx = self._fx(m["assign_to"])
            trial = Fixture.from_dict({**fx.to_dict(), "profile": name})
            validate_fixture(trial, {**self.profiles, name: channels})
            self.profiles[name] = channels
            self.device_profiles.discard(name)
            fx.profile = name
            fx.segs = None
            fx.model = None
        else:
            self.profiles[name] = channels
            self.device_profiles.discard(name)

    def cmd_raw_set(self, m):
        """Тест каналів: виставити DMX-адресу (1..512) вручну поверх усього."""
        addr = int(m["address"])
        if not 1 <= addr <= DMX_CHANNELS:
            raise ValueError("адреса має бути 1..512")
        self.raw[addr - 1] = _byte(m["value"])

    def cmd_raw_clear(self, m):
        addrs = m.get("addresses")
        if addrs is None:
            self.raw.clear()
        else:
            for a in addrs:
                self.raw.pop(int(a) - 1, None)

    def cmd_delete_profile(self, m):
        name = m["name"]
        if any(f.profile == name for f in self.fixtures):
            raise ValueError("профіль використовується приладами")
        if name in DEFAULT_PROFILES:
            raise ValueError("вбудований профіль не можна видалити")
        self.profiles.pop(name, None)

    def cmd_set_effect(self, m):
        kind = m.get("type", self.effect["type"])
        if kind not in EFFECTS:
            raise ValueError(f"невідомий ефект {kind!r}")
        cur = _clean_effect(self.effect) or {"ids": [], "speed": 0.5, "spread": 1.0, "colors": [], "by_segment": True}
        colors = m["colors"] if "colors" in m else cur["colors"]
        for c in colors:   # перевіряємо лише те, що надіслав клієнт; старі кольори вже очищені
            hex_to_rgb(c)
        self.effect = {
            "type": kind,
            "ids": list(m.get("ids", cur["ids"])),
            "speed": max(0.01, min(20.0, float(m.get("speed", cur["speed"])))),
            "spread": max(0.0, min(1.0, float(m.get("spread", cur["spread"])))),
            "colors": colors[:16],
            "by_segment": bool(m.get("by_segment", cur["by_segment"])),
        }

    def cmd_save_scene(self, m):
        name = str(m["name"]).strip()
        if not name:
            raise ValueError("вкажіть назву сцени")
        self.scenes[name] = {
            "fixtures": {f.id: {**{k: getattr(f, k) for k in STATE_KEYS}, "segs": f.segs, "preset": f.preset,
                              "speed": f.speed}
                         for f in self.fixtures},
            "effect": dict(self.effect) if m.get("with_effect") else None,
        }

    def cmd_recall_scene(self, m):
        scene = self.scenes[m["name"]]
        fade = max(0.0, float(m.get("fade", 0)))
        targets = {}
        for fid, vals in scene["fixtures"].items():
            try:
                fx = self._fx(fid)
            except KeyError:
                continue
            targets[fid] = ({**{k: getattr(fx, k) for k in STATE_KEYS}, "segs": fx.segs, "preset": fx.preset}, vals)
        effect = _clean_effect(scene.get("effect"))
        if effect:
            self.effect = effect
        if fade > 0:
            self._fade = {"start": time.monotonic(), "dur": fade, "targets": targets}
        else:
            self._apply_fade(targets, 1.0)
            self._fade = None

    def cmd_delete_scene(self, m):
        self.scenes.pop(m["name"], None)

    # ------------------------------------------------- сцена у файлі ----
    def pop_notice(self) -> str | None:
        note, self._notice = self._notice, None
        return note

    def export_scene(self, name: str) -> dict:
        """Сцена як самодостатній файл: стан + опис приладів (адреса, канали, модель)."""
        from . import __version__
        scene = self.scenes[name]
        by_id = {f.id: f for f in self.fixtures}
        fixtures = []
        for fid, vals in scene["fixtures"].items():
            fx = by_id.get(fid)
            item = {"id": fid, "state": vals}
            if fx is not None:
                item.update(name=fx.name, address=fx.address, profile=fx.profile,
                            channels=list(self.profiles.get(fx.profile, [])), model=fx.model)
            fixtures.append(item)
        return {"format": SCENE_FORMAT, "version": 1, "app": __version__, "name": name,
                "fixtures": fixtures, "effect": scene.get("effect")}

    def cmd_import_scene(self, m):
        # усе або нічого: якщо файл зіпсований посередині, додані прилади й профілі прибираються
        snap = self._snapshot()
        try:
            self._import_scene(m)
        except Exception:
            self._restore(snap)
            raise

    def _import_scene(self, m):
        """Сцена з файлу іншого комп'ютера.

        Прилади файлу зіставляються з тутешніми: за id, далі за адресою й каналами, далі за
        назвою й каналами. Прилад, якого тут немає, додається на ту саму адресу, якщо вона вільна.
        """
        data = m.get("data")
        if not isinstance(data, dict) or data.get("format") not in {SCENE_FORMAT, *LEGACY_SCENE_FORMATS}:
            raise ValueError("це не файл сцени Nitor")
        if not isinstance(data.get("fixtures"), list):
            raise ValueError("файл сцени пошкоджено")
        used: set[str] = set()
        mapping: dict[str, str] = {}
        added = skipped = 0

        def free(fx_id: str) -> Fixture | None:
            return next((f for f in self.fixtures if f.id == fx_id and f.id not in used), None)

        def same_ch(f: Fixture, ch) -> bool:
            return ch is None or self.profiles.get(f.profile) == ch

        items = [i for i in data["fixtures"]
                 if isinstance(i, dict) and isinstance(i.get("state"), dict) and i.get("id") is not None]
        pending = []
        for it in items:
            ch = it.get("channels")
            ch = [str(c) for c in ch] if isinstance(ch, list) and ch else None
            it["_ch"] = ch
            f = free(str(it.get("id", "")))
            if f is not None and not same_ch(f, ch):
                f = None
            if f is None and ch:
                f = next((x for x in self.fixtures if x.id not in used and x.address == it.get("address")
                          and same_ch(x, ch)), None)
            if f is None and ch and it.get("name"):
                f = next((x for x in self.fixtures if x.id not in used and x.name == it.get("name")
                          and same_ch(x, ch)), None)
            if f is None:
                pending.append(it)
                continue
            used.add(f.id)
            mapping[str(it["id"])] = f.id
        for it in pending:   # приладів немає — додаємо на їхні адреси, якщо ті вільні
            ch = it["_ch"]
            try:
                address = int(it.get("address"))
                if ch is None:
                    raise ValueError
                validate_profile(ch)
            except (TypeError, ValueError):
                skipped += 1
                continue
            end = address + len(ch) - 1
            busy = any(address <= f.address + len(self.profiles.get(f.profile, [])) - 1 and f.address <= end
                       for f in self.fixtures)
            if address < 1 or end > DMX_CHANNELS or busy:
                skipped += 1
                continue
            profile, model = self._import_profile(str(it.get("profile") or ""), ch, _model(it.get("model")))
            fx = Fixture(id=uuid.uuid4().hex[:8], name=str(it.get("name") or "Прожектор")[:80],
                         address=address, profile=profile, model=model)
            self.fixtures.append(fx)
            used.add(fx.id)
            mapping[str(it["id"])] = fx.id
            added += 1
        if not mapping:
            raise ValueError("жоден прилад зі сцени не вдалося зіставити: адреси зайняті іншими приладами")

        states = {}
        for it in items:
            fid = mapping.get(str(it.get("id")))
            if fid:
                states[fid] = _scene_state(it["state"], self._segments(self._fx(fid)))
        effect = _clean_effect(data.get("effect"))
        if effect:
            effect["ids"] = [mapping[i] for i in effect["ids"] if i in mapping]
        name = str(m.get("name") or data.get("name") or "Сцена").strip()[:80] or "Сцена"
        base, k = name, 2
        while name in self.scenes:
            name, k = f"{base} ({k})", k + 1
        self.scenes[name] = {"fixtures": states, "effect": effect}
        parts = [f"зіставлено приладів: {len(mapping) - added}"]
        if added:
            parts.append(f"додано: {added}")
        if skipped:
            parts.append(f"пропущено (адреса зайнята): {skipped}")
        self._notice = f"Сцену «{name}» відкрито з файлу · " + ", ".join(parts)

    def _import_profile(self, name: str, channels: list[str], model: dict | None) -> tuple[str, dict | None]:
        """Профіль для приладу з файлу сцени: наявний з тими самими каналами або новий."""
        if model:
            return self._profile_from({"profile": name, "channels": channels, "model": model})
        for n, ch in self.profiles.items():   # стандартний або власний профіль з такими ж каналами
            if ch == channels and not self._is_device(n):
                return n, None
        name = name or f"Профіль ({len(channels)} кан.)"
        base, k = name, 2
        while name in self.profiles:
            name, k = f"{base} ({k})", k + 1
        self.profiles[name] = channels
        return name, None

    def cmd_set_output(self, m):
        cfg = {k: v for k, v in m.items() if k != "cmd"}
        if cfg.get("type") not in OUTPUT_TYPES:
            raise ValueError("невідомий тип виходу")
        self.output.stop()
        self.output_cfg = cfg
        self.output = create_output(cfg)
        self.output.start()

    # ----------------------------------------------------------- render ---
    def _apply_fade(self, targets, k):
        for fid, (start, end) in targets.items():
            fx = next((f for f in self.fixtures if f.id == fid), None)
            if fx is None:
                continue
            for key in STATE_KEYS:
                a, b = start.get(key, 0), end.get(key, 0)
                setattr(fx, key, int(round(a + (b - a) * k)))
            if k >= 1.0:
                fx.segs = [list(s) if s else None for s in end["segs"]] if end.get("segs") else None
                fx.preset = end.get("preset")
                fx.speed = end.get("speed", fx.speed)
            elif start.get("segs") or end.get("segs"):
                n = self._segments(fx)
                s0, s1 = _seg_rgbs(start, n), _seg_rgbs(end, n)
                fx.segs = [[int(round(a + (b - a) * k)) for a, b in zip(p, q)] for p, q in zip(s0, s1)]

    def render(self, now: float | None = None) -> bytes:
        now = time.monotonic() if now is None else now
        if self._fade:
            k = min(1.0, (now - self._fade["start"]) / self._fade["dur"])
            self._apply_fade(self._fade["targets"], k)
            if k >= 1.0:
                self._fade = None

        uni = bytearray(DMX_CHANNELS)
        live = {}
        t = now - self._t0
        eff = self.effect
        by_id = {f.id: f for f in self.fixtures}
        # «пікселі» ефекту: кожен сегмент кожного приладу (або прилад цілком)
        pixel = {}
        if eff["type"] != "none":
            for fid in eff["ids"]:
                fx = by_id.get(fid)
                if fx is None:
                    continue
                if eff.get("by_segment", True):
                    for k in range(self._segments(fx)):
                        pixel[(fid, k)] = len(pixel)
                else:
                    idx = len({p for (f, _), p in pixel.items()})
                    for k in range(self._segments(fx)):
                        pixel[(fid, k)] = idx
        count = len(set(pixel.values()))
        master = 0.0 if self.blackout else self.master / 255.0
        for fx in self.fixtures:
            channels = self.profiles.get(fx.profile)
            if not channels:
                continue
            if self.strobe["on"] and "strobe" in channels and (not self.strobe["ids"] or fx.id in self.strobe["ids"]):
                fx = replace(fx, strobe=fx.strobe or STROBE_LEVEL)
            if fx.preset and has_presets(channels):
                # профіль з каналом програми (A001 / H001): програма — у свій канал
                n_seg = segment_count(channels)
                render_fixture(uni, fx, channels, [fx.seg_color(k) for k in range(n_seg)], master)
                rgb = _program_rgb(fx.preset)
                lvl = (fx.dimmer / 255.0 if "dim" in channels else 1.0) * master
                live[fx.id] = [[round(c * lvl) for c in rgb] + [0]] * n_seg
                continue
            colors = []
            for k in range(segment_count(channels)):
                c = fx.seg_color(k)
                if (fx.id, k) in pixel:
                    c = effect_color(eff, pixel[(fx.id, k)], count, t, c)
                colors.append(c)
            render_fixture(uni, fx, channels, colors, master)
            lvl = fx.dimmer / 255.0 * master
            live[fx.id] = [[round(min(255.0, c[ch] * lvl)) for ch in ("r", "g", "b", "w")] for c in colors]
        for ch, v in self.raw.items():
            uni[ch] = v
        self.universe = uni
        self.live = live
        return bytes(uni)

    # ------------------------------------------------------------- loop ---
    async def run(self) -> None:
        self.output.start()
        period = 1.0 / FPS
        last_save = time.monotonic()
        while True:
            started = time.monotonic()
            try:
                self.output.set_frame(self.render(started))
            except Exception:  # noqa: BLE001
                log.exception("Помилка рендеру")
            if self._dirty_save and started - last_save > 1.0:
                try:
                    self.save()
                except OSError:
                    log.exception("Не вдалося зберегти конфігурацію")
                last_save = started
            await asyncio.sleep(max(0.0, period - (time.monotonic() - started)))

    def shutdown(self, blackout: bool = True) -> None:
        if self._dirty_save:
            self.save()
        if blackout:  # перед вимкненням гасимо світло
            self.output.set_frame(bytes(DMX_CHANNELS))
            time.sleep(0.1)
        self.output.stop()
