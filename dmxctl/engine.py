"""Рушій: стан шоу, рендер кадрів, сцени з кросфейдом, збереження конфігурації."""
from __future__ import annotations

import asyncio
import json
import logging
import os
import time
import uuid
from pathlib import Path

from .effects import EFFECTS, effect_color, hex_to_rgb
from .fixtures import (COLOR_KEYS, DEFAULT_PROFILES, Fixture, find_overlaps,
                       render_fixture, validate_fixture, validate_profile)
from .outputs import DMX_CHANNELS, OUTPUT_TYPES, create_output

log = logging.getLogger(__name__)

FPS = 40

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


def _byte(v) -> int:
    v = int(v)
    if not 0 <= v <= 255:
        raise ValueError("значення має бути 0..255")
    return v


class Engine:
    def __init__(self, config_path: str | os.PathLike):
        self.config_path = Path(config_path)
        self.profiles: dict[str, list[str]] = dict(DEFAULT_PROFILES)
        self.fixtures: list[Fixture] = []
        self.scenes: dict[str, dict] = {}
        self.static_colors: list[dict] = [dict(c) for c in DEFAULT_STATIC_COLORS]
        self.output_cfg: dict = {"type": "udmx"}
        self.master = 255
        self.blackout = False
        self.effect: dict = {"type": "none", "ids": [], "speed": 0.5, "spread": 1.0, "colors": []}
        self.universe = bytearray(DMX_CHANNELS)
        self.live: dict[str, list[int]] = {}   # реальні кольори приладів для превʼю
        self._fade: dict | None = None
        self._t0 = time.monotonic()
        self._dirty_save = False
        self._listeners: set = set()
        self.load()
        self.output = create_output(self.output_cfg)

    # ------------------------------------------------------- persistence --
    def load(self) -> None:
        if not self.config_path.exists():
            self._demo_patch()
            return
        cfg = json.loads(self.config_path.read_text("utf-8"))
        self.profiles.update(cfg.get("profiles", {}))
        self.fixtures = [Fixture.from_dict(f) for f in cfg.get("fixtures", [])]
        self.scenes = cfg.get("scenes", {})
        if "static_colors" in cfg:
            self.static_colors = cfg["static_colors"]
        self.output_cfg = cfg.get("output", {"type": "udmx"})
        self.master = int(cfg.get("master", 255))

    def _demo_patch(self) -> None:
        for i in range(4):
            self.fixtures.append(Fixture(id=uuid.uuid4().hex[:8], name=f"Прожектор {i + 1}",
                                         address=1 + i * 4, profile="Dim+RGB (4 кан.)",
                                         r=255, g=120, b=40))
        self._dirty_save = True

    def save(self) -> None:
        custom = {k: v for k, v in self.profiles.items() if DEFAULT_PROFILES.get(k) != v}
        cfg = {
            "output": self.output_cfg,
            "master": self.master,
            "profiles": custom,
            "fixtures": [f.to_dict() for f in self.fixtures],
            "scenes": self.scenes,
            "static_colors": self.static_colors,
        }
        tmp = self.config_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), "utf-8")
        tmp.replace(self.config_path)
        self._dirty_save = False

    # --------------------------------------------------------- helpers ----
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

    def state(self) -> dict:
        from . import __version__
        return {
            "version": __version__,
            "fixtures": [f.to_dict() for f in self.fixtures],
            "profiles": self.profiles,
            "scenes": {k: {"fixtures": len(v["fixtures"])} for k, v in self.scenes.items()},
            "output": self.output.info(),
            "output_cfg": self.output_cfg,
            "output_types": list(OUTPUT_TYPES),
            "master": self.master,
            "blackout": self.blackout,
            "effect": self.effect,
            "static_colors": self.static_colors,
            "effects": EFFECTS,
            "overlaps": find_overlaps(self.fixtures, self.profiles),
        }

    # -------------------------------------------------------- commands ----
    def handle(self, msg: dict) -> None:
        """Застосовує команду від клієнта. Кидає ValueError/KeyError при помилці."""
        cmd = msg.get("cmd")
        handler = getattr(self, f"cmd_{cmd}", None)
        if handler is None:
            raise ValueError(f"невідома команда {cmd!r}")
        handler(msg)
        self._dirty_save = True

    def cmd_set_color(self, m):
        self._fade = None
        values = {k: _byte(m[k]) for k in STATE_KEYS + ("strobe",) if k in m}
        if "hex" in m:
            values["r"], values["g"], values["b"] = hex_to_rgb(m["hex"])
        for f in self._targets(m.get("ids")):
            for k, v in values.items():
                setattr(f, k, v)

    def cmd_static_color(self, m):
        """Заливає прилади статичним кольором і знімає з них ефект.

        m: {ids (порожньо — усі прилади), index — номер збереженого кольору
        або hex [+ hex_w, w]}.
        """
        if "index" in m:
            preset = self.static_colors[int(m["index"])]
        else:
            preset = {k: m[k] for k in ("hex", "hex_w", "w") if k in m}
        rgb = hex_to_rgb(preset["hex"])
        w = _byte(preset.get("w", 0))
        rgb_w = hex_to_rgb(preset.get("hex_w") or preset["hex"])
        targets = self._targets(m.get("ids")) or list(self.fixtures)
        self._fade = None
        for f in targets:
            has_w = "w" in self.profiles.get(f.profile, [])
            f.r, f.g, f.b = rgb_w if has_w and w else rgb
            f.w = w if has_w else 0
            f.a = f.uv = 0
        ids = {f.id for f in targets}
        self.effect["ids"] = [i for i in self.effect["ids"] if i not in ids]
        if not self.effect["ids"]:
            self.effect["type"] = "none"

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

    def cmd_delete_static_color(self, m):
        self.static_colors.pop(int(m["index"]))

    def cmd_reset_static_colors(self, m):
        self.static_colors = [dict(c) for c in DEFAULT_STATIC_COLORS]

    def cmd_set_master(self, m):
        self.master = _byte(m["value"])

    def cmd_blackout(self, m):
        self.blackout = bool(m.get("on", not self.blackout))

    def cmd_add_fixture(self, m):
        count = max(1, min(64, int(m.get("count", 1))))
        profile = m["profile"]
        if profile not in self.profiles:
            raise ValueError(f"невідомий профіль «{profile}»")
        width = len(self.profiles[profile])
        address = int(m["address"])
        new = []
        for i in range(count):
            name = m.get("name") or "Прожектор"
            if count > 1 or not m.get("name"):
                name = f"{name} {len(self.fixtures) + len(new) + 1}"
            fx = Fixture(id=uuid.uuid4().hex[:8], name=name, address=address + i * width,
                         profile=profile)
            validate_fixture(fx, self.profiles)
            new.append(fx)
        self.fixtures.extend(new)

    def cmd_update_fixture(self, m):
        fx = self._fx(m["id"])
        trial = Fixture.from_dict({**fx.to_dict(), **{k: m[k] for k in ("name", "address", "profile") if k in m}})
        trial.address = int(trial.address)
        validate_fixture(trial, self.profiles)
        fx.name, fx.address, fx.profile = trial.name, trial.address, trial.profile

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
        channels = [c.strip() for c in m["channels"]]
        validate_profile(channels)
        self.profiles[name] = channels

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
        colors = m.get("colors", self.effect["colors"])
        for c in colors:
            hex_to_rgb(c)
        self.effect = {
            "type": kind,
            "ids": list(m.get("ids", self.effect["ids"])),
            "speed": max(0.01, min(20.0, float(m.get("speed", self.effect["speed"])))),
            "spread": max(0.0, min(1.0, float(m.get("spread", self.effect["spread"])))),
            "colors": colors[:16],
        }

    def cmd_save_scene(self, m):
        name = str(m["name"]).strip()
        if not name:
            raise ValueError("вкажіть назву сцени")
        self.scenes[name] = {
            "fixtures": {f.id: {k: getattr(f, k) for k in STATE_KEYS} for f in self.fixtures},
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
            targets[fid] = ({k: getattr(fx, k) for k in STATE_KEYS}, vals)
        if scene.get("effect"):
            self.effect = dict(scene["effect"])
        if fade > 0:
            self._fade = {"start": time.monotonic(), "dur": fade, "targets": targets}
        else:
            self._apply_fade(targets, 1.0)
            self._fade = None

    def cmd_delete_scene(self, m):
        self.scenes.pop(m["name"], None)

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
        eff_ids = [i for i in eff["ids"] if any(f.id == i for f in self.fixtures)] if eff["type"] != "none" else []
        eff_index = {fid: n for n, fid in enumerate(eff_ids)}
        master = 0.0 if self.blackout else self.master / 255.0
        for fx in self.fixtures:
            channels = self.profiles.get(fx.profile)
            if not channels:
                continue
            color = fx.color()
            if fx.id in eff_index:
                color = effect_color(eff, eff_index[fx.id], len(eff_ids), t, color)
            render_fixture(uni, fx, channels, color, master)
            lvl = fx.dimmer / 255.0 * master
            live[fx.id] = [round(min(255.0, color[c] * lvl)) for c in ("r", "g", "b", "w")]
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
