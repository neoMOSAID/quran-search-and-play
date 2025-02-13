#!/usr/bin/env python
"""
install.py – Install script for Quran Search on Windows

This script creates a command-line wrapper (a .bat file) that launches gui.py
and, if possible, creates a desktop shortcut.
"""

import os
import sys

def create_windows_wrapper():
    # Determine the installation directory (the directory containing this script)
    install_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Determine the path to the Python executable in the virtual environment
    python_exec = os.path.join(install_dir, "env", "python.exe")
    if not os.path.exists(python_exec):
        print("Error: Python executable not found at", python_exec)
        sys.exit(1)
    
    # Create a batch file wrapper in the installation directory
    wrapper_path = os.path.join(install_dir, "quranSearch.bat")
    with open(wrapper_path, "w") as f:
        f.write(r"""@echo off
start "" "{}" "{}"
""".format(python_exec, os.path.join(install_dir, "gui.py")))
    print("Batch file wrapper created at:", wrapper_path)
    
    # Attempt to create a desktop shortcut
    try:
        import winshell
        from win32com.client import Dispatch
        desktop = winshell.desktop()
        shortcut_path = os.path.join(desktop, "Quran Search.lnk")
        target = wrapper_path
        icon = os.path.join(install_dir, "icon.png")
        
        shell = Dispatch('WScript.Shell')
        shortcut = shell.CreateShortCut(shortcut_path)
        shortcut.Targetpath = target
        shortcut.WorkingDirectory = install_dir
        # Use the icon if available, else default to the batch file
        shortcut.IconLocation = icon if os.path.exists(icon) else target
        shortcut.save()
        print("Desktop shortcut created at:", shortcut_path)
    except ImportError:
        print("winshell module not found. To create a desktop shortcut, install it via pip (pip install winshell pywin32).")
    except Exception as e:
        print("Error creating desktop shortcut:", e)

if __name__ == "__main__":
    if os.name != "nt":
        print("This install.py script is intended for Windows systems.")
        sys.exit(1)
    create_windows_wrapper()
    print("Installation completed on Windows.")
