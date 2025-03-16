import os
from PyQt5.QtCore import QSettings, QStandardPaths

class AppSettings:
    def __init__(self):
        self.settings = QSettings("MOSAID", "QuranSearch")
    
    def get(self, key, default=None):
        return self.settings.value(key, default)

    def set(self, key, value):
        self.settings.setValue(key, value)

    def get_bool(self, key, default=False):
        return self.settings.value(key, default, type=bool)

    def value(self, key, default=None, type=None):
        if type is not None:
            return self.settings.value(key, default, type)
        return self.settings.value(key, default)
        
    def get_audio_directory(self):
        """Returns the saved audio directory or creates the default one if not set."""
        if not self.settings.contains("AudioDirectory"):
            default_dir = self.default_audio_directory()
            self.set("AudioDirectory", default_dir)
        return self.get("AudioDirectory")

    def set_audio_directory(self, path):
        self.set("AudioDirectory", path)

    def get_last_directory(self):
        """Returns the last directory used for import/export."""
        return self.get("LastDirectory", QStandardPaths.writableLocation(QStandardPaths.HomeLocation))

    def set_last_directory(self, path):
        self.set("LastDirectory", os.path.dirname(path))

    def default_audio_directory(self):
        """Creates the default audio directory inside Music/Abdul Basit Mujawwad."""
        music_dir = QStandardPaths.writableLocation(QStandardPaths.MusicLocation)
        default_dir = os.path.join(music_dir, "Abdul Basit Mujawwad")
        os.makedirs(default_dir, exist_ok=True)
        return default_dir
