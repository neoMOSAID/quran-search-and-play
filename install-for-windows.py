#!/usr/bin/env python
"""
Enhanced Windows Installer with User-Level Installation Support
"""

import os
import sys
import subprocess
import shutil
import ctypes
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

def is_admin():
    """Check if running with administrator privileges"""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

def get_install_path():
    """Get appropriate install path based on privileges"""
    if is_admin():
        return Path(os.environ.get("ProgramFiles", "C:\\Program Files")) / "Quran Search"
    else:
        return Path(os.environ["APPDATA"]) / "Quran Search"

def create_virtualenv(venv_path):
    """Create virtual environment with improved error handling"""
    try:
        subprocess.run([sys.executable, "-m", "venv", str(venv_path)], check=True)
        logging.info(f"Created virtual environment at {venv_path}")
        return True
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
    # Set up paths
    source_dir = Path(__file__).parent.resolve()
    install_dir = get_install_path()
    venv_path = install_dir / "venv"

    try:
        # Create installation directory
        install_dir.mkdir(parents=True, exist_ok=True)
        logging.info(f"Installation directory: {install_dir}")

        # Copy files
        logging.info("Copying application files...")
        shutil.copytree(source_dir, install_dir, dirs_exist_ok=True)

        # Create virtual environment
        if not create_virtualenv(venv_path):
            logging.error("Virtual environment creation failed")
            sys.exit(1)

        # Install requirements
        # Install requirements from requirements.txt, winshell, and pywin32
        req_file = install_dir / "requirements.txt"
        if not install_packages(venv_path, ["-r", str(req_file), "winshell", "pywin32"]):
            logging.error("Initial package installation failed. Attempting to install PyQt5 and PyQtWebEngine manually...")
            if not install_packages(venv_path, ["PyQt5", "PyQtWebEngine", "winshell", "pywin32"]):
                logging.error("Manual installation of PyQt5, PyQtWebEngine and , winshell, pywin32 also failed.")
                sys.exit(1)

        # Create launcher
        python_exe = venv_path / "Scripts" / "pythonw.exe"
        gui_script = install_dir / "gui.py"
        bat_launcher = install_dir / "quran-search.bat"
        
        with open(bat_launcher, 'w') as f:
            f.write(f'@"{python_exe}" "{gui_script}" %*')

        # Create shortcuts
        try:
            from winshell import desktop, shortcut
            shortcut_path = desktop() / "Quran Search.lnk"
            with shortcut.Shortcut(shortcut_path) as s:
                s.path = str(bat_launcher)
                s.working_directory = str(install_dir)
                s.icon_location = (str(install_dir / "icon.ico"), 0)
                s.write()
            logging.info("Created desktop shortcut using winshell")
        except ImportError:
            logging.warning("winshell/pywin32 not available, using VBScript fallback")
            create_desktop_shortcut(bat_launcher, install_dir / "icon.ico")

        logging.info("Installation completed successfully")

    except Exception as e:
        logging.error(f"Installation failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()