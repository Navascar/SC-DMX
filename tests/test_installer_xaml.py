"""XAML вікон встановлення й видалення — коректний XML.

Інакше вікно не відкривається (код 3), а інсталятор чекає на повідомлення про помилку —
на Windows це видно лише після збірки. Збираємо XAML так само, як New-ScDmxWindow в ui-common.ps1."""
import re
import xml.dom.minidom
from pathlib import Path

import pytest

INSTALLER = Path(__file__).resolve().parent.parent / "installer"


def _here(text: str, var: str, quote: str) -> str:
    return re.search(rf'\${var} = @{quote}\r?\n(.*?)\r?\n{quote}@', text, re.S).group(1)


@pytest.mark.parametrize("script", ["setup-gui.ps1", "uninstall-gui.ps1"])
def test_window_xaml_is_valid_xml(script):
    common = (INSTALLER / "ui-common.ps1").read_text("utf-8-sig")
    body = _here((INSTALLER / script).read_text("utf-8-sig"), "Body", "'")
    xaml = (_here(common, "text", '"')
            .replace("$ScDmxResources", _here(common, "ScDmxResources", "'"))
            .replace("$Body", body).replace("$Title", "T").replace("$MainText", "M").replace("$MainStyle", "Primary"))
    xml.dom.minidom.parseString(xaml.encode("utf-8"))
