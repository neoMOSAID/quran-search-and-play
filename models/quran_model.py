from PyQt5 import QtCore

#class QuranListModel(QtCore.QAbstractListModel):
    # Keep all original methods:
    # - loading_complete signal
    # - data()
    # - rowCount()
    # - appendResults()
    # - updateResults()
    # - load_remaining_results()
    # - handle_pending_scroll()   

class QuranListModel(QtCore.QAbstractListModel):
    loading_complete = QtCore.pyqtSignal()
    def __init__(self, results=None, parent=None):
        super().__init__(parent)
        self.results = results or []
        self._displayed_results = 0
        self.loading_complete.connect(self.handle_loading_complete, QtCore.Qt.UniqueConnection)

    def handle_loading_complete(self):
        # Handle any final loading tasks
        pass

    def data(self, index, role=QtCore.Qt.DisplayRole):
        if not index.isValid() or index.row() >= len(self.results):
            return None

        result = self.results[index.row()]

        if role == QtCore.Qt.DisplayRole:
            return result.get('text_uthmani', '')
        elif role == QtCore.Qt.UserRole:
            return result
        return None

    def rowCount(self, parent=QtCore.QModelIndex()):
        return self._displayed_results

    def appendResults(self, new_results):
        start = self._displayed_results
        end = start + len(new_results)
        self.beginInsertRows(QtCore.QModelIndex(), start, end-1)
        self.results.extend(new_results)
        self._displayed_results = len(self.results)  # Show all immediately for now
        self.endInsertRows()

    def updateResults(self, results):
        self.beginResetModel()
        self.results = results
        self._displayed_results = min(50, len(results))  # Initial batch
        self.endResetModel()
        # Schedule remaining results
        if len(results) > 50:
            QtCore.QTimer.singleShot(100, lambda: self.load_remaining_results())

    def load_remaining_results(self):
        """Force load next chunk immediately"""
        remaining = len(self.results) - self._displayed_results
        if remaining > 0:
            batch_size = min(100, remaining)
            self.beginInsertRows(QtCore.QModelIndex(),
                               self._displayed_results,
                               self._displayed_results + batch_size - 1)
            self._displayed_results += batch_size
            self.endInsertRows()
            self.loading_complete.emit()



#class BookmarkModel(QtCore.QAbstractListModel):
    # Keep all original methods:
    # - load_bookmarks()
    # - load_next_chunk()
    # - data()
    # - rowCount()

class BookmarkModel(QtCore.QAbstractListModel):
    def __init__(self):
        super().__init__()
        self._bookmarks = []
        self._loaded_count = 0
        self.chunk_size = 100  # Items per chunk
        self.load_timer = QtCore.QTimer()
        self.load_timer.timeout.connect(self.load_next_chunk)

    def rowCount(self, parent=QtCore.QModelIndex()):
        return min(self._loaded_count, len(self._bookmarks))

    def data(self, index, role=QtCore.Qt.DisplayRole):
        if not index.isValid() or index.row() >= len(self._bookmarks):
            return None
            
        bm = self._bookmarks[index.row()]
        
        if role == QtCore.Qt.DisplayRole:
            return f"""
                <div style='font-family: Amiri; font-size: 14pt'>
                    <b>{bm['surah_name']} - الآية {bm['ayah']}</b><br>
                    <span style='color: #666; font-size: 12pt'>
                        {bm['timestamp'][:16]}
                    </span>
                </div>
            """
        if role == QtCore.Qt.UserRole:
            return bm
        return None

    def load_bookmarks(self, bookmarks):
        self.beginResetModel()
        self._bookmarks = bookmarks
        self._loaded_count = min(self._loaded_count, len(self._bookmarks))
        self.endResetModel()
        self.load_timer.start(0)  # Start loading immediately
        self.layoutChanged.emit()

    def load_next_chunk(self):
        if self._loaded_count >= len(self._bookmarks):
            self.load_timer.stop()
            return
            
        remaining = len(self._bookmarks) - self._loaded_count
        chunk = min(self.chunk_size, remaining)
        
        self.beginInsertRows(QtCore.QModelIndex(), 
                           self._loaded_count, 
                           self._loaded_count + chunk - 1)
        self._loaded_count += chunk
        self.endInsertRows()
