#!/usr/bin/env python
"""
install.py – Enhanced Install Script for Quran Search on Windows

This script performs the following:
1. Creates a virtual environment (in the "env" folder) if it doesn’t already exist.
2. Installs required dependencies from requirements.txt.
3. Creates a command-line wrapper (a .bat file) that launches gui.py using the virtual environment's Python.
4. Attempts to create a desktop shortcut for the application.
"""

import os
import sys
import subprocess

def create_virtual_environment(install_dir):
    """Create a virtual environment in the 'env' folder if it does not exist."""
    venv_path = os.path.join(install_dir, "env")
    if os.path.exists(venv_path):
        print("Virtual environment already exists at:", venv_path)
        return venv_path

    print("Creating virtual environment at:", venv_path)
    try:
        subprocess.check_call([sys.executable, "-m", "venv", venv_path])
    except subprocess.CalledProcessError as e:
        print("Error creating virtual environment:", e)
        sys.exit(1)
    return venv_path


def install_requirements(venv_path, install_dir): 
    """Install dependencies from requirements.txt using the virtual environment's pip. 
    If installation fails (e.g., due to version conflicts for PyQt5 or PyQtWebEngine),
    it will attempt to install these two packages individually without version restrictions. """ 
    req_file = os.path.join(install_dir, "requirements.txt") 
    if not os.path.exists(req_file): 
        print("No requirements.txt found in", install_dir) 
        return
    
    print("Installing requirements from:", req_file)
    # On Windows, the pip executable is located in the Scripts folder.
    pip_executable = os.path.join(venv_path, "Scripts", "pip.exe")
    if not os.path.exists(pip_executable):
        print("pip executable not found at:", pip_executable)
        sys.exit(1)
    try:
        subprocess.check_call([pip_executable, "install", "-r", req_file])
    except subprocess.CalledProcessError as e:
        print("Error installing requirements with specified versions:", e)
        print("No matching versions found. Trying to install PyQt5 and PyQtWebEngine individually without version restrictions.")
        try:
            subprocess.check_call([pip_executable, "install", "PyQt5", "PyQtWebEngine"])
        except subprocess.CalledProcessError as e2:
            print("Error installing PyQt5 and PyQtWebEngine individually:", e2)
            sys.exit(1)


def create_windows_wrapper(install_dir, venv_path):
    """Create a batch file wrapper and optionally a desktop shortcut."""
    # Determine the path to the Python executable in the virtual environment.
    python_exec = os.path.join(venv_path, "Scripts", "python.exe")
    if not os.path.exists(python_exec):
        print("Error: Python executable not found at", python_exec)
        sys.exit(1)
    
    # Create a batch file wrapper in the installation directory.
    wrapper_path = os.path.join(install_dir, "quranSearch.bat")
    with open(wrapper_path, "w") as f:
        f.write(r"""@echo off
start "" "{}" "{}"
""".format(python_exec, os.path.join(install_dir, "gui.py")))
    print("Batch file wrapper created at:", wrapper_path)
    
    # Attempt to create a desktop shortcut.
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
        # Use the icon if available; otherwise, default to the batch file.
        shortcut.IconLocation = icon if os.path.exists(icon) else target
        shortcut.save()
        print("Desktop shortcut created at:", shortcut_path)
    except ImportError:
        print("winshell module not found. To create a desktop shortcut, install it via pip (pip install winshell pywin32).")
    except Exception as e:
        print("Error creating desktop shortcut:", e)

def main():
    if os.name != "nt":
        print("This install.py script is intended for Windows systems.")
        sys.exit(1)
    
    # Determine the installation directory (the directory containing this script)
    install_dir = os.path.dirname(os.path.abspath(__file__))
    print("Installation directory:", install_dir)
    
    # Step 1: Create the virtual environment.
    venv_path = create_virtual_environment(install_dir)
    
    # Step 2: Install required packages from requirements.txt.
    install_requirements(venv_path, install_dir)
    
    # Step 3: Create the command-line wrapper and desktop shortcut.
    create_windows_wrapper(install_dir, venv_path)
    
    print("Installation completed on Windows.")

if __name__ == "__main__":
    main()
