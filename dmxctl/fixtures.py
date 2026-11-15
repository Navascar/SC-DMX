"""Прилади (прожектори), профілі каналів і рендер у DMX-всесвіт."""
from __future__ import annotations

from dataclasses import asdict, dataclass, fields

COLOR_KEYS = ("r", "g", "b", "w", "a", "uv")

# Ролі каналів:
#   r g b w a uv — колірні канали;  dim — загальний диммер приладу;
#   strobe — апаратний строб;  zero — завжди 0;  full — завжди 255.
ROLES = set(COLOR_KEYS) | {"dim", "strobe", "zero", "full"}

DEFAULT_PROFILES: dict[str, list[str]] = {
    "RGB (3 кан.)": ["r", "g", "b"],
    "RGBW (4 кан.)": ["r", "g", "b", "w"],
    "Dim+RGB (4 кан.)": ["dim", "r", "g", "b"],
    "RGB+Dim (4 кан.)": ["r", "g", "b", "dim"],
    "Dim+RGB+Strobe (5 кан.)": ["dim", "r", "g", "b", "strobe"],
    "Dim+RGBW+Strobe (6 кан.)": ["dim", "r", "g", "b", "w", "strobe"],
    "RGBWA+UV (6 кан.)": ["r", "g", "b", "w", "a", "uv"],
    "Dim+RGBWA+UV+Strobe (8 кан.)": ["dim", "r", "g", "b", "w", "a", "uv", "strobe"],
}


@dataclass
class Fixture:
    id: str
    name: str
    address: int                 # 1..512
    profile: str
    r: int = 0
    g: int = 0
    b: int = 0
    w: int = 0
    a: int = 0
    uv: int = 0
    dimmer: int = 255
    strobe: int = 0

    @classmethod
    def from_dict(cls, d: dict) -> "Fixture":
        names = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in d.items() if k in names})

    def to_dict(self) -> dict:
        return asdict(self)

    def color(self) -> dict[str, float]:
        return {k: float(getattr(self, k)) for k in COLOR_KEYS}


def clamp8(v: float) -> int:
    return 0 if v <= 0 else 255 if v >= 255 else int(round(v))


def validate_profile(channels: list[str]) -> None:
    if not channels or len(channels) > 64:
        raise ValueError("профіль має містити 1..64 каналів")
    bad = [c for c in channels if c not in ROLES]
    if bad:
        raise ValueError(f"невідомі ролі каналів: {', '.join(bad)}")


def validate_fixture(fx: Fixture, profiles: dict[str, list[str]]) -> None:
    if fx.profile not in profiles:
        raise ValueError(f"невідомий профіль «{fx.profile}»")
    n = len(profiles[fx.profile])
    if not 1 <= fx.address <= 512 - n + 1:
        raise ValueError(f"адреса має бути в межах 1..{512 - n + 1} для профілю з {n} каналів")


def render_fixture(universe: bytearray, fx: Fixture, channels: list[str],
                   color: dict[str, float], master: float) -> None:
    """Записує прилад у всесвіт.

    color — значення 0..255 для r/g/b/w/a/uv (вже з урахуванням ефектів);
    master — 0..1. Якщо в профілі є канал dim, яскравість іде туди,
    інакше колірні канали масштабуються програмно.
    """
    has_dim = "dim" in channels
    level = fx.dimmer / 255.0 * master
    # при нульовому рівні гасимо і кольорові канали — на випадок, якщо прилад ігнорує диммер
    scale = 1.0 if has_dim and level > 0 else level
    base = fx.address - 1
    for i, role in enumerate(channels):
        ch = base + i
        if ch >= len(universe):
            break
        if role in COLOR_KEYS:
            v = color.get(role, 0.0) * scale
        elif role == "dim":
            v = 255.0 * level
        elif role == "strobe":
            v = fx.strobe
        elif role == "full":
            v = 255
        else:
            v = 0
        universe[ch] = clamp8(v)


def find_overlaps(fixtures: list[Fixture], profiles: dict[str, list[str]]) -> list[tuple[str, str]]:
    """Пари приладів, у яких перетинаються діапазони адрес."""
    spans = []
    for fx in fixtures:
        n = len(profiles.get(fx.profile, []))
        spans.append((fx.address, fx.address + n - 1, fx))
    spans.sort(key=lambda s: s[0])
    out = []
    for i, (s1, e1, f1) in enumerate(spans):
        for s2, e2, f2 in spans[i + 1:]:
            if s2 > e1:
                break
            out.append((f1.id, f2.id))
    return out
