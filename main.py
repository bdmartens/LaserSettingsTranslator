import os
import sys
import customtkinter as ctk

# Ensure workspace folder is in system path for clean imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.gui.main_window import LaserSettingsApp

def main():
    # Set visual theme
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")

    # Initialize and run application
    app = LaserSettingsApp()
    app.mainloop()

if __name__ == "__main__":
    main()
