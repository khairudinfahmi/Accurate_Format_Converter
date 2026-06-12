import sys
import os

# Ensure src in system paths
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

import customtkinter as ctk
from ui.app_window import UniversalAccurateConverter

if __name__ == "__main__":
    root = ctk.CTk()
    app = UniversalAccurateConverter(root)
    root.mainloop()
