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
        logging.error(f"Virtual environment creation failed: {e}")
        return False

def install_packages(venv_path, packages):
    """Install packages with retry logic using python -m pip."""
    python_exe = venv_path / "Scripts" / "python.exe"
    for attempt in range(2):
        try:
            subprocess.run([str(python_exe), "-m", "pip", "install"] + packages, check=True)
            logging.info(f"Installed packages: {', '.join(packages)}")
            return True
        except subprocess.CalledProcessError as e:
            logging.warning(f"Package installation failed (attempt {attempt+1}): {e}")
    return False


def create_desktop_shortcut(target, icon=None):
    """Create desktop shortcut using VBScript as fallback"""
    desktop = Path.home() / "Desktop"
    vbs_script = desktop / "Quran Search.vbs"
    
    script_content = f'''
    Set WshShell = WScript.CreateObject("WScript.Shell")
    Set shortcut = WshShell.CreateShortcut("{desktop / 'Quran Search.lnk'}")
    shortcut.TargetPath = "{target}"
    shortcut.WorkingDirectory = "{target.parent}"
    shortcut.IconLocation = "{icon if icon else target}"
    shortcut.Save
    '''
    
    try:
        with open(vbs_script, 'w') as f:
            f.write(script_content)
        subprocess.run(['cscript.exe', '//B', str(vbs_script)], check=True)
        vbs_script.unlink()
        logging.info("Created desktop shortcut via VBScript fallback")
        return True
    except Exception as e:
        logging.error(f"Failed to create desktop shortcut: {e}")
        return False

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