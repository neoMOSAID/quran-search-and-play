
from PyQt5 import QtWidgets, QtCore
from models.search_engine import QuranSearch, QuranWordCache


class SearchLineEdit(QtWidgets.QLineEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        QuranWordCache(QuranSearch())
        self.history_max = 500  # 
        self.init_completer()
        self.init_history()

        # Setup text editing signals
        self.textEdited.connect(self.update_completion_prefix)

    def init_completer(self):
        # Create completer with dual models
        self.completer_model = QtCore.QStringListModel()
        
        self.completer = QtWidgets.QCompleter()
        self.completer.setCaseSensitivity(QtCore.Qt.CaseInsensitive)
        self.completer.setFilterMode(QtCore.Qt.MatchContains)
        self.completer.setModel(self.completer_model)
        self.completer.setCompletionMode(QtWidgets.QCompleter.PopupCompletion)
        self.completer.activated.connect(self.on_completer_activated)
        # Arabic font styling
        self.completer.popup().setStyleSheet("""
            QListView {
                font-family: 'Amiri';
                font-size: 14pt;
            }
        """)
        
        self.setCompleter(self.completer)
        
        # Load Quran words in background
        QtCore.QTimer.singleShot(100, self.update_completer_model)

    def on_completer_activated(self, text):
        """Handle selection from completer popup"""
        if text == "── Quran Words ──":
            return  # Ignore the separator line
        self.setText(text)
        self._history_index = -1
        self.update_history(text)
        self.returnPressed.emit()  # Trigger search immediately

    def init_history(self):
        # Create history menu
        self.history_menu = QtWidgets.QMenu(self)
        self.history_list = QtWidgets.QListWidget()
        self.history_menu.setLayout(QtWidgets.QVBoxLayout())
        self.history_menu.layout().addWidget(self.history_list)
        self.history_list.itemClicked.connect(self.select_history_item)

        # Load persisted history
        settings = QtCore.QSettings("MOSAID", "QuranSearch")
        self.history = settings.value("searchHistory", [], type=list)
        self.history = self.history[:self.history_max]  # Enforce max limit
        self.update_history_list()

        self.update_completer_model()

    def select_history_item(self, item):
        self.setText(item.text())
        self.returnPressed.emit()

    def update_history(self, query):
        """Update search history, moving existing entries to the top"""
        if not query.strip():
            return

        self._history_index = -1
        # Remove existing entry (if any) to avoid duplicates
        if query in self.history:
            self.history.remove(query)
        
        # Insert at the beginning (most recent first)
        self.history.insert(0, query)
        
        # Enforce max limit
        self.history = self.history[:self.history_max]
        
        # Persist to settings
        settings = QtCore.QSettings("MOSAID", "QuranSearch")
        settings.setValue("searchHistory", self.history)
        
        # Refresh UI and completer
        self.update_history_list()
        self.update_completer_model()

    # def update_history(self, query):
    #     """Update both history and completer"""
    #     if query and query not in self.history:
    #         self.history.insert(0, query)
    #         self.history = self.history[:self.history_max]
    #         settings = QtCore.QSettings("MOSAID", "QuranSearch")
    #         settings.setValue("searchHistory", self.history)
    #         self.update_history_list()
    #         self.update_completer_model()
        
    def update_completer_model(self):
        """Combine search history and Quran words, maintaining order"""
        # Separate history and Quran words with a divider
        combined = self.history.copy()
        combined.append("── Quran Words ──")  # Divider line
        combined.extend(QuranWordCache._words)
        
        self.completer_model.setStringList(combined)

    def update_history_list(self):
        self.history_list.clear()
        for item in self.history:
            self.history_list.addItem(item)

    def update_completion_prefix(self, text):
        """Handle RTL text properly"""
        if text.strip():
            self.completer.setCompletionPrefix(text)
            if self.completer.completionCount() > 0:
                self.completer.complete()

    #still unused
    def clear_history(self):
        settings = QtCore.QSettings("MOSAID", "QuranSearch")
        settings.remove("searchHistory")
        self.history = []
        self.update_history_list()

    def keyPressEvent(self, event):
        if event.key() in (QtCore.Qt.Key_Up, QtCore.Qt.Key_Down):
            self.handle_history_navigation(event.key())
        elif event.key() == QtCore.Qt.Key_Return or event.key() == QtCore.Qt.Key_Enter:
            # Reset history index on search execution
            self._history_index = -1
            super().keyPressEvent(event) 
        else:
            super().keyPressEvent(event)

    def handle_history_navigation(self, key):
        if not hasattr(self, '_history_index'):
            self._history_index = -1

        if key == QtCore.Qt.Key_Up:
            self._history_index = min(self._history_index + 1, len(self.history)-1)
        elif key == QtCore.Qt.Key_Down:
            self._history_index = max(self._history_index - 1, -1)

        if self._history_index >= 0:
            self.setText(self.history[self._history_index])
        else:
            self.clear()


