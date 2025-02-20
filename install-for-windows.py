#!/usr/bin/env python
"""
Enhanced Install Script for Quran Search on Windows

This script performs the following:
1. Copies necessary files from the source directory to a secure installation directory 
   (by default: "C:\Program Files\Quran Search").
2. Creates a virtual environment (in the "env" folder) if it doesn’t already exist.
3. Installs required dependencies from requirements.txt.
4. Ensures winshell and pywin32 are installed (needed for shortcut creation).
5. Creates two launchers:
   - A CLI batch file launcher.
   - A subtle VBScript launcher (which hides the command window).
6. Creates an uninstall.bat that removes the secure install directory.
7. Creates a Start Menu folder containing shortcuts to the subtle launcher and the uninstall script.
"""

import os
import sys
import subprocess
import shutil

def create_secure_directory(secure_dir):
    if not os.path.exists(secure_dir):
        os.makedirs(secure_dir)
        print("Created secure directory:", secure_dir)
    else:
        print("Secure directory already exists:", secure_dir)

def copy_files_to_secure_dir(source_dir, secure_dir):
    """
    Copy all necessary files from source_dir to secure_dir.
    Skip directories or files that are generated (like 'env' or previous launchers).
    """
    for item in os.listdir(source_dir):
        if item in ["env", "uninstall.bat", "quranSearch.bat", "quranSearch.vbs", "venv_win"]:
            continue  # Skip generated files and folders
        src = os.path.join(source_dir, item)
        dst = os.path.join(secure_dir, item)
        try:
            if os.path.isdir(src):
                if os.path.exists(dst):
                    shutil.rmtree(dst)
                shutil.copytree(src, dst)
                print("Copied directory:", src, "to", dst)
            else:
                shutil.copy2(src, dst)
                print("Copied file:", src, "to", dst)
        except Exception as e:
            print("Error copying {}: {}".format(src, e))

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
    """
    Install dependencies from requirements.txt using the virtual environment's pip.
    If installation fails (e.g., version conflicts for PyQt5 or PyQtWebEngine),
    it will try to install these two packages individually.
    """
    req_file = os.path.join(install_dir, "requirements.txt")
    if not os.path.exists(req_file):
        print("No requirements.txt found in", install_dir)
        return

    print("Installing requirements from:", req_file)
    pip_executable = os.path.join(venv_path, "Scripts", "pip.exe")
    if not os.path.exists(pip_executable):
        print("pip executable not found at:", pip_executable)
        sys.exit(1)
    try:
        subprocess.check_call([pip_executable, "install", "-r", req_file])
    except subprocess.CalledProcessError as e:
        print("Error installing requirements with specified versions:", e)
        print("Attempting to install PyQt5 and PyQtWebEngine without version restrictions.")
        try:
            subprocess.check_call([pip_executable, "install", "PyQt5", "PyQtWebEngine"])
        except subprocess.CalledProcessError as e2:
            print("Error installing PyQt5 and PyQtWebEngine:", e2)
            sys.exit(1)

def ensure_extra_packages(venv_path):
    """
    Ensure that winshell and pywin32 are installed,
    as they are needed to create shortcuts.
    """
    pip_executable = os.path.join(venv_path, "Scripts", "pip.exe")
    try:
        subprocess.check_call([pip_executable, "install", "winshell", "pywin32"])
        print("Installed winshell and pywin32.")
    except subprocess.CalledProcessError as e:
        print("Error installing winshell and pywin32:", e)
        sys.exit(1)

def create_launchers(install_dir, venv_path):
    """
    Create two launcher files:
    1. A CLI batch wrapper (quranSearch.bat) that runs gui.py using the virtual environment's Python.
    2. A subtle VBScript launcher (quranSearch.vbs) that starts the application with no visible console.
    """
    python_exec = os.path.join(venv_path, "Scripts", "python.exe")
    if not os.path.exists(python_exec):
        print("Error: Python executable not found at", python_exec)
        sys.exit(1)
    gui_py = os.path.join(install_dir, "gui.py")
    if not os.path.exists(gui_py):
        print("Error: gui.py not found in", install_dir)
        sys.exit(1)
    
    # Create CLI batch wrapper (still provided for users who prefer it)
    cli_wrapper_path = os.path.join(install_dir, "quranSearch.bat")
    with open(cli_wrapper_path, "w") as f:
        f.write(r'''@echo off
"%~dp0\env\Scripts\python.exe" "%~dp0\gui.py"
pause
''')
    print("Created CLI batch launcher at:", cli_wrapper_path)
    
    # Create subtle VBScript launcher to avoid the cmd window
    vbscript_path = os.path.join(install_dir, "quranSearch.vbs")
    # The VBScript directly launches the Python executable with gui.py hidden (0 = no window)
    command = '"{}" "{}"'.format(python_exec, gui_py)
    vbscript_content = (
        'Set WshShell = CreateObject("WScript.Shell")\n'
        'WshShell.Run "{}", 0, False'.format(command)
    )
    with open(vbscript_path, "w") as f:
        f.write(vbscript_content)
    print("Created VBScript launcher at:", vbscript_path)
    
    return cli_wrapper_path, vbscript_path

def create_uninstall_script(install_dir):
    """
    Create an uninstall.bat that, when run, will remove the secure installation directory
    (i.e. the virtual environment and all copied files).
    WARNING: This will delete ALL files in the install directory.
    """
    uninstall_path = os.path.join(install_dir, "uninstall.bat")
    uninstall_content = r'''@echo off
echo Uninstalling Quran Search...
cd /d "%~dp0"
rmdir /S /Q .
echo Uninstallation complete.
pause
'''
    with open(uninstall_path, "w") as f:
        f.write(uninstall_content)
    print("Created uninstall script at:", uninstall_path)
    return uninstall_path

def create_start_menu_shortcuts(install_dir, subtle_launcher, uninstall_script):
    """
    Create a Start Menu folder ("Quran Search") and add shortcuts for:
    - The subtle (VBScript) launcher.
    - The uninstall script.
    """
    try:
        import winshell
        from win32com.client import Dispatch
    except ImportError:
        print("winshell and pywin32 are not available; cannot create Start Menu shortcuts.")
        return
    # Determine the Start Menu folder path (per-user)
    start_menu_dir = os.path.join(os.environ.get("APPDATA"), "Microsoft", "Windows", "Start Menu", "Programs", "Quran Search")
    if not os.path.exists(start_menu_dir):
        os.makedirs(start_menu_dir)
        print("Created Start Menu directory at:", start_menu_dir)
    
    shell = Dispatch('WScript.Shell')
    
    # Shortcut for the subtle launcher
    shortcut_path = os.path.join(start_menu_dir, "Quran Search.lnk")
    shortcut = shell.CreateShortCut(shortcut_path)
    # Use the VBScript launcher so that no console window appears.
    shortcut.Targetpath = os.path.abspath(subtle_launcher)
    shortcut.WorkingDirectory = install_dir
    icon_path = os.path.join(install_dir, "icon.ico")
    if os.path.exists(icon_path):
        shortcut.IconLocation = icon_path
    else:
        shortcut.IconLocation = shortcut.Targetpath
    shortcut.save()
    print("Created Start Menu shortcut at:", shortcut_path)
    
    # Shortcut for uninstalling the application
    uninstall_shortcut_path = os.path.join(start_menu_dir, "Uninstall Quran Search.lnk")
    uninstall_shortcut = shell.CreateShortCut(uninstall_shortcut_path)
    uninstall_shortcut.Targetpath = os.path.abspath(uninstall_script)
    uninstall_shortcut.WorkingDirectory = install_dir
    uninstall_shortcut.IconLocation = uninstall_shortcut.Targetpath
    uninstall_shortcut.save()
    print("Created Start Menu uninstall shortcut at:", uninstall_shortcut_path)

def main():
    if os.name != "nt":
        print("This install.py script is intended for Windows systems.")
        sys.exit(1)
    
    # Determine the current (source) installation directory (the directory containing this script)
    source_dir = os.path.dirname(os.path.abspath(__file__))
    print("Source directory:", source_dir)
    
    # Define the secure installation directory (defaulting to "Program Files\Quran Search")
    program_files = os.environ.get("ProgramFiles", "C:\\Program Files")
    secure_dir = os.path.join(program_files, "Quran Search")
    
    # Create the secure installation directory and copy files to it
    create_secure_directory(secure_dir)
    copy_files_to_secure_dir(source_dir, secure_dir)
    
    # Now work in the secure installation directory
    install_dir = secure_dir
    print("Installation directory (secure):", install_dir)
    
    # Create the virtual environment
    venv_path = create_virtual_environment(install_dir)
    
    # Install required packages from requirements.txt
    install_requirements(venv_path, install_dir)
    
    # Ensure winshell and pywin32 are installed
    ensure_extra_packages(venv_path)
    
    # Create launchers (both CLI and subtle VBScript)
    cli_launcher, vbscript_launcher = create_launchers(install_dir, venv_path)
    
    # Create the uninstall script
    uninstall_script = create_uninstall_script(install_dir)
    
    # Create Start Menu shortcuts (in a Start folder containing the subtle launcher and uninstall shortcut)
    create_start_menu_shortcuts(install_dir, vbscript_launcher, uninstall_script)
    
    print("Installation completed on Windows in secure directory:", install_dir)

if __name__ == "__main__":
    main()
