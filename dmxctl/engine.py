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
                       render_fixture, segment_count, validate_fixture, validate_profile)
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


def _seg_rgbs(vals: dict, n: int) -> list[list[int]]:
    """Кольори n сегментів зі збереженого стану приладу (для кросфейду)."""
    base = [vals.get("r", 0), vals.get("g", 0), vals.get("b", 0)]
    segs = list(vals.get("segs") or [])
    return [list(segs[k]) if k < len(segs) and segs[k] else base for k in range(n)]


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
        self.load()
        self.output = create_output(self.output_cfg)

    # ------------------------------------------------------- persistence --
    def load(self) -> None:
        if not self.config_path.exists():
            return  # перший запуск: прилади додає користувач
        cfg = json.loads(self.config_path.read_text("utf-8"))
        self.profiles.update(cfg.get("profiles", {}))
        self.fixtures = [Fixture.from_dict(f) for f in cfg.get("fixtures", [])]
        self.scenes = cfg.get("scenes", {})
        if "static_colors" in cfg:
            self.static_colors = cfg["static_colors"]
        self.output_cfg = cfg.get("output", {"type": "udmx"})
        self.master = int(cfg.get("master", 255))

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
        rgb_keys = [k for k in ("r", "g", "b") if k in values]
        whole, segs = self._resolve(m.get("ids"))
        for f in whole:
            for k, v in values.items():
                setattr(f, k, v)
            if rgb_keys:  # колір на весь прилад скидає кольори сегментів
                f.segs = None
        for f, k in segs:
            if rgb_keys:
                cur = f.seg_color(k)
                f.set_seg(k, [values.get(c, cur[c]) for c in ("r", "g", "b")], self._segments(f))
            for key, v in values.items():  # диммер, білий тощо — спільні для приладу
                if key not in ("r", "g", "b"):
                    setattr(f, key, v)

    def cmd_clear(self, m):
        """Очищає кольори: вибрані прилади/сегменти, або всі, якщо нічого не вибрано."""
        self._fade = None
        whole, segs = self._resolve(m.get("ids"))
        if not whole and not segs:
            whole = list(self.fixtures)
        for f in whole:
            f.r = f.g = f.b = f.w = f.a = f.uv = f.strobe = 0
            f.segs = None
        for f, k in segs:
            f.set_seg(k, (0, 0, 0), self._segments(f))
        self._drop_from_effect([f.id for f in whole] + [f.id for f, _ in segs])

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
        for f, k in segs:
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

    def cmd_rename_static_color(self, m):
        name = str(m.get("name") or "").strip()
        if not name:
            raise ValueError("назва не може бути порожньою")
        self.static_colors[int(m["index"])]["name"] = name[:40]

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
        if name in DEFAULT_PROFILES:
            raise ValueError("вбудований профіль не можна змінити — дайте іншу назву")
        channels = [c.strip() for c in m["channels"]]
        validate_profile(channels)
        if m.get("assign_to"):  # одразу призначити профіль приладу
            fx = self._fx(m["assign_to"])
            trial = Fixture.from_dict({**fx.to_dict(), "profile": name})
            validate_fixture(trial, {**self.profiles, name: channels})
            self.profiles[name] = channels
            fx.profile = name
            fx.segs = None
        else:
            self.profiles[name] = channels

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
        colors = m.get("colors", self.effect["colors"])
        for c in colors:
            hex_to_rgb(c)
        self.effect = {
            "type": kind,
            "ids": list(m.get("ids", self.effect["ids"])),
            "speed": max(0.01, min(20.0, float(m.get("speed", self.effect["speed"])))),
            "spread": max(0.0, min(1.0, float(m.get("spread", self.effect["spread"])))),
            "colors": colors[:16],
            "by_segment": bool(m.get("by_segment", self.effect.get("by_segment", True))),
        }

    def cmd_save_scene(self, m):
        name = str(m["name"]).strip()
        if not name:
            raise ValueError("вкажіть назву сцени")
        self.scenes[name] = {
            "fixtures": {f.id: {**{k: getattr(f, k) for k in STATE_KEYS}, "segs": f.segs}
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
            targets[fid] = ({**{k: getattr(fx, k) for k in STATE_KEYS}, "segs": fx.segs}, vals)
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
            if k >= 1.0:
                fx.segs = [list(s) if s else None for s in end["segs"]] if end.get("segs") else None
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
