import zipfile

import pytest

from dmxctl import updater


def test_version_compare():
    assert updater.is_newer("1.0.1", "1.0.0")
    assert updater.is_newer("v1.10.0", "1.9.9")
    assert not updater.is_newer("1.0.0", "1.0.0")
    assert not updater.is_newer("0.9", "1.0.0")


def _make_app(dirpath, version):
    pkg = dirpath / "dmxctl"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text(f'__version__ = "{version}"\n')
    (dirpath / "requirements.txt").write_text("")
    return dirpath


def _zip_of(src, zpath, prefix):
    with zipfile.ZipFile(zpath, "w") as zf:
        for f in src.rglob("*"):
            zf.write(f, f"{prefix}{f.relative_to(src)}")


@pytest.mark.parametrize("prefix", ["", "Navascar-SC-DMX-abc123/"])  # архів релізу та zipball GitHub
def test_install_from_zip_replaces_files_and_keeps_config(tmp_path, prefix):
    app = _make_app(tmp_path / "app", "1.0.0")
    (app / "config.json").write_text('{"keep": true}')
    (app / "dmxctl" / "old_module.py").write_text("x = 1")
    (app / ".venv").mkdir()
    new = _make_app(tmp_path / "new", "1.1.0")
    (new / "dmxctl" / "new_module.py").write_text("y = 2")
    zpath = tmp_path / "u.zip"
    _zip_of(new, zpath, prefix)

    updater.install_from_zip(zpath, app)

    assert '"1.1.0"' in (app / "dmxctl" / "__init__.py").read_text()
    assert (app / "dmxctl" / "new_module.py").exists()
    assert not (app / "dmxctl" / "old_module.py").exists()      # старі файли прибрано
    assert (app / "config.json").read_text() == '{"keep": true}'  # налаштування цілі
    assert (app / ".venv").is_dir()
    assert (app / ".update-backup" / "dmxctl" / "old_module.py").exists()  # резервна копія


def test_install_rejects_archive_without_app(tmp_path):
    app = _make_app(tmp_path / "app", "1.0.0")
    zpath = tmp_path / "bad.zip"
    with zipfile.ZipFile(zpath, "w") as zf:
        zf.writestr("readme.txt", "nothing")
    with pytest.raises(RuntimeError):
        updater.install_from_zip(zpath, app)
    assert (app / "dmxctl" / "__init__.py").exists()


def test_install_rejects_path_traversal(tmp_path):
    app = _make_app(tmp_path / "app", "1.0.0")
    zpath = tmp_path / "evil.zip"
    with zipfile.ZipFile(zpath, "w") as zf:
        zf.writestr("../../evil.txt", "x")
    with pytest.raises(RuntimeError):
        updater.install_from_zip(zpath, app)


def test_open_external_only_http(monkeypatch):
    import webbrowser
    import sys
    from dmxctl import server
    opened = []
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(webbrowser, "open", lambda url: opened.append(url) or True)
    assert server.open_external("https://github.com/Navascar/SC-DMX/releases")
    assert not server.open_external("file:///C:/Windows/System32/calc.exe")
    assert not server.open_external("javascript:alert(1)")
    assert not server.open_external("https:///nohost")
    assert opened == ["https://github.com/Navascar/SC-DMX/releases"]


def test_failed_requirements_restore_previous_version(tmp_path, monkeypatch):
    """Компоненти нової версії не встановилися — файли програми повертаються до попередньої версії."""
    import io
    app = tmp_path / "app"
    (app / "dmxctl").mkdir(parents=True)
    (app / "dmxctl" / "__init__.py").write_text('__version__ = "1.0.0"\n')
    (app / "config.json").write_text("{}")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("SC-DMX/dmxctl/__init__.py", '__version__ = "9.9.9"\n')
        z.writestr("SC-DMX/dmxctl/new.py", "")
        z.writestr("SC-DMX/requirements.txt", "x\n")

    class Resp(io.BytesIO):
        headers = {}
    monkeypatch.setattr(updater, "_open", lambda url, timeout=15: Resp(buf.getvalue()))
    monkeypatch.setattr(updater, "can_self_update", lambda: None)

    def pip_fail(app_dir):
        raise RuntimeError("pip: немає мережі")
    monkeypatch.setattr(updater, "install_requirements", pip_fail)
    with pytest.raises(RuntimeError):
        updater.download_and_install("http://x/SC-DMX.zip", app_dir=app)
    assert "1.0.0" in (app / "dmxctl" / "__init__.py").read_text()
    assert not (app / "dmxctl" / "new.py").exists()
    assert (app / "config.json").read_text() == "{}"          # налаштування не чіпаються
