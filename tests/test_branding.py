"""Стара назва SC DMX не повертається в інтерфейс (навіть з нерозривним пробілом чи розбита тегом)."""
import re
from pathlib import Path

STATIC = Path(__file__).resolve().parent.parent / "dmxctl" / "static"
OLD = re.compile(r"SC(?:\s|&nbsp;|&#160;|\\u00a0|<[^>]*>)*DMX|scdmx(?!,)", re.I)


def test_ui_has_no_old_name():
    for name in ("index.html", "app.js", "style.css"):
        text = (STATIC / name).read_text("utf-8")
        # .scdmx у виборі файлу — старі файли сцен ще відкриваються
        text = text.replace('accept=".nitor,.scdmx,', "")
        assert not OLD.search(text), f"{name}: {OLD.search(text).group(0)}"
    assert "<h1>Nitor</h1>" in (STATIC / "index.html").read_text("utf-8")
