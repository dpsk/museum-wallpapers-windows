"""Windows: the wallpaper per monitor through IDesktopWallpaper (COM), with
SystemParametersInfo as the fallback; monitors and taskbar areas from
EnumDisplayMonitors; toasts with buttons from windows-toasts (a tray balloon
when those cannot be shown); autostart in the HKCU Run key."""

import contextlib
import ctypes
import gc
import os
import sys
import threading
import uuid
import winreg
from ctypes import wintypes
from pathlib import Path

from .. import APP_ID, APP_NAME, AUMID
from .base import Monitor, Platform, largest, language_code

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
shell32 = ctypes.WinDLL("shell32")
ole32 = ctypes.WinDLL("ole32")

SPI_SETDESKWALLPAPER = 0x0014
SPI_GETDESKWALLPAPER = 0x0073
SPI_GETWORKAREA = 0x0030
SPIF_UPDATEINIFILE = 0x01
SPIF_SENDWININICHANGE = 0x02
DWPOS_FILL = 4
ERROR_ALREADY_EXISTS = 183
EVENT_MODIFY_STATE = 0x0002
SYNCHRONIZE = 0x00100000
INFINITE = 0xFFFFFFFF
WAIT_OBJECT_0 = 0
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
FOLDERID_PICTURES = "{33E28130-4E1E-4676-835A-98395C3BC3BB}"

CLSID_DESKTOP_WALLPAPER = "{C2CF3110-460E-4fc1-B9D0-8A1C0C9CC4BD}"
IID_DESKTOP_WALLPAPER = "{B92B56A9-8B55-4E14-9A89-0199BBB6F93B}"


class MONITORINFOEXW(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT), ("rcWork", wintypes.RECT),
                ("dwFlags", wintypes.DWORD), ("szDevice", wintypes.WCHAR * 32)]


class GUID(ctypes.Structure):
    _fields_ = [("Data1", wintypes.DWORD), ("Data2", wintypes.WORD), ("Data3", wintypes.WORD),
                ("Data4", ctypes.c_ubyte * 8)]

    @classmethod
    def parse(cls, text):
        guid = cls()
        ctypes.memmove(ctypes.byref(guid), uuid.UUID(text).bytes_le, ctypes.sizeof(guid))
        return guid


MonitorEnumProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HMONITOR, wintypes.HDC,
                                     ctypes.POINTER(wintypes.RECT), wintypes.LPARAM)
user32.EnumDisplayMonitors.argtypes = [wintypes.HDC, ctypes.POINTER(wintypes.RECT), MonitorEnumProc, wintypes.LPARAM]
user32.GetMonitorInfoW.argtypes = [wintypes.HMONITOR, ctypes.POINTER(MONITORINFOEXW)]
user32.SystemParametersInfoW.argtypes = [wintypes.UINT, wintypes.UINT, wintypes.LPVOID, wintypes.UINT]
user32.SystemParametersInfoW.restype = wintypes.BOOL
kernel32.CreateMutexW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR]
kernel32.CreateMutexW.restype = wintypes.HANDLE
kernel32.CreateEventW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.BOOL, wintypes.LPCWSTR]
kernel32.CreateEventW.restype = wintypes.HANDLE
kernel32.OpenEventW.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.LPCWSTR]
kernel32.OpenEventW.restype = wintypes.HANDLE
kernel32.SetEvent.argtypes = [wintypes.HANDLE]
kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
kernel32.WaitForSingleObject.restype = wintypes.DWORD
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
kernel32.LCIDToLocaleName.argtypes = [wintypes.DWORD, wintypes.LPWSTR, ctypes.c_int, wintypes.DWORD]
shell32.SHGetKnownFolderPath.argtypes = [ctypes.POINTER(GUID), wintypes.DWORD, wintypes.HANDLE,
                                         ctypes.POINTER(ctypes.c_void_p)]
ole32.CoTaskMemFree.argtypes = [ctypes.c_void_p]


def _rect(r):
    return (r.left, r.top, r.right, r.bottom)


# ----------------------------------------------------------------- COM


_interface = None


def _wallpaper_interface():
    """IDesktopWallpaper, defined once; comtypes ships no definition of it."""
    global _interface
    if _interface is None:
        from comtypes import COMMETHOD, GUID as ComGUID, HRESULT, IUnknown

        class IDesktopWallpaper(IUnknown):
            _iid_ = ComGUID(IID_DESKTOP_WALLPAPER)
            _methods_ = [
                COMMETHOD([], HRESULT, "SetWallpaper", (["in"], wintypes.LPCWSTR, "monitorID"),
                          (["in"], wintypes.LPCWSTR, "wallpaper")),
                COMMETHOD([], HRESULT, "GetWallpaper", (["in"], wintypes.LPCWSTR, "monitorID"),
                          (["out"], ctypes.POINTER(ctypes.c_void_p), "wallpaper")),
                COMMETHOD([], HRESULT, "GetMonitorDevicePathAt", (["in"], wintypes.UINT, "monitorIndex"),
                          (["out"], ctypes.POINTER(ctypes.c_void_p), "monitorID")),
                COMMETHOD([], HRESULT, "GetMonitorDevicePathCount", (["out"], ctypes.POINTER(wintypes.UINT), "count")),
                COMMETHOD([], HRESULT, "GetMonitorRECT", (["in"], wintypes.LPCWSTR, "monitorID"),
                          (["out"], ctypes.POINTER(wintypes.RECT), "displayRect")),
                COMMETHOD([], HRESULT, "SetBackgroundColor", (["in"], wintypes.DWORD, "color")),
                COMMETHOD([], HRESULT, "GetBackgroundColor", (["out"], ctypes.POINTER(wintypes.DWORD), "color")),
                COMMETHOD([], HRESULT, "SetPosition", (["in"], ctypes.c_int, "position")),
                COMMETHOD([], HRESULT, "GetPosition", (["out"], ctypes.POINTER(ctypes.c_int), "position")),
                COMMETHOD([], HRESULT, "SetSlideshow", (["in"], ctypes.c_void_p, "items")),
                COMMETHOD([], HRESULT, "GetSlideshow", (["out"], ctypes.POINTER(ctypes.c_void_p), "items")),
                COMMETHOD([], HRESULT, "SetSlideshowOptions", (["in"], ctypes.c_int, "options"),
                          (["in"], wintypes.UINT, "slideshowTick")),
                COMMETHOD([], HRESULT, "GetSlideshowOptions", (["out"], ctypes.POINTER(ctypes.c_int), "options"),
                          (["out"], ctypes.POINTER(wintypes.UINT), "slideshowTick")),
                COMMETHOD([], HRESULT, "AdvanceSlideshow", (["in"], wintypes.LPCWSTR, "monitorID"),
                          (["in"], ctypes.c_int, "direction")),
                COMMETHOD([], HRESULT, "GetStatus", (["out"], ctypes.POINTER(ctypes.c_int), "state")),
                COMMETHOD([], HRESULT, "Enable", (["in"], wintypes.BOOL, "enable")),
            ]

        _interface = IDesktopWallpaper
    return _interface


def _take_string(address):
    """A COM-allocated wide string, freed after copying."""
    if not address:
        return ""
    try:
        return ctypes.wstring_at(address)
    finally:
        ole32.CoTaskMemFree(address)


_com_executor = None
_com_executor_lock = threading.Lock()


def _com_thread_init():
    import comtypes
    try:
        comtypes.CoInitializeEx(comtypes.COINIT_APARTMENTTHREADED)
    except OSError:  # already initialized on this thread
        pass


def with_desktop_wallpaper(work):
    """Run work(IDesktopWallpaper) and return its result. All COM calls go
    to one long-lived thread that initializes COM once and never
    uninitializes it, so no interface is ever released after
    CoUninitialize, whatever the caller's thread or an exception holds."""
    global _com_executor
    with _com_executor_lock:
        if _com_executor is None:
            from concurrent.futures import ThreadPoolExecutor
            _com_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="com",
                                               initializer=_com_thread_init)

    def call():
        import comtypes
        failure = None
        desktop = comtypes.CoCreateInstance(comtypes.GUID(CLSID_DESKTOP_WALLPAPER), interface=_wallpaper_interface())
        try:
            return work(desktop)
        except Exception as exc:  # noqa: BLE001 - re-raised below, without its traceback
            failure = (type(exc), exc.args, repr(exc))
        finally:
            # The traceback's frames reference `desktop`: with them gone,
            # it is released here, on the COM thread, while COM is up.
            del desktop
            gc.collect()
        kind, args, text = failure
        try:
            error = kind(*args)
        except Exception:  # noqa: BLE001
            error = RuntimeError(text)
        raise error

    return _com_executor.submit(call).result(timeout=60)


def _com_monitors(desktop):
    """[(device path, rect)] for active monitors."""
    found = []
    for index in range(desktop.GetMonitorDevicePathCount()):
        device = _take_string(desktop.GetMonitorDevicePathAt(index))
        try:
            rect = _rect(desktop.GetMonitorRECT(device))
        except Exception:  # noqa: BLE001 - COMError: an inactive monitor reports one here
            continue
        if rect[2] > rect[0] and rect[3] > rect[1]:
            found.append((device, rect))
    return found


# ----------------------------------------------------------------- platform


class WindowsPlatform(Platform):
    name = "windows"

    def __init__(self):
        self.balloon = None  # the tray app's fallback notification: callable(title, body)
        self._toaster = None
        self._toasts = []  # keep shown toasts alive so their callbacks still fire
        self._toast_lock = threading.Lock()

    # -- setup and paths

    def setup(self):
        """Per-monitor DPI awareness, so sizes are physical pixels at 125-200%
        scaling; then the AppUserModelID toasts are grouped under."""
        # comtypes initializes COM on the thread that first imports it; make
        # that the main thread (which pumps messages for the tray icon), not
        # whichever worker happens to touch the wallpaper first.
        try:
            import comtypes  # noqa: F401
        except ImportError:
            pass
        try:
            if not user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4)):  # PER_MONITOR_AWARE_V2
                raise OSError
        except (AttributeError, OSError):
            try:
                ctypes.WinDLL("shcore").SetProcessDpiAwareness(2)
            except (AttributeError, OSError):
                user32.SetProcessDPIAware()
        try:
            shell32.SetCurrentProcessExplicitAppUserModelID(ctypes.c_wchar_p(AUMID))
        except (AttributeError, OSError):
            pass

    def paths(self):
        if os.environ.get("MUSEUM_WALLPAPERS_HOME"):
            return super().paths()
        home = Path.home()
        roaming = Path(os.environ.get("APPDATA") or home / "AppData" / "Roaming") / APP_ID
        local = Path(os.environ.get("LOCALAPPDATA") or home / "AppData" / "Local") / APP_ID
        return {"config": roaming, "cache": local / "cache", "state": local / "state",
                "pictures": self.pictures_folder()}

    @staticmethod
    def pictures_folder():
        """The Pictures folder, wherever it is (OneDrive moves it)."""
        address = ctypes.c_void_p()
        try:
            if shell32.SHGetKnownFolderPath(ctypes.byref(GUID.parse(FOLDERID_PICTURES)), 0, None,
                                            ctypes.byref(address)) == 0:
                return Path(_take_string(address.value))
        except OSError:
            pass
        return Path.home() / "Pictures"

    # -- monitors and wallpaper

    def _display_monitors(self):
        """[(device name, monitor rect, work rect, primary)] from EnumDisplayMonitors."""
        found = []

        def callback(hmonitor, _hdc, _lprc, _data):
            info = MONITORINFOEXW()
            info.cbSize = ctypes.sizeof(MONITORINFOEXW)
            if user32.GetMonitorInfoW(hmonitor, ctypes.byref(info)):
                found.append((info.szDevice, _rect(info.rcMonitor), _rect(info.rcWork), bool(info.dwFlags & 1)))
            return True

        user32.EnumDisplayMonitors(None, None, MonitorEnumProc(callback), 0)
        return found

    def monitors(self):
        displays = self._display_monitors()
        try:
            devices = with_desktop_wallpaper(_com_monitors)
        except Exception as exc:  # noqa: BLE001 - no COM: one image for all through SPI
            print(f"museum-wallpapers: IDesktopWallpaper unavailable: {exc}", file=sys.stderr)
            devices = []
        result = []
        if devices:
            for device, rect in devices:
                work = next((w for _, r, w, _ in displays if r == rect), rect)
                result.append(Monitor(device, rect[2] - rect[0], rect[3] - rect[1], _inset(rect, work)))
        else:
            for name, rect, work, _primary in displays:
                result.append(Monitor(name, rect[2] - rect[0], rect[3] - rect[1], _inset(rect, work)))
        return result

    def set_wallpaper(self, images):
        images = {key: str(Path(value).resolve()) for key, value in images.items()}
        try:
            def apply(desktop):
                known = {device for device, _ in _com_monitors(desktop)}
                if not known & set(images):
                    raise LookupError("no monitor of these images is connected")
                desktop.SetPosition(DWPOS_FILL)
                for device, path in images.items():
                    if device in known:
                        desktop.SetWallpaper(device, path)

            with_desktop_wallpaper(apply)
            return
        except Exception as exc:  # noqa: BLE001 - fall back to the classic API below
            print(f"museum-wallpapers: per-monitor wallpaper failed ({exc}); using one image", file=sys.stderr)
        biggest = largest([m for m in self.monitors() if m.id in images])
        path = images.get(biggest.id) or next(iter(images.values()))
        with contextlib.suppress(OSError):
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Control Panel\Desktop", 0, winreg.KEY_SET_VALUE) as key:
                winreg.SetValueEx(key, "WallpaperStyle", 0, winreg.REG_SZ, "10")  # fill
                winreg.SetValueEx(key, "TileWallpaper", 0, winreg.REG_SZ, "0")
        buffer = ctypes.create_unicode_buffer(path)
        if not user32.SystemParametersInfoW(SPI_SETDESKWALLPAPER, 0, buffer,
                                            SPIF_UPDATEINIFILE | SPIF_SENDWININICHANGE):
            raise ctypes.WinError(ctypes.get_last_error())

    def current_wallpaper(self):
        try:
            def read(desktop):
                devices = _com_monitors(desktop)
                if not devices:
                    return None
                device = max(devices, key=lambda d: ((d[1][2] - d[1][0]) * (d[1][3] - d[1][1]), d[1][2] - d[1][0]))[0]
                return _take_string(desktop.GetWallpaper(device))

            path = with_desktop_wallpaper(read)
        except Exception:  # noqa: BLE001
            buffer = ctypes.create_unicode_buffer(1024)
            path = buffer.value if user32.SystemParametersInfoW(SPI_GETDESKWALLPAPER, len(buffer), buffer, 0) else ""
        return Path(path) if path else None

    def work_area(self):
        """The primary screen above the taskbar, for placing the card."""
        rect = wintypes.RECT()
        if user32.SystemParametersInfoW(SPI_GETWORKAREA, 0, ctypes.byref(rect), 0):
            return _rect(rect)
        return None

    # -- notifications

    def notify(self, title, body, actions=(), image=None, on_click=None):
        try:
            self._toast(title, body, actions, image, on_click)
        except Exception as exc:  # noqa: BLE001 - windows-toasts missing, or an old Windows
            print(f"museum-wallpapers: toast failed ({exc}); using a balloon", file=sys.stderr)
            if self.balloon:
                self.balloon(title, body)

    def _toast(self, title, body, actions, image, on_click):
        from windows_toasts import (InteractableWindowsToaster, Toast, ToastButton, ToastDisplayImage,
                                    ToastImagePosition)
        with self._toast_lock:
            if self._toaster is None:
                self._toaster = InteractableWindowsToaster(APP_NAME, notifierAUMID=AUMID)
            callbacks = {f"action-{n}": callback for n, (_label, callback) in enumerate(actions)}

            def activated(event):
                callback = callbacks.get(getattr(event, "arguments", "") or "", on_click)
                if callback:
                    threading.Thread(target=callback, daemon=True).start()

            toast = Toast([title, body], on_activated=activated)
            for n, (label, _callback) in enumerate(actions):
                toast.AddAction(ToastButton(label, f"action-{n}"))
            if image and Path(image).exists():
                toast.AddImage(ToastDisplayImage.fromPath(str(image), position=ToastImagePosition.Hero))
            self._toaster.show_toast(toast)
            self._toasts = (self._toasts + [toast])[-5:]

    def register_app(self, icon_path):
        """Name and icon for toasts from this AppUserModelID (the installer's
        Start menu shortcut carries the same id)."""
        key_path = rf"Software\Classes\AppUserModelId\{AUMID}"
        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, key_path) as key:
            winreg.SetValueEx(key, "DisplayName", 0, winreg.REG_SZ, APP_NAME)
            if icon_path and Path(icon_path).exists():
                winreg.SetValueEx(key, "IconUri", 0, winreg.REG_SZ, str(Path(icon_path).resolve()))

    # -- shell

    def open_url(self, url):
        os.startfile(url)

    def open_folder(self, path):
        Path(path).mkdir(parents=True, exist_ok=True)
        os.startfile(str(path))

    def ui_language(self):
        buffer = ctypes.create_unicode_buffer(85)
        try:
            if kernel32.LCIDToLocaleName(kernel32.GetUserDefaultUILanguage(), buffer, len(buffer), 0):
                return language_code(buffer.value) or "en"
        except OSError:
            pass
        return super().ui_language()

    def caption_fonts(self):
        fonts = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"
        title = next((fonts / f for f in ("georgiai.ttf", "seguisli.ttf", "segoeuii.ttf") if (fonts / f).exists()), None)
        body = next((fonts / f for f in ("segoeui.ttf", "arial.ttf") if (fonts / f).exists()), None)
        return (title, body)

    # -- autostart

    @staticmethod
    def launch_command():
        if getattr(sys, "frozen", False):
            return f'"{sys.executable}" --background'
        pythonw = Path(sys.executable).with_name("pythonw.exe")
        runner = pythonw if pythonw.exists() else Path(sys.executable)
        return f'"{runner}" -m museum_wallpapers --background'

    def autostart_enabled(self):
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
                winreg.QueryValueEx(key, APP_ID)
            return True
        except OSError:
            return False

    def set_autostart(self, enabled):
        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
            if enabled:
                winreg.SetValueEx(key, APP_ID, 0, winreg.REG_SZ, self.launch_command())
            else:
                with contextlib.suppress(FileNotFoundError):
                    winreg.DeleteValue(key, APP_ID)


def _inset(rect, work):
    """Pixels the taskbar (or other app bars) take from each edge."""
    return (max(0, work[0] - rect[0]), max(0, work[1] - rect[1]),
            max(0, rect[2] - work[2]), max(0, rect[3] - work[3]))


# ----------------------------------------------------------------- one instance


class SingleInstance:
    """A named mutex marks the running app; a second launch signals a named
    event, which the first one answers (by opening its card), and exits."""

    MUTEX = f"Local\\{APP_ID}.Instance"
    EVENT = f"Local\\{APP_ID}.Show"

    def __init__(self):
        self._mutex = kernel32.CreateMutexW(None, False, self.MUTEX)
        self.first = ctypes.get_last_error() != ERROR_ALREADY_EXISTS
        self._event = kernel32.CreateEventW(None, False, False, self.EVENT) if self.first else None

    def signal_running(self):
        handle = kernel32.OpenEventW(EVENT_MODIFY_STATE, False, self.EVENT)
        if handle:
            kernel32.SetEvent(handle)
            kernel32.CloseHandle(handle)
            return True
        return False

    def listen(self, callback):
        """Call `callback` (on a daemon thread) whenever a second launch signals."""
        def loop():
            while kernel32.WaitForSingleObject(self._event, INFINITE) == WAIT_OBJECT_0:
                callback()

        if self._event:
            threading.Thread(target=loop, name="single-instance", daemon=True).start()
