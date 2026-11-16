"""Динамічні ефекти. Кожен ефект — чиста функція часу та позиції приладу в групі."""
from __future__ import annotations

import colorsys
import math
import random

EFFECTS = {
    "none": "Без ефекту",
    "rainbow": "Веселка",
    "fade": "Плавна зміна кольорів",
    "chase": "Біжучий вогонь",
    "pulse": "Пульсація",
    "strobe": "Стробоскоп",
    "random": "Випадкові кольори",
    "fire": "Вогонь",
}


def hex_to_rgb(h: str) -> tuple[int, int, int]:
    if not isinstance(h, str):
        raise ValueError(f"некоректний колір {h!r}")
    h = h.lstrip("#")
    if len(h) != 6:
        raise ValueError(f"некоректний колір {h!r}")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _rgb(r: float, g: float, b: float) -> dict[str, float]:
    return {"r": r, "g": g, "b": b, "w": 0.0, "a": 0.0, "uv": 0.0}


def _scaled(color: dict[str, float], k: float) -> dict[str, float]:
    return {key: v * k for key, v in color.items()}


def _lerp(c1, c2, t):
    return tuple(a + (b - a) * t for a, b in zip(c1, c2))


def effect_color(effect: dict, index: int, count: int, t: float,
                 base: dict[str, float]) -> dict[str, float]:
    """Колір приладу з номером index (0..count-1) у момент t (секунди).

    effect: {"type", "speed" (циклів/с), "spread" (0..1 — розкид фази між
    приладами), "colors" (список "#rrggbb"; порожній — власний колір приладу)}.
    base — власний колір приладу.
    """
    kind = effect.get("type", "none")
    speed = float(effect.get("speed", 0.5))
    spread = float(effect.get("spread", 1.0))
    palette = [hex_to_rgb(c) for c in effect.get("colors") or []]
    count = max(count, 1)
    offset = index / count * spread
    phase = t * speed + offset

    if kind == "rainbow":
        r, g, b = colorsys.hsv_to_rgb(phase % 1.0, 1.0, 1.0)
        return _rgb(r * 255, g * 255, b * 255)

    if kind == "fade":
        if not palette:
            palette = [(255, 0, 0), (0, 255, 0), (0, 0, 255)]
        pos = phase % 1.0 * len(palette)
        i = int(pos) % len(palette)
        frac = pos - int(pos)
        frac = 0.5 - 0.5 * math.cos(math.pi * frac)  # м'які переходи
        return _rgb(*_lerp(palette[i], palette[(i + 1) % len(palette)], frac))

    if kind == "chase":
        # «голова» пробігає по приладах, позаду — згасаючий хвіст
        head = (t * speed * count) % count
        dist = (head - index) % count
        k = max(0.0, 1.0 - dist / max(1.0, count * 0.35 * spread + 0.6))
        src = _rgb(*palette[int(t * speed) % len(palette)]) if palette else base
        return _scaled(src, k)

    if kind == "pulse":
        k = 0.5 - 0.5 * math.cos(2 * math.pi * phase)
        src = _rgb(*palette[int(phase) % len(palette)]) if palette else base
        return _scaled(src, k)

    if kind == "strobe":
        on = phase % 1.0 < 0.2
        src = _rgb(*palette[int(t * speed) % len(palette)]) if palette else base
        return src if on else _scaled(src, 0.0)

    if kind == "random":
        step = int(t * speed + offset)
        rng = random.Random(step * 7919 + index * 104729)
        if palette:
            return _rgb(*rng.choice(palette))
        r, g, b = colorsys.hsv_to_rgb(rng.random(), 1.0, 1.0)
        return _rgb(r * 255, g * 255, b * 255)

    if kind == "fire":
        n = (math.sin(t * speed * 7.3 + index * 1.7) + math.sin(t * speed * 13.1 + index * 3.1)
             + math.sin(t * speed * 23.7 + index * 0.7)) / 3.0
        k = 0.65 + 0.35 * n
        return _rgb(255 * k, (70 + 60 * n) * k, 0)

    return base
