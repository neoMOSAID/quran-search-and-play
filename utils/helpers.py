import os
import sys

def resource_path(relative_path):
    """Get absolute path to resource, works for both development and PyInstaller."""
    try:
        # When running as a bundled executable
        base_path = sys._MEIPASS
    except AttributeError:
        # When running in development
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)



def get_default_audio_directory():
    from utils.settings import AppSettings

    app_settings = AppSettings()
    return app_settings.ensure_default_audio_directory()


def get_audio_directory():
    from utils.settings import AppSettings

    app_settings = AppSettings()
    return app_settings.get_audio_directory(get_default_audio_directory())


