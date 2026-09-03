import sys
import os
import subprocess

# Auto-trampoline: jika dijalankan sebagai entry point dari Python luar .venv, alihkan otomatis ke .venv
if __name__ == "__main__" and not getattr(sys, 'frozen', False):
    venv_python = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.venv', 'Scripts', 'python.exe')
    if os.path.exists(venv_python) and os.path.abspath(sys.executable).lower() != os.path.abspath(venv_python).lower():
        sys.exit(subprocess.call([venv_python, os.path.abspath(__file__)] + sys.argv[1:]))

# Ensure src in system paths
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

import customtkinter as ctk
from ui.app_window import UniversalAccurateConverter

if __name__ == "__main__":
    root = ctk.CTk()
    app = UniversalAccurateConverter(root)
    root.mainloop()
