import os
import sys

def resource_path(relative_path):
    """Get absolute path to resource, works for both development and PyInstaller."""
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except AttributeError:
        # In development, base path is the project root (parent of utils directory)
        base_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    
    return os.path.join(base_path, relative_path)

def get_default_audio_directory():
    from utils.settings import AppSettings

    app_settings = AppSettings()
    return app_settings.default_audio_directory()


def get_audio_directory():
    from utils.settings import AppSettings

    app_settings = AppSettings()
    return app_settings.get_audio_directory()


