"""Збирає бібліотеку приладів SC DMX з відкритих баз описів DMX-приладів.

Джерела (локальні клони):
  * Open Fixture Library — https://github.com/OpenLightingProject/open-fixture-library (MIT)
  * QLC+ fixtures        — https://github.com/mcallegari/qlcplus/tree/master/resources/fixtures (Apache-2.0)

Кожен режим кожного приладу переводиться в ролі каналів програми:
  кольори (r g b w a uv), dim, strobe, «=N» (фіксоване значення) або zero.
Безпечні правила: канал строба/затвора ставиться на «відкрито», макроси та програми —
на «без функції», щоб прилад гарантовано слухався кольорів. Беруться лише прилади
з адитивним змішуванням кольорів (RGB/RGBW/…).

Запуск:
  python tools/build_library.py --ofl ../open-fixture-library --qlc ../qlcplus/resources/fixtures
Результат: dmxctl/library.json.gz
"""
from __future__ import annotations

import argparse
import gzip
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "dmxctl" / "library.json.gz"

COLOR_ROLE = {"red": "r", "green": "g", "blue": "b", "white": "w", "warm white": "w", "cold white": "w",
              "amber": "a", "uv": "uv", "ultraviolet": "uv"}
IGNORED_COLORS = {"lime", "cyan", "indigo", "magenta", "yellow", "lavender", "orange", "pink"}
NEUTRAL_TEXT = re.compile(r"no ?func|no ?effect|^off$|disabled|^none|rgb|manual|dimmer mode|open|default|dmx mode|standard",
                          re.I)


def color_role(name: str | None) -> str | None:
    if not name:
        return None
    n = name.strip().lower()
    if n in COLOR_ROLE:
        return COLOR_ROLE[n]
    if n in IGNORED_COLORS:
        return "zero"
    return None


def fixed(v) -> str:
    v = max(0, min(255, int(v)))
    return "zero" if v == 0 else f"={v}"


def usable(roles: list[str]) -> bool:
    s = set(roles)
    return {"r", "g", "b"} <= s or "w" in s


# ---------------------------------------------------------------- OFL ----
def ofl_value(v) -> int:
    """defaultValue: число, «50%» або «x%»."""
    if isinstance(v, (int, float)):
        return int(v)
    m = re.match(r"([\d.]+)%", str(v))
    return round(float(m.group(1)) * 2.55) if m else 0


def ofl_caps(ch: dict) -> list[dict]:
    if "capability" in ch:
        return [{**ch["capability"], "dmxRange": [0, 255]}]
    return ch.get("capabilities", [])


def ofl_role(ch: dict | None) -> str:
    if ch is None:
        return "zero"
    caps = ofl_caps(ch)
    if not caps:
        return "zero"
    first = caps[0]
    t = first.get("type")
    if len(caps) == 1 and t == "ColorIntensity":
        return color_role(first.get("color")) or "zero"
    if len(caps) == 1 and t == "Intensity":
        return "dim"
    at0 = next((c for c in caps if c.get("dmxRange", [0, 0])[0] == 0), first)
    if any(c.get("type") in ("ShutterStrobe", "StrobeSpeed", "StrobeDuration") for c in caps):
        opened = next((c for c in caps if c.get("type") == "ShutterStrobe" and c.get("shutterEffect") == "Open"), None)
        if at0.get("type") in ("NoFunction",) or (at0.get("shutterEffect") == "Open"):
            return "strobe"
        if opened:
            return fixed(opened["dmxRange"][0])
        return "strobe"
    if at0.get("type") == "NoFunction":
        return "zero"
    nofunc = next((c for c in caps if c.get("type") == "NoFunction"), None)
    if nofunc:
        return fixed(nofunc["dmxRange"][0])
    if t == "Intensity":
        return "dim"
    if "defaultValue" in ch:
        return fixed(ofl_value(ch["defaultValue"]))
    return "zero"


def ofl_pixel_count(fx: dict, repeat) -> int:
    if isinstance(repeat, list):
        return len(repeat)
    m = fx.get("matrix", {})
    if repeat == "eachPixelGroup":
        return max(1, len(m.get("pixelGroups", {})))
    if "pixelKeys" in m:
        return sum(1 for z in m["pixelKeys"] for y in z for x in y if x)
    if "pixelCount" in m:
        x, y, z = (m["pixelCount"] + [1, 1, 1])[:3]
        return x * y * z
    return 1


def load_ofl(root: Path) -> list[dict]:
    out = []
    makers = json.loads((root / "manufacturers.json").read_text("utf-8"))
    for path in sorted(root.glob("*/*.json")):
        maker = makers.get(path.parent.name, {}).get("name", path.parent.name)
        try:
            fx = json.loads(path.read_text("utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        chans = dict(fx.get("availableChannels", {}))
        fine = set()
        for name, ch in list(chans.items()):
            for alias in ch.get("fineChannelAliases", []):
                fine.add(alias)
            for alias in ch.get("switchChannels", {}):
                fine.add(alias)
        templates = fx.get("templateChannels", {})
        modes = []
        for mode in fx.get("modes", []):
            roles = []
            for item in mode.get("channels", []):
                if isinstance(item, dict) and item.get("insert") == "matrixChannels":
                    count = ofl_pixel_count(fx, item.get("repeatFor"))
                    tpl = [templates.get(t) if t not in fine else None for t in item.get("templateChannels", [])]
                    tpl_roles = [ofl_role(t) for t in tpl]
                    if item.get("channelOrder") == "perChannel":
                        roles += [r for r in tpl_roles for _ in range(count)]
                    else:
                        roles += tpl_roles * count
                elif item is None or item in fine:
                    roles.append("zero")
                else:
                    roles.append(ofl_role(chans.get(item)))
            if roles and usable(roles) and len(roles) <= 512:
                modes.append([mode.get("shortName") or mode.get("name") or f"{len(roles)}ch", roles])
        if modes:
            name = fx.get("name", path.stem)
            out.append({"m": maker, "n": name, "t": fixture_type((fx.get("categories") or [""])[0], name, modes),
                        "modes": modes})
    return out


# ---------------------------------------------------------------- QLC+ ---
QLC_COLOR = {"IntensityRed": "r", "IntensityGreen": "g", "IntensityBlue": "b", "IntensityWhite": "w",
             "IntensityAmber": "a", "IntensityUV": "uv", "IntensityWarmWhite": "w", "IntensityColdWhite": "w",
             "IntensityDimmer": "dim", "IntensityMasterDimmer": "dim",
             "IntensityCyan": "zero", "IntensityMagenta": "zero", "IntensityYellow": "zero",
             "IntensityLime": "zero", "IntensityIndigo": "zero"}


def qlc_role(ch: ET.Element, ns: str) -> str:
    preset = ch.get("Preset") or ""
    if preset in QLC_COLOR:
        return QLC_COLOR[preset]
    if preset.endswith("Fine") or preset.startswith("Position") or preset.startswith("Speed"):
        return "zero"
    group = ch.find(ns + "Group")
    gname = (group.text or "").strip() if group is not None else ""
    if gname == "Intensity":
        if group is not None and group.get("Byte") == "1":
            return "zero"
        col = ch.find(ns + "Colour")
        return color_role(col.text if col is not None else None) or "dim"
    caps = [(int(c.get("Min", 0)), int(c.get("Max", 255)), c.get("Preset") or "", (c.text or "").strip())
            for c in ch.findall(ns + "Capability")]
    at0 = next((c for c in caps if c[0] == 0), None)
    if gname == "Shutter" or any(p.startswith(("Shutter", "Strobe")) for _, _, p, _ in caps):
        if at0 and (at0[2] in ("ShutterOpen", "NoFunction") or NEUTRAL_TEXT.search(at0[3])):
            return "strobe"
        opened = next((c for c in caps if c[2] == "ShutterOpen"), None)
        if opened:
            return fixed(opened[0])
        return "strobe"
    if at0 and (at0[2] in ("NoFunction", "ShutterOpen") or NEUTRAL_TEXT.search(at0[3])):
        return "zero"
    neutral = next((c for c in caps if c[2] == "NoFunction" or NEUTRAL_TEXT.search(c[3])), None)
    if neutral:
        return fixed(neutral[0])
    if ch.get("Default"):
        return fixed(ch.get("Default"))
    return "zero"


def load_qlc(root: Path) -> list[dict]:
    out = []
    for path in sorted(root.glob("*/*.qxf")):
        try:
            t = ET.parse(path).getroot()
        except ET.ParseError:
            continue
        ns = t.tag.split("}")[0] + "}" if t.tag.startswith("{") else ""
        maker = (t.findtext(ns + "Manufacturer") or path.parent.name).strip()
        model = (t.findtext(ns + "Model") or path.stem).strip()
        chans = {c.get("Name"): qlc_role(c, ns) for c in t.findall(ns + "Channel")}
        modes = []
        for mode in t.findall(ns + "Mode"):
            items = sorted(((int(c.get("Number", 0)), (c.text or "").strip()) for c in mode.findall(ns + "Channel")))
            roles = [chans.get(name, "zero") for _, name in items]
            if roles and usable(roles):
                modes.append([mode.get("Name") or f"{len(roles)}ch", roles])
        if modes:
            out.append({"m": maker, "n": model, "t": fixture_type(t.findtext(ns + "Type") or "", model, modes),
                        "modes": modes})
    return out


# Тип приладу для поділу бібліотеки на розділи
TYPE_MAP = {
    "color changer": "par", "dimmer": "par",
    "pixel bar": "bar", "led bar (beams)": "bar", "led bar (pixels)": "bar",
    "moving head": "head",
    "strobe": "strobe", "blinder": "strobe",
    "matrix": "matrix",
    "flower": "effect", "effect": "effect", "scanner": "effect", "barrel scanner": "effect",
    "laser": "effect", "fan": "effect",
}


def fixture_type(raw: str, name: str, modes: list) -> str:
    t = TYPE_MAP.get((raw or "").strip().lower(), "other")
    n = name.lower()
    if t in ("par", "other") and re.search(r"\bbar\b|batten|strip|tube|pixel", n):
        return "bar"
    if t in ("par", "other") and re.search(r"matrix|panel|blinder", n):
        return "matrix" if "matrix" in n or "panel" in n else "strobe"
    if t == "par" and max(m[1].count("r") for m in modes) >= 4:
        return "bar"
    return t


def norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ofl", type=Path, required=True, help="тека fixtures з Open Fixture Library")
    ap.add_argument("--qlc", type=Path, required=True, help="тека resources/fixtures з QLC+")
    args = ap.parse_args()
    ofl, qlc = load_ofl(args.ofl), load_qlc(args.qlc)
    seen, merged = set(), []
    for fx in ofl + qlc:  # OFL має пріоритет: точніша схема
        key = (norm(fx["m"]), norm(fx["n"]))
        if key in seen:
            continue
        seen.add(key)
        merged.append(fx)
    merged.sort(key=lambda f: (f["m"].lower(), f["n"].lower()))
    data = {"fixtures": merged}  # ліцензії джерел — у THIRD_PARTY_LICENSES.md
    OUT.write_bytes(gzip.compress(json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf-8"), 9))
    print(f"OFL: {len(ofl)}, QLC+: {len(qlc)}, разом без дублікатів: {len(merged)} приладів, "
          f"{sum(len(f['modes']) for f in merged)} режимів → {OUT} ({OUT.stat().st_size // 1024} КБ)")


if __name__ == "__main__":
    main()
