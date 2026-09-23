"""Windows: WM_CLIPBOARDUPDATE listener on a hidden message-only window (ctypes).

All Win32 bindings are created lazily so this module imports on every OS.
"""
from __future__ import annotations

import ctypes
import os
import threading
import time

from scrubboard.watchers.base import ClipboardBackend, ClipboardEvent, OnChange

CF_UNICODETEXT = 13
WM_CLOSE = 0x0010
WM_CLIPBOARDUPDATE = 0x031D
GMEM_MOVEABLE = 0x0002
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
MARKER_FORMAT = "Scrubboard.Redacted"
EXCLUDE_FORMAT = "ExcludeClipboardContentFromMonitorProcessing"
CONCEALED_FORMATS = (EXCLUDE_FORMAT, "Clipboard Viewer Ignore")
_OPEN_RETRY_DELAYS = (0, 0.01, 0.02, 0.05, 0.1, 0.2, 0.3)

_api = None


def _win32():
    global _api
    if _api is None:
        _api = _load_api()
    return _api


def _load_api():
    from ctypes import wintypes as w

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    lresult = ctypes.c_ssize_t

    class Api:
        pass

    api = Api()

    def bind(dll, name, restype, *argtypes):
        fn = getattr(dll, name)
        fn.restype, fn.argtypes = restype, list(argtypes)
        setattr(api, name, fn)

    api.WNDPROC = ctypes.WINFUNCTYPE(lresult, w.HWND, w.UINT, w.WPARAM, w.LPARAM)

    class WNDCLASSEXW(ctypes.Structure):
        _fields_ = [("cbSize", w.UINT), ("style", w.UINT), ("lpfnWndProc", api.WNDPROC),
                    ("cbClsExtra", ctypes.c_int), ("cbWndExtra", ctypes.c_int),
                    ("hInstance", w.HINSTANCE), ("hIcon", w.HANDLE), ("hCursor", w.HANDLE),
                    ("hbrBackground", w.HANDLE), ("lpszMenuName", w.LPCWSTR),
                    ("lpszClassName", w.LPCWSTR), ("hIconSm", w.HANDLE)]

    api.WNDCLASSEXW = WNDCLASSEXW
    api.MSG = w.MSG
    api.DWORD = w.DWORD
    bind(user32, "OpenClipboard", w.BOOL, w.HWND)
    bind(user32, "CloseClipboard", w.BOOL)
    bind(user32, "EmptyClipboard", w.BOOL)
    bind(user32, "GetClipboardData", w.HANDLE, w.UINT)
    bind(user32, "SetClipboardData", w.HANDLE, w.UINT, w.HANDLE)
    bind(user32, "IsClipboardFormatAvailable", w.BOOL, w.UINT)
    bind(user32, "RegisterClipboardFormatW", w.UINT, w.LPCWSTR)
    bind(user32, "AddClipboardFormatListener", w.BOOL, w.HWND)
    bind(user32, "RemoveClipboardFormatListener", w.BOOL, w.HWND)
    bind(user32, "GetClipboardOwner", w.HWND)
    bind(user32, "GetWindowThreadProcessId", w.DWORD, w.HWND, ctypes.POINTER(w.DWORD))
    bind(user32, "RegisterClassExW", w.ATOM, ctypes.POINTER(WNDCLASSEXW))
    bind(user32, "CreateWindowExW", w.HWND, w.DWORD, w.LPCWSTR, w.LPCWSTR, w.DWORD, ctypes.c_int,
         ctypes.c_int, ctypes.c_int, ctypes.c_int, w.HWND, w.HMENU, w.HINSTANCE, w.LPVOID)
    bind(user32, "DefWindowProcW", lresult, w.HWND, w.UINT, w.WPARAM, w.LPARAM)
    bind(user32, "DestroyWindow", w.BOOL, w.HWND)
    bind(user32, "PostMessageW", w.BOOL, w.HWND, w.UINT, w.WPARAM, w.LPARAM)
    bind(user32, "PostQuitMessage", None, ctypes.c_int)
    bind(user32, "GetMessageW", w.BOOL, ctypes.POINTER(w.MSG), w.HWND, w.UINT, w.UINT)
    bind(user32, "TranslateMessage", w.BOOL, ctypes.POINTER(w.MSG))
    bind(user32, "DispatchMessageW", lresult, ctypes.POINTER(w.MSG))
    bind(kernel32, "GlobalAlloc", w.HANDLE, w.UINT, ctypes.c_size_t)
    bind(kernel32, "GlobalLock", w.LPVOID, w.HANDLE)
    bind(kernel32, "GlobalUnlock", w.BOOL, w.HANDLE)
    bind(kernel32, "GlobalFree", w.HANDLE, w.HANDLE)
    bind(kernel32, "GetModuleHandleW", w.HMODULE, w.LPCWSTR)
    bind(kernel32, "OpenProcess", w.HANDLE, w.DWORD, w.BOOL, w.DWORD)
    bind(kernel32, "QueryFullProcessImageNameW", w.BOOL, w.HANDLE, w.DWORD, w.LPWSTR,
         ctypes.POINTER(w.DWORD))
    bind(kernel32, "CloseHandle", w.BOOL, w.HANDLE)
    return api


class WindowsClipboard(ClipboardBackend):
    name = "windows"

    def __init__(self) -> None:
        api = _win32()
        self._api = api
        self._marker = api.RegisterClipboardFormatW(MARKER_FORMAT)
        self._concealed = [api.RegisterClipboardFormatW(f) for f in CONCEALED_FORMATS]
        self._no_history = api.RegisterClipboardFormatW("CanIncludeInClipboardHistory")
        self._no_cloud = api.RegisterClipboardFormatW("CanUploadToCloudClipboard")
        self._hwnd = None
        self._wndproc = None  # keep the callback alive
        self._thread: threading.Thread | None = None

    # -- clipboard I/O -----------------------------------------------------
    def _open(self) -> None:
        for delay in _OPEN_RETRY_DELAYS:
            if delay:
                time.sleep(delay)
            if self._api.OpenClipboard(self._hwnd):
                return
        raise OSError("clipboard is busy (another application has it open)")

    def read_text(self) -> str | None:
        self._open()
        try:
            return self._get_text()
        finally:
            self._api.CloseClipboard()

    def _get_text(self) -> str | None:
        api = self._api
        if not api.IsClipboardFormatAvailable(CF_UNICODETEXT):
            return None
        handle = api.GetClipboardData(CF_UNICODETEXT)
        if not handle:
            return None
        ptr = api.GlobalLock(handle)
        if not ptr:
            return None
        try:
            return ctypes.wstring_at(ptr)
        finally:
            api.GlobalUnlock(handle)

    def write_text(self, text: str, *, transient: bool = False) -> None:
        self._open()
        try:
            self._api.EmptyClipboard()
            self._set(CF_UNICODETEXT, (text + "\0").encode("utf-16-le"))
            self._set(self._marker, (1).to_bytes(4, "little"))
            if transient:
                zero = (0).to_bytes(4, "little")
                self._set(self._no_history, zero)
                self._set(self._no_cloud, zero)
                self._set(self._concealed[0], zero)
        finally:
            self._api.CloseClipboard()

    def _set(self, fmt: int, data: bytes) -> None:
        api = self._api
        handle = api.GlobalAlloc(GMEM_MOVEABLE, len(data))
        if not handle:
            raise MemoryError("GlobalAlloc failed")
        ptr = api.GlobalLock(handle)
        ctypes.memmove(ptr, data, len(data))
        api.GlobalUnlock(handle)
        if not api.SetClipboardData(fmt, handle):
            api.GlobalFree(handle)
            raise OSError(f"SetClipboardData failed ({ctypes.get_last_error()})")

    # -- watching ----------------------------------------------------------
    def start(self, on_change: OnChange) -> None:
        ready = threading.Event()
        self._thread = threading.Thread(target=self._run, args=(on_change, ready),
                                        name="scrubboard-win-clipboard", daemon=True)
        self._thread.start()
        if not ready.wait(5) or not self._hwnd:
            raise OSError("could not create the clipboard listener window")

    def stop(self) -> None:
        if self._hwnd:
            self._api.PostMessageW(self._hwnd, WM_CLOSE, 0, 0)

    def _run(self, on_change: OnChange, ready: threading.Event) -> None:
        api = self._api

        def wndproc(hwnd, msg, wparam, lparam):
            if msg == WM_CLIPBOARDUPDATE:
                try:
                    on_change(self._snapshot())
                except Exception:
                    pass
                return 0
            if msg == WM_CLOSE:
                api.RemoveClipboardFormatListener(hwnd)
                api.DestroyWindow(hwnd)
                api.PostQuitMessage(0)
                return 0
            return api.DefWindowProcW(hwnd, msg, wparam, lparam)

        self._wndproc = api.WNDPROC(wndproc)
        hinst = api.GetModuleHandleW(None)
        wc = api.WNDCLASSEXW()
        wc.cbSize = ctypes.sizeof(api.WNDCLASSEXW)
        wc.lpfnWndProc = self._wndproc
        wc.hInstance = hinst
        wc.lpszClassName = "ScrubboardClipboardListener"
        api.RegisterClassExW(ctypes.byref(wc))  # fails harmlessly if already registered
        hwnd_message = (1 << (8 * ctypes.sizeof(ctypes.c_void_p))) - 3  # HWND_MESSAGE
        hwnd = api.CreateWindowExW(0, wc.lpszClassName, "Scrubboard", 0, 0, 0, 0, 0,
                                   hwnd_message, None, hinst, None)
        if hwnd and api.AddClipboardFormatListener(hwnd):
            self._hwnd = hwnd
        ready.set()
        if not self._hwnd:
            return
        msg = api.MSG()
        while api.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            api.TranslateMessage(ctypes.byref(msg))
            api.DispatchMessageW(ctypes.byref(msg))
        self._hwnd = None

    def _snapshot(self) -> ClipboardEvent:
        api = self._api
        own = bool(api.IsClipboardFormatAvailable(self._marker))
        concealed = any(api.IsClipboardFormatAvailable(f) for f in self._concealed)
        text = None if (own or concealed) else self.read_text()
        return ClipboardEvent(text, own=own, concealed=concealed, source_app=self._owner_process())

    def _owner_process(self) -> str | None:
        api = self._api
        owner = api.GetClipboardOwner()
        if not owner:
            return None
        pid = api.DWORD()
        api.GetWindowThreadProcessId(owner, ctypes.byref(pid))
        handle = api.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value)
        if not handle:
            return None
        try:
            buf = ctypes.create_unicode_buffer(1024)
            size = api.DWORD(1024)
            if api.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size)):
                return os.path.basename(buf.value)
        finally:
            api.CloseHandle(handle)
        return None
