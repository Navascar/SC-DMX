"""Інтеграція з оболонкою Windows: ярлики, панель задач, заголовок вікна.

Щоб Windows показувала на панелі задач «SC DMX» з власною іконкою (а не «Python»),
у вікна і в ярликів має бути однаковий ідентифікатор застосунку (AppUserModelID).
Тоді закріплене на панелі задач вікно — це ярлик SC DMX, а меню правої кнопки
називається «SC DMX».

Ярлики запускають sc-dmx.pyw через pythonw.exe — без консолі й з будь-якої теки.

python -m dmxctl.winshell install   — створити ярлики (так робить інсталятор)
    --no-desktop      без ярлика на робочому столі
    --no-start-menu   без ярлика в меню «Пуск»
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

APP_ID = "SCDMX.Controller"
APP_NAME = "SC DMX"
APP_DIR = Path(__file__).resolve().parent.parent
LAUNCHER = APP_DIR / "sc-dmx.pyw"
ICON = APP_DIR / "dmxctl" / "static" / "icon.ico"
DESCRIPTION = "SC DMX — керування RGB-прожекторами"

# Кольори заголовка вікна — як верхня панель інтерфейсу (style.css: --surface, --text, --line)
CAPTION = (0x17, 0x1A, 0x21)
CAPTION_TEXT = (0xE6, 0xE8, 0xEE)
BORDER = (0x2B, 0x30, 0x3B)


def pythonw() -> Path:
    exe = Path(sys.executable)
    w = exe.with_name("pythonw.exe")
    return w if w.exists() else exe


def launch_command() -> tuple[str, str]:
    """(програма, аргументи) для ярлика й перезапуску з панелі задач."""
    return str(pythonw()), f'"{LAUNCHER}"'


def set_process_id() -> None:
    """Ідентифікатор застосунку для всього процесу (до створення вікон)."""
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)
    except Exception:  # noqa: BLE001
        pass


def _shortcut_dirs() -> list[Path]:
    from win32com.shell import shell, shellcon
    return [Path(shell.SHGetFolderPath(0, shellcon.CSIDL_DESKTOPDIRECTORY, None, 0)),
            Path(shell.SHGetFolderPath(0, shellcon.CSIDL_PROGRAMS, None, 0))]


def _read_id(path: Path) -> str | None:
    import pythoncom
    from win32com.propsys import propsys, pscon
    from win32com.shell import shell
    link = pythoncom.CoCreateInstance(shell.CLSID_ShellLink, None, pythoncom.CLSCTX_INPROC_SERVER,
                                      shell.IID_IShellLink)
    link.QueryInterface(pythoncom.IID_IPersistFile).Load(str(path))
    store = link.QueryInterface(propsys.IID_IPropertyStore)
    try:
        return store.GetValue(pscon.PKEY_AppUserModel_ID).GetValue()
    except Exception:  # noqa: BLE001
        return None


def write_shortcut(path: Path) -> None:
    import pythoncom
    from win32com.propsys import propsys, pscon
    from win32com.shell import shell
    target, args = launch_command()
    link = pythoncom.CoCreateInstance(shell.CLSID_ShellLink, None, pythoncom.CLSCTX_INPROC_SERVER,
                                      shell.IID_IShellLink)
    link.SetPath(target)
    link.SetArguments(args)
    link.SetWorkingDirectory(str(APP_DIR))
    link.SetIconLocation(str(ICON), 0)
    link.SetDescription(DESCRIPTION)
    store = link.QueryInterface(propsys.IID_IPropertyStore)
    store.SetValue(pscon.PKEY_AppUserModel_ID, propsys.PROPVARIANTType(APP_ID, pythoncom.VT_LPWSTR))
    store.Commit()
    path.parent.mkdir(parents=True, exist_ok=True)
    link.QueryInterface(pythoncom.IID_IPersistFile).Save(str(path), 0)


def install_shortcuts(desktop: bool = True, start_menu: bool = True) -> list[Path]:
    """Ярлики «SC DMX» на робочому столі й у меню «Пуск» (лише вибрані)."""
    desk, programs = _shortcut_dirs()
    paths = [d / f"{APP_NAME}.lnk" for d, on in ((desk, desktop), (programs, start_menu)) if on]
    for p in paths:
        write_shortcut(p)
    _notify()
    return paths


def repair_shortcuts() -> None:
    """Ярлики старих версій (без ідентифікатора застосунку) переписуються на нові."""
    changed = False
    for d in _shortcut_dirs():
        p = d / f"{APP_NAME}.lnk"
        if p.exists() and _read_id(p) != APP_ID:
            write_shortcut(p)
            changed = True
    if changed:
        _notify()


def _notify() -> None:
    from win32com.shell import shell, shellcon
    shell.SHChangeNotify(shellcon.SHCNE_ASSOCCHANGED, shellcon.SHCNF_IDLIST, None, None)


def set_window_identity(hwnd: int) -> None:
    """Вікно = застосунок SC DMX: назва, іконка й команда запуску для панелі задач."""
    import pythoncom
    from win32com.propsys import propsys, pscon
    target, args = launch_command()
    store = propsys.SHGetPropertyStoreForWindow(hwnd, propsys.IID_IPropertyStore)
    for key, value in ((pscon.PKEY_AppUserModel_ID, APP_ID),
                       (pscon.PKEY_AppUserModel_RelaunchCommand, f'"{target}" {args}'),
                       (pscon.PKEY_AppUserModel_RelaunchDisplayNameResource, APP_NAME),
                       (pscon.PKEY_AppUserModel_RelaunchIconResource, f"{ICON},0")):
        store.SetValue(key, propsys.PROPVARIANTType(value, pythoncom.VT_LPWSTR))
    store.Commit()


def style_title_bar(hwnd: int) -> None:
    """Темний заголовок вікна в кольорах програми (Windows 10 1809+; кольори — Windows 11)."""
    import ctypes
    from ctypes import wintypes
    dwm = ctypes.windll.dwmapi

    def attr(n: int, value: int) -> bool:
        v = wintypes.DWORD(value)
        return dwm.DwmSetWindowAttribute(wintypes.HWND(hwnd), n, ctypes.byref(v), ctypes.sizeof(v)) == 0

    if not attr(20, 1):          # DWMWA_USE_IMMERSIVE_DARK_MODE
        attr(19, 1)              # те саме у Windows 10 до 20H1
    colorref = lambda rgb: rgb[0] | (rgb[1] << 8) | (rgb[2] << 16)  # noqa: E731
    attr(35, colorref(CAPTION))       # DWMWA_CAPTION_COLOR
    attr(36, colorref(CAPTION_TEXT))  # DWMWA_TEXT_COLOR
    attr(34, colorref(BORDER))        # DWMWA_BORDER_COLOR


# ------------------------------------------------------------ одна копія ---
APP_MUTEX = "Local\\SCDMX.App"         # лаунчер із сервером — лише один
WINDOW_MUTEX = "Local\\SCDMX.Window"   # вікно програми — лише одне
WINDOW_TITLE = APP_NAME


def single_instance(name: str):
    """Іменований м'ютекс Windows: дескриптор, якщо ми перші, або None, якщо копія вже працює.
    Дескриптор треба тримати, доки працює процес (Windows звільнить його сама)."""
    import ctypes
    from ctypes import wintypes
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.CreateMutexW.restype = wintypes.HANDLE
    k32.CreateMutexW.argtypes = (wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR)
    handle = k32.CreateMutexW(None, False, name)
    if ctypes.get_last_error() == 183:      # ERROR_ALREADY_EXISTS
        k32.CloseHandle(handle)
        return None
    return handle


def find_app_window() -> int | None:
    """Відкрите вікно SC DMX (вікно Qt із заголовком «SC DMX»)."""
    import ctypes
    from ctypes import wintypes
    user32 = ctypes.windll.user32
    found: list[int] = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def callback(hwnd, _):
        title = ctypes.create_unicode_buffer(64)
        cls = ctypes.create_unicode_buffer(128)
        user32.GetWindowTextW(hwnd, title, 64)
        user32.GetClassNameW(hwnd, cls, 128)
        if title.value == WINDOW_TITLE and "Qt" in cls.value and user32.IsWindowVisible(hwnd):
            found.append(hwnd)
            return False
        return True

    user32.EnumWindows(callback, 0)
    return found[0] if found else None


def focus_window(hwnd: int) -> None:
    """Показує вікно: розгортає згорнуте й виводить на передній план."""
    import ctypes
    from ctypes import wintypes
    user32 = ctypes.windll.user32
    user32.ShowWindow.argtypes = (wintypes.HWND, ctypes.c_int)
    user32.IsIconic.argtypes = (wintypes.HWND,)
    user32.SetForegroundWindow.argtypes = (wintypes.HWND,)
    user32.ShowWindow(hwnd, 9 if user32.IsIconic(hwnd) else 5)   # SW_RESTORE / SW_SHOW
    # Windows не дає іншому процесу забрати фокус; натискання Alt знімає це обмеження
    user32.keybd_event(0x12, 0, 0, 0)
    user32.keybd_event(0x12, 0, 2, 0)
    user32.SetForegroundWindow(hwnd)


def main(argv: list[str]) -> int:
    if sys.platform != "win32":
        print("Лише для Windows")
        return 1
    if argv[:1] == ["install"]:
        for p in install_shortcuts(desktop="--no-desktop" not in argv, start_menu="--no-start-menu" not in argv):
            print(p)
        return 0
    if argv[:1] == ["repair"]:
        repair_shortcuts()
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
