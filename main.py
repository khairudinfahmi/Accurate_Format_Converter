import sys
import os
import subprocess

# Auto-trampoline: jika dijalankan sebagai entry point dari Python luar .venv, alihkan otomatis ke .venv
if __name__ == "__main__" and not getattr(sys, 'frozen', False):
    venv_python = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.venv', 'Scripts', 'python.exe')
    if os.path.exists(venv_python) and os.path.abspath(sys.executable).lower() != os.path.abspath(venv_python).lower():
        sys.exit(subprocess.call([venv_python, os.path.abspath(__file__)] + sys.argv[1:]))

# Single Instance Protection via Win32 Named Mutex
def ensure_single_instance():
    try:
        import ctypes
        from ctypes import wintypes
        kernel32 = ctypes.windll.kernel32
        mutex = kernel32.CreateMutexW(None, False, "AccurateFormatConverter_SingleInstance_Mutex")
        if kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
            try:
                user32 = ctypes.windll.user32
                def enum_cb(h, l):
                    if user32.IsWindowVisible(h):
                        length = user32.GetWindowTextLengthW(h)
                        if length > 0:
                            buff = ctypes.create_unicode_buffer(length + 1)
                            user32.GetWindowTextW(h, buff, length + 1)
                            if "Accurate Format Converter" in buff.value:
                                user32.ShowWindow(h, 9)  # SW_RESTORE
                                user32.SetForegroundWindow(h)
                                return False
                    return True
                cb = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)(enum_cb)
                user32.EnumWindows(cb, 0)
            except Exception:
                pass
            sys.exit(0)
        return mutex
    except Exception:
        return None

_app_mutex = ensure_single_instance()

# Ensure src in system paths
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

import customtkinter as ctk
from ui.app_window import UniversalAccurateConverter

if __name__ == "__main__":
    root = ctk.CTk()
    app = UniversalAccurateConverter(root)
    root.mainloop()
