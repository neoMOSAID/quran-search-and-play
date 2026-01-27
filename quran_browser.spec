# -*- mode: python ; coding: utf-8 -*-

import sys
import os

# -----------------------------------------------------------------------------
# Paths
# -----------------------------------------------------------------------------
spec_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
app_dir = spec_dir

sys.path.insert(0, app_dir)

block_cipher = None

# -----------------------------------------------------------------------------
# Collect python files
# -----------------------------------------------------------------------------
def collect_py_files(directory):
    py_modules = []
    py_datas = []

    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith(".py"):
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, directory)

                module_name = rel_path.replace(os.sep, ".").replace(".py", "")
                if module_name.endswith("__init__"):
                    module_name = module_name[:-9].rstrip(".")

                if module_name:
                    py_modules.append(module_name)

                dest_dir = os.path.dirname(rel_path)
                if not dest_dir:
                    dest_dir = "."   # 🔥 THIS FIXES EVERYTHING

                py_datas.append((full_path, dest_dir))

    return list(set(py_modules)), py_datas


all_modules, all_datas = collect_py_files(app_dir)

print(f"Modules found: {len(all_modules)}")
print(f"Python files as datas: {len(all_datas)}")

# -----------------------------------------------------------------------------
# Analysis
# -----------------------------------------------------------------------------
a = Analysis(
    ["app.py"],
    pathex=[spec_dir],
    binaries=[],
    datas=[
        # Icons
        ("icon.ico", "."),
        ("icon.png", "."),

        # Resources
        ('resources/quran_text/chapters.txt', 'resources/quran_text'),
        ('resources/quran_text/simplified.txt', 'resources/quran_text'),
        ('resources/quran_text/uthmani.txt', 'resources/quran_text'),
        ('resources/help/help_ar.html', 'resources/help'),

        # Cached data
        ("models/*.cache", "models"),
    ] + all_datas,
    hiddenimports=all_modules + [
        # ---- stdlib ----
        "json",
        "sqlite3",
        "threading",
        "multiprocessing",
        "queue",
        "tempfile",
        "datetime",
        "subprocess",
        "re",
        "time",

        # ---- PyQt5 core ----
        "PyQt5",
        "PyQt5.QtCore",
        "PyQt5.QtGui",
        "PyQt5.QtWidgets",
        "PyQt5.QtNetwork",
        "PyQt5.QtMultimedia",
        "PyQt5.QtMultimediaWidgets",

        # ---- WebEngine (CRITICAL) ----
        "PyQt5.QtWebEngine",
        "PyQt5.QtWebEngineCore",
        "PyQt5.QtWebEngineWidgets",
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=[
        "PySide2",
        "PySide6",
        "tkinter",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# -----------------------------------------------------------------------------
# PYZ
# -----------------------------------------------------------------------------
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# -----------------------------------------------------------------------------
# EXE
# -----------------------------------------------------------------------------
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="QuranBrowser",
    debug=False,
    strip=False,
    upx=True,
    console=False,
    icon="icon.ico",
)

