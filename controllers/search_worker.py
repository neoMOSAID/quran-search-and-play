
import logging

from PyQt5 import QtCore

class SearchWorker(QtCore.QThread):
    results_ready = QtCore.pyqtSignal(str, list, int)
    error_occurred = QtCore.pyqtSignal(str)
    
    def __init__(self, search_engine, method, query, is_dark_theme=False, 
                 highlight_words=None, surah_to_search=None, parent=None):
        super().__init__(parent)
        self.search_engine = search_engine
        self.method = method
        self.query = query
        self.is_dark_theme = is_dark_theme
        self.highlight_words = highlight_words or []
        self.surah_to_search = surah_to_search
        
    def run(self):
        try:
            if self.method == "Text":
                # Check if we need to search in a specific surah
                if self.surah_to_search:
                    results, total_occurrences = self.search_engine.search_in_surah(
                        self.query, 
                        self.surah_to_search,
                        self.is_dark_theme, 
                        self.highlight_words
                    )
                else:
                    # Regular search across all surahs
                    results, total_occurrences = self.search_engine.search_verses(
                        self.query, 
                        self.is_dark_theme, 
                        self.highlight_words
                    )
                    
            elif self.method == "Surah":
                surah_num = int(self.query) if self.query.isdigit() else 1
                results = self.search_engine.search_by_surah(
                    surah_num, 
                    self.is_dark_theme, 
                    self.highlight_words
                )
                total_occurrences = 0
                
            elif self.method == "Surah FirstAyah LastAyah":
                parts = self.query.split()
                if len(parts) == 1:
                    surah = int(parts[0]) if parts[0].isdigit() else 1
                    first = 1
                    last = self.search_engine.get_verse_count(surah)
                elif len(parts) == 2:
                    surah = int(parts[0]) if parts[0].isdigit() else 1
                    first = int(parts[1]) if parts[1].isdigit() else 1
                    last = first
                elif len(parts) >= 3:
                    surah = int(parts[0]) if parts[0].isdigit() else 1
                    first = int(parts[1]) if parts[1].isdigit() else 1
                    last = int(parts[2]) if parts[2].isdigit() else first
                else:
                    surah = 1
                    first = 1
                    last = 1
                    
                results = self.search_engine.search_by_surah_ayah(
                    surah, first, last, 
                    self.is_dark_theme, 
                    self.highlight_words
                )
                total_occurrences = 0
                
            else:
                results = []
                total_occurrences = 0
                
            self.results_ready.emit(self.method, results, total_occurrences)
            
        except Exception as e:
            self.error_occurred.emit(str(e))
