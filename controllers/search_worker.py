
import logging

from PyQt5 import QtCore


class SearchWorker(QtCore.QThread):
    results_ready = QtCore.pyqtSignal(list)
    error_occurred = QtCore.pyqtSignal(str)

    def __init__(self, search_engine, method, query, is_dark_theme, parent=None):
        super().__init__(parent)
        self.parent = parent  
        self.search_engine = search_engine
        self.method = method
        self.query = query
        self.is_dark_theme = is_dark_theme  

    def run(self):
        try:
            if self.method == "Text":
                results = self.search_engine.search_verses(self.query,self.is_dark_theme)
            elif self.method == "Surah":
                if self.query.isdigit():
                    results = self.search_engine.search_by_surah(int(self.query))
                else:
                    results = []
            elif self.method == "Surah FirstAyah LastAyah":
                parts = [int(p) for p in self.query.split() if p.isdigit()]
                if len(parts) == 2:
                    results = self.search_engine.search_by_surah_ayah(parts[0], parts[1])
                elif len(parts) == 3:
                    results = self.search_engine.search_by_surah_ayah(parts[0], parts[1], parts[2])
                else:
                    results = []
            else:
                results = []
            
            for result in results:
                if self.parent.notes_manager.has_note(result['surah'], result['ayah']):
                    #bullet = "● "  # smaller bullet than "●"
                    bullet = "<span style='font-size:32px;'>•</span> "
                    result['text_simplified'] = bullet + result['text_simplified']
                    result['text_uthmani'] = bullet + result['text_uthmani']
            self.results_ready.emit(results)
        except Exception as e:
            logging.exception("Error during search")
            self.error_occurred.emit(str(e))
