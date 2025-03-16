
import os
import time
from pathlib import Path

from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEnginePage
from PyQt5.QtGui import QColor

from views.web_view import CustomWebEnginePage
from utils.helpers import resource_path

class HelpDialog(QtWidgets.QDialog):
    _instance = None  # Singleton instance
    _cache = None
    DARK_CSS =  """
        <style>
            body {
                background-color: #333333 !important;
                color: #FFFFFF !important;
            }
            a {
                color: #1a73e8 !important;
            }
            h1, h2, h3 {
                border-color: #1a73e8 !important;
            }
            .section, table {
                background-color: #444444 !important;
                color: #FFFFFF !important;
                box-shadow: none !important;
            }
            .shortcut-key {
                background: red;
            }
        </style>
        """
    
    def __new__(cls, parent=None):
        if not cls._instance:
            cls._instance = super().__new__(cls)
            cls._cache = HelpCacheManager()
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self, parent=None):
        if self._initialized:
            return
        super().__init__(parent)
        self._initialized = True
        self.setup_ui()
        self.parent = parent
        
    def setup_ui(self):
        self.setWindowTitle("دليل استخدام متصفح القرآن المتقدم")
        self.resize(800, 600)
        self.setWindowModality(QtCore.Qt.NonModal)
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose, False)
        
        layout = QtWidgets.QVBoxLayout(self)
        self.web_view = QWebEngineView(self)
        self.web_view.setPage(CustomWebEnginePage(self.web_view))
        layout.addWidget(self.web_view)
        
    def load_content(self):
        dark_mode = self.parent.theme_action.isChecked() if self.parent else False
        content = self._cache.get_content(dark_mode)
        self.web_view.page().setBackgroundColor(QColor("#333" if dark_mode else "#FFF"))
        base_url = QtCore.QUrl.fromLocalFile(str(HelpCacheManager._file_path.parent))
        self.web_view.setHtml(content, base_url)
        
    def toggle_theme(self, dark_mode):
        self.web_view.page().setBackgroundColor(QColor("#333" if dark_mode else "#FFF"))
        self.load_content()
        
    def showEvent(self, event):
        self.load_content()
        super().showEvent(event)



class HelpCacheManager:
    _instance = None
    _content = ""
    _dark_content = ""
    _last_modified = 0
    _file_path = Path(resource_path("resources/help/help_ar.html"))

    def __new__(cls):
        if not cls._instance:
            cls._instance = super().__new__(cls)
            cls._load_content()
        return cls._instance
    
    @classmethod
    def _load_content(cls):
        try:
            if cls._file_path.exists():
                cls._last_modified = cls._file_path.stat().st_mtime
                with open(cls._file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    cls._content = content
                    cls._dark_content = content.replace("</head>", HelpDialog.DARK_CSS + "</head>")
        except Exception as e:
            logging.error(f"Help content error: {str(e)}")
            cls._content = cls._dark_content = "<h1>Help content unavailable</h1>"
    
    @classmethod
    def get_content(cls, dark_mode=False):
        # Refresh content every 5 minutes
        if time.time() - cls._last_modified > 300:
            cls._load_content()
            
        return cls._dark_content if dark_mode else cls._content

