#!/usr/bin/env python3
"""
Improved Quran Browser with:
- Model–View architecture using QAbstractListModel
- Asynchronous search using QThread
- Integrated audio playback using QMediaPlayer
- Persistent user settings with QSettings
- Logging for error handling
- UI enhancements with QSplitter for layout
"""

import os
import sys
import logging
from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtCore import QUrl, QSize, Qt, QSettings, QTimer
from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent
from PyQt5.QtCore import QStandardPaths, QSettings
from search import QuranSearch  


# Configure logging for debugging and error reporting.
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')


def get_default_audio_directory():
    music_dir = QStandardPaths.writableLocation(QStandardPaths.MusicLocation)
    # Ensure the directory exists (create it if not)
    default_dir = os.path.join(music_dir, "Abelbaset")
    if not os.path.isdir(default_dir):
        try:
            os.makedirs(default_dir, exist_ok=True)
        except Exception as e:
            # Log or handle the exception as needed.
            print("Error creating default audio directory:", e)
    return default_dir

def get_audio_directory():
    """
    Retrieve the audio directory from an INI file.
    If the setting doesn't exist, create the INI file with a default value.
    The INI file is stored in the user's home directory as ".quran_audio.ini".
    """
    # Build the config file path (hidden file in the user's home directory)
    config_file = os.path.join(os.path.expanduser("~"), ".quran_audio.ini")
    settings = QSettings(config_file, QSettings.IniFormat)
    
    # Check if the AudioDirectory key exists; if not, set it to the default.
    if not settings.contains("AudioDirectory"):
        default_dir = get_default_audio_directory()
        settings.setValue("AudioDirectory", default_dir)
        settings.sync()  # Write the changes to disk
    return settings.value("AudioDirectory")



# =============================================================================
# STEP 1: Create a custom QAbstractListModel to replace the QListWidget.
# =============================================================================
class QuranListModel(QtCore.QAbstractListModel):
    def __init__(self, results=None, parent=None):
        super().__init__(parent)
        self.results = results or []
    
    def rowCount(self, parent=QtCore.QModelIndex()):
        return len(self.results)
    
    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        result = self.results[index.row()]
        if role == Qt.DisplayRole:
            return result.get('text_uthmani', '')
        elif role == Qt.UserRole:
            return result
        return None

    def updateResults(self, results):
        self.beginResetModel()
        self.results = results
        self.endResetModel()

# =============================================================================
# STEP 2: Create a worker thread for asynchronous search operations.
# =============================================================================
class SearchWorker(QtCore.QThread):
    results_ready = QtCore.pyqtSignal(list)
    error_occurred = QtCore.pyqtSignal(str)

    def __init__(self, search_engine, method, query, parent=None):
        super().__init__(parent)
        self.search_engine = search_engine
        self.method = method
        self.query = query

    def run(self):
        try:
            if self.method == "Text":
                results = self.search_engine.search_verses(self.query)
            elif self.method == "Surah":
                if self.query.isdigit():
                    results = self.search_engine.search_by_surah(int(self.query))
                else:
                    results = []
            elif self.method == "Surah FirstAyah LastAyah":
                parts = [int(p) for p in self.query.split()]
                if len(parts) == 2:
                    results = self.search_engine.search_by_surah_ayah(parts[0], parts[1])
                elif len(parts) == 3:
                    results = self.search_engine.search_by_surah_ayah(parts[0], parts[1], parts[2])
                else:
                    results = []
            else:
                results = []
            self.results_ready.emit(results)
        except Exception as e:
            logging.exception("Error during search")
            self.error_occurred.emit(str(e))

# =============================================================================
# STEP 3: Retain (or slightly modify) the SearchLineEdit, QuranDelegate, and DetailView.
# =============================================================================
class SearchLineEdit(QtWidgets.QLineEdit):
    """A QLineEdit that supports navigating through search history."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.history = []
        self.history_index = -1

    def keyPressEvent(self, event):
        if event.key() == QtCore.Qt.Key_Up:
            if self.history:
                if self.history_index == -1:
                    self.history_index = len(self.history) - 1
                elif self.history_index > 0:
                    self.history_index -= 1
                self.setText(self.history[self.history_index])
        elif event.key() == QtCore.Qt.Key_Down:
            if self.history and self.history_index != -1:
                if self.history_index < len(self.history) - 1:
                    self.history_index += 1
                    self.setText(self.history[self.history_index])
                else:
                    self.history_index = -1
                    self.clear()
        else:
            super().keyPressEvent(event)

class QuranDelegate(QtWidgets.QStyledItemDelegate):
    """Custom delegate for rendering Quran verses with proper RTL support."""
    def __init__(self, version="uthmani", parent=None):
        super().__init__(parent)
        self.version = version
        self.query = ""
        self.highlight_color = "#4CAF5050"
        
    def update_version(self, version):
        self.version = version
        if self.parent():
            self.parent().viewport().update()

    def paint(self, painter, option, index):
        painter.save()
        doc = QtGui.QTextDocument()
        doc.setDocumentMargin(2)
        result = index.data(Qt.UserRole)
        text = self._format_text(result, self.version)
        doc.setHtml(text)
        text_option = doc.defaultTextOption()
        text_option.setTextDirection(Qt.RightToLeft)
        text_option.setAlignment(Qt.AlignRight)
        doc.setDefaultTextOption(text_option)
        doc.setTextWidth(option.rect.width() - 20)
        
        if option.state & QtWidgets.QStyle.State_Selected:
            painter.fillRect(option.rect, option.palette.highlight())
            doc.setDefaultStyleSheet(f"body {{ color: {option.palette.highlightedText().color().name()}; }}")
        
        painter.translate(option.rect.topLeft())
        doc.drawContents(painter)
        painter.restore()

    def _format_text(self, result, version):
        text = result.get(f"text_{version}", "")
        return f"""
            <div dir="rtl" style="text-align:left;">
                <div style="font-family: 'Amiri'; font-size: 16pt; margin: 5px;">
                    {text}
                    <span style="color: #006400; font-size: 14pt;">
                        ({result.get('surah', '')}-{result.get('chapter', '')} {result.get('ayah', '')})
                    </span>
                </div>
            </div>
            """

    def sizeHint(self, option, index):
        result = index.data(Qt.UserRole)
        doc = QtGui.QTextDocument()
        doc.setHtml(self._format_text(result, self.version))
        doc.setTextWidth(option.rect.width() - 20)
        return QSize(int(doc.idealWidth()) + 20, int(doc.size().height()))

class DetailView(QtWidgets.QWidget):
    """Detailed view for showing verse context."""
    backRequested = QtCore.pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.initUI()

    def initUI(self):
        layout = QtWidgets.QVBoxLayout(self)
        self.back_button = QtWidgets.QPushButton("← Back to Results")
        self.back_button.clicked.connect(self.backRequested.emit)
        self.text_browser = QtWidgets.QTextBrowser()
        self.text_browser.setOpenExternalLinks(True)
        layout.addWidget(self.back_button)
        layout.addWidget(self.text_browser)

    def display_ayah(self, result, search_engine, version):
        verses = search_engine.get_ayah_with_context(result['surah'], result['ayah'])
        html = []
        for verse in verses:
            text = verse.get(f'text_{version}', "")
            current_class = "current-ayah" if verse['ayah'] == result['ayah'] else ""
            html.append(f"""
            <div class="verse {current_class}" dir="rtl" style="text-align:left;">
                <div style="font-family: 'Amiri'; font-size: 16pt; margin: 5px;">
                    {text}
                    <span style="color: #006400; font-size: 14pt;">
                        ({verse.get('surah', '')}-{verse.get('chapter', '')} {verse.get('ayah', '')})
                    </span>
                </div>
            </div>
            """)
        self.text_browser.setHtml(f"""
        <html>
            <style>
                body {{ background: {self.palette().window().color().name()}; }}
            </style>
            {''.join(html)}
        </html>
        """)

# =============================================================================
# STEP 4: Main application window with all improvements.
# =============================================================================
class QuranBrowser(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        icon_path = os.path.join(os.path.dirname(__file__), "icon.png")
        self.setWindowIcon(QtGui.QIcon(icon_path))
        self.search_engine = QuranSearch()
        self.current_detail_result = None  
        self.current_surah = 0
        self.current_start_ayah = 0
        self.sequence_files = []
        self.current_sequence_index = 0

        self.settings = QtCore.QSettings("MOSAID", "QuranSearch")
        self.init_ui()
        self.setup_connections()
        self.setup_menu()
        self.setup_shortcuts()
        self.load_settings()
        self.trigger_initial_search()
        self.player = QMediaPlayer()  # For audio playback
        self.player.mediaStatusChanged.connect(self.on_media_status_changed)


    def init_ui(self):
        # Create search bar widgets.
        self.search_input = SearchLineEdit()
        self.version_combo = QtWidgets.QComboBox()
        self.version_combo.addItems(["Show Uthmani", "Show Simplified"])
        self.search_method_combo = QtWidgets.QComboBox()
        self.search_method_combo.addItems(["Text", "Surah", "Surah FirstAyah LastAyah"])
        self.surah_combo = QtWidgets.QComboBox()
        self.surah_combo.addItems(self.search_engine.get_chapters_names())
        self.clear_button = QtWidgets.QPushButton("Clear")

        # Build the search bar as a compact widget.
        search_bar = QtWidgets.QWidget()
        search_layout = QtWidgets.QHBoxLayout(search_bar)
        search_layout.setContentsMargins(5, 5, 5, 5)
        search_layout.setSpacing(10)
        search_layout.addWidget(QtWidgets.QLabel("Surah:"))
        search_layout.addWidget(self.surah_combo)
        search_layout.addWidget(QtWidgets.QLabel("Version:"))
        search_layout.addWidget(self.version_combo)
        search_layout.addWidget(QtWidgets.QLabel("Method:"))
        search_layout.addWidget(self.search_method_combo)
        search_layout.addWidget(self.search_input)
        search_layout.addWidget(self.clear_button)

        # Ensure the search bar does not expand vertically.
        search_bar.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        search_bar.setMaximumHeight(50)

        # Use QVBoxLayout to stack search bar and results view.
        central = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(central)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)
        layout.addWidget(search_bar)  # Compact search bar at the top.

        # Create the results and detail views in a QSplitter.
        self.splitter = QtWidgets.QSplitter(Qt.Horizontal)
        self.results_view = QtWidgets.QListView()
        self.model = QuranListModel()
        self.results_view.setModel(self.model)
        self.delegate = QuranDelegate(parent=self.results_view)
        self.results_view.setItemDelegate(self.delegate)
        self.results_view.setUniformItemSizes(False)
        self.results_view.activated.connect(self.show_detail_view)
        self.results_view.setWordWrap(True)
        self.results_view.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)


        self.detail_view = DetailView()
        self.splitter.addWidget(self.results_view)
        self.splitter.addWidget(self.detail_view)

        # Set stretch factors to maximize results view space.
        self.splitter.setStretchFactor(0, 4)
        self.splitter.setStretchFactor(1, 1)

        # Initially hide the detail view.
        self.detail_view.hide()

        # Add the splitter to the main layout.
        layout.addWidget(self.splitter)

        # Status bar with result count and shortcuts.
        self.status_bar = QtWidgets.QStatusBar()
        self.setStatusBar(self.status_bar)

        # Left widget: result count (no stretch)
        self.result_count = QtWidgets.QLabel()
        self.status_bar.addWidget(self.result_count, 0)

        # Center widget: copyright message (stretch factor 1)
        center_label = QtWidgets.QLabel("© 2025 MOSAID, <a href='https://mosaid.xyz'>https://mosaid.xyz</a>")
        center_label.setAlignment(QtCore.Qt.AlignCenter)
        center_label.setTextFormat(QtCore.Qt.RichText)
        center_label.setTextInteractionFlags(QtCore.Qt.TextBrowserInteraction)
        center_label.setOpenExternalLinks(True)
        self.status_bar.addWidget(center_label, 1)

        # Right widget: shortcuts info (no stretch)
        shortcuts = QtWidgets.QLabel("Help: Ctrl+F")
        shortcuts.setAlignment(QtCore.Qt.AlignRight)
        self.status_bar.addWidget(shortcuts, 0)


        # Set the central widget.
        self.setCentralWidget(central)
        # self.setWindowTitle("Quran Search")
        # self.resize(1200, 500)


    def setup_connections(self):
        self.search_input.returnPressed.connect(self.search)
        self.version_combo.currentIndexChanged.connect(self.handle_version_change)
        self.search_method_combo.currentIndexChanged.connect(self.search)
        self.surah_combo.currentIndexChanged.connect(self.handle_surah_selection)
        self.clear_button.clicked.connect(self.clear_search)
        self.detail_view.backRequested.connect(self.show_results_view)
        self.results_view.doubleClicked.connect(self.show_detail_view)

    def setup_shortcuts(self):
        QtWidgets.QShortcut(QtGui.QKeySequence("Space"), self, activated=self.play_current)
        QtWidgets.QShortcut(QtGui.QKeySequence("Escape"), self, activated=self.toggle_version)
        QtWidgets.QShortcut(QtGui.QKeySequence("Backspace"), self, activated=self.show_results_view)
        QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+F"), self, activated=self.input_focus)
        QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+D"), self, activated=self.toggle_theme)
        QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+P"), self, activated=lambda: self.play_current(count=6))
        QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+S"), self, activated=self.stop_playback)
        QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+A"), self.results_view, activated=self.play_current_surah)
        QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+B"), self, activated=self.backto_current_surah)
        QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+H"), self, activated=self.show_help_dialog)
        QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+J"), self, activated=self.load_surah_from_current_ayah)
        QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+K"), self, activated=self.load_surah_from_current_playback)


    def showMessage(self, message, timeout=7000):
        # Save the current stylesheet.
        original_style = self.status_bar.styleSheet()
        # Set the error background.
        self.status_bar.setStyleSheet("QStatusBar { background-color: red; }")
        self.status_bar.showMessage(message, timeout)
        # After 'timeout' milliseconds, revert to the original style.
        QtCore.QTimer.singleShot(timeout, lambda: self.status_bar.setStyleSheet(original_style))


    def setup_menu(self):
        menu = self.menuBar().addMenu("&Menu")
        self.theme_action = QtWidgets.QAction("Dark Mode", self, checkable=True)
        self.theme_action.toggled.connect(self.update_theme_style)
        menu.addAction(self.theme_action)
        about_action = QtWidgets.QAction("About", self)
        about_action.triggered.connect(self.about_dialog)
        menu.addAction(about_action)
        # New action: Set Audio Directory.
        audio_dir_action = QtWidgets.QAction("Set Audio Directory", self)
        audio_dir_action.triggered.connect(self.choose_audio_directory)
        menu.addAction(audio_dir_action)
        # Add Help action with Ctrl+H shortcut.
        help_action = QtWidgets.QAction("Help", self)
        help_action.triggered.connect(self.show_help_dialog)
        menu.addAction(help_action)

    def load_settings(self):
        geometry = self.settings.value("geometry")
        if geometry:
            self.restoreGeometry(geometry)
        window_state = self.settings.value("windowState")
        if window_state:
            self.restoreState(window_state)
        dark_mode = self.settings.value("darkMode", False, type=bool)
        self.theme_action.setChecked(dark_mode)
        version_index = self.settings.value("versionIndex", 0, type=int)
        self.version_combo.setCurrentIndex(version_index)
        surah_index = self.settings.value("surahIndex", 0, type=int)
        self.surah_combo.setCurrentIndex(surah_index)

    def choose_audio_directory(self):
        """
        Open a dialog to choose an audio directory.
        If a directory is chosen, update the INI file with the new value.
        """
        # Get the current audio directory from the INI file.
        current_dir = get_audio_directory()
        
        # Open a directory chooser dialog.
        chosen_dir = QtWidgets.QFileDialog.getExistingDirectory(
            self,
            "Select Audio Directory",
            current_dir
        )
        
        # If the user selected a directory, update the INI file.
        if chosen_dir:
            config_file = os.path.join(os.path.expanduser("~"), ".quran_audio.ini")
            settings = QtCore.QSettings(config_file, QtCore.QSettings.IniFormat)
            settings.setValue("AudioDirectory", chosen_dir)
            settings.sync()  # Write changes immediately.
            self.status_bar.showMessage(f"Audio directory set to: {chosen_dir}", 3000)


    def closeEvent(self, event):
        self.settings.setValue("geometry", self.saveGeometry())
        self.settings.setValue("windowState", self.saveState())
        self.settings.setValue("darkMode", self.theme_action.isChecked())
        self.settings.setValue("versionIndex", self.version_combo.currentIndex())
        self.settings.setValue("surahIndex", self.surah_combo.currentIndex())
        event.accept()

    def trigger_initial_search(self):
        QtCore.QTimer.singleShot(100, lambda: self.handle_surah_selection(self.surah_combo.currentIndex()))

    def handle_version_change(self):
        version = self.get_current_version()
        self.delegate.update_version(version)
        self.results_view.viewport().update()
        if self.detail_view.isVisible() and self.current_detail_result:
            self.detail_view.display_ayah(self.current_detail_result, self.search_engine, version)

    def get_current_version(self):
        return "uthmani" if "Uthmani" in self.version_combo.currentText() else "simplified"

    def handle_surah_selection(self, index):
        if index < 0:
            return
        surah = index + 1
        try:
            results = self.search_engine.search_by_surah(surah)
            self.update_results(results, f"Surah {surah} (Automatic Selection)")
        except Exception as e:
            logging.exception("Error during surah selection")
            self.showMessage("Error loading surah", 3000)
        self.show_results_view()

    def load_surah_from_current_ayah(self, surah=None, selected_ayah=None):
        """
        Load the full surah for a given surah and ayah.
        If surah and selected_ayah are not provided, use the currently selected verse.
        This does not affect playback. (Use Ctrl+A to play the surah.)
        """
        # If no parameters provided, use the current selection.
        if surah is None or selected_ayah is None:
            index = self.results_view.currentIndex()
            if not index.isValid():
                self.showMessage("No verse selected", 2000)
                return

            result = self.model.data(index, Qt.UserRole)
            try:
                surah = int(result.get('surah'))
                selected_ayah = int(result.get('ayah'))
            except Exception as e:
                self.showMessage("Invalid surah/ayah information", 3000)
                return

        # Load the full surah using your search engine.
        try:
            results = self.search_engine.search_by_surah(surah)
            self.update_results(results, f"Surah {surah} (Automatic Selection)")
        except Exception as e:
            logging.exception("Error loading surah")
            self.showMessage("Error loading surah", 3000)
            return

        # Show the results view.
        self.show_results_view()

        # Scroll to the specified ayah.
        self._scroll_to_ayah(surah, selected_ayah)


    def load_surah_from_current_playback(self):
        """
        If a playback sequence is active, use its current surah and the
        last played (or currently playing) ayah to load that surah and scroll to it.
        Bind this method to Ctrl+K.
        """
        if self.current_surah is None:
            self.showMessage("No current playback info", 2000)
            return

        # Calculate the current ayah from the playback sequence.
        # For example, if current_sequence_index is 0 then nothing has played yet,
        # so we default to current_start_ayah; otherwise, use (current_start_ayah + current_sequence_index - 1).
        current_ayah = self.current_start_ayah + max(self.current_sequence_index - 1, 0)
        self.load_surah_from_current_ayah(surah=self.current_surah, selected_ayah=current_ayah)



    def search(self):
        if self.detail_view.isVisible():
            self.show_results_view()
            
        query = self.search_input.text().strip()
        method = self.search_method_combo.currentText()
        if not query and method == "Text":
            self.showMessage("Please enter a search query", 3000)
            return
        self.status_bar.showMessage("Searching...", 2000)

        if (method == "Surah" and query.isdigit()) or method == "Surah FirstAyah LastAyah":
            try:
                if method == "Surah":
                    surah_num = int(query)
                else:
                    parts = [int(p) for p in query.split()]
                    surah_num = parts[0] if parts else None
                if surah_num is not None:
                    self.current_surah = surah_num
                    self.surah_combo.setCurrentIndex(surah_num - 1)  # Adjust for 0-based index
            except ValueError:
                # Conversion failed; do nothing.
                pass

        # Start the search in a background thread.
        self.search_worker = SearchWorker(self.search_engine, method, query)
        self.search_worker.results_ready.connect(lambda results: self.update_results(results, query))
        self.search_worker.error_occurred.connect(lambda error: self.showMessage(f"Search error: {error}", 3000))
        self.search_worker.start()

    def update_results(self, results, query):
        self.model.updateResults(results)
        self.result_count.setText(f"Found {len(results)} results")
        if results:
            self.results_view.setFocus()

    def show_detail_view(self, index):
        if isinstance(index, QtCore.QModelIndex):
            result = self.model.data(index, Qt.UserRole)
        else:
            result = None
        if result:
            self.current_detail_result = result
            version = self.get_current_version()
            self.detail_view.display_ayah(result, self.search_engine, version)
            self.detail_view.show()
            self.results_view.hide()

    def input_focus(self):
        self.search_input.setFocus()
        self.search_input.selectAll()

    def show_results_view(self):
        self.detail_view.hide()
        self.results_view.show()
        self.results_view.setFocus()

    def play_current(self, surah=None, ayah=None, count=1):
        """
        Play a single audio file or a sequence of files.
        
        If surah and ayah are provided, they are used directly; otherwise,
        the currently selected verse in the results view is used.
        
        If count == 1, play a single file.
        If count > 1, build a list of files and play them sequentially.
        Audio files are expected to be named with padded numbers (e.g., "001001.mp3").
        """
        # If surah/ayah are not provided, use the currently selected item.
        if surah is None or ayah is None:
            index = self.results_view.currentIndex()
            if not index.isValid():
                self.showMessage("No verse selected", 7000)
                return
            result = self.model.data(index, Qt.UserRole)
            try:
                surah = int(result.get('surah'))
                ayah = int(result.get('ayah'))
            except Exception as e:
                self.showMessage("Invalid verse data", 2000)
                return

        # Retrieve the audio directory from the INI file.
        audio_dir = get_audio_directory()
        
        # Single-file playback:
        if count == 1:
            audio_file = os.path.join(audio_dir, f"{int(surah):03d}{int(ayah):03d}.mp3")
            if os.path.exists(audio_file):
                url = QUrl.fromLocalFile(os.path.abspath(audio_file))
                self.player.setMedia(QMediaContent(url))
                self.player.play()
                self.status_bar.showMessage(f"Playing audio for Surah {surah}, Ayah {ayah}", 2000)
            else:
                self.showMessage("Audio file not found", 3000)
            return

        # For sequence playback, store the surah and starting ayah.
        self.current_surah = int(surah)
        self.current_start_ayah = int(ayah)
        self.sequence_files = []
        
        # Build a list of files for 'count' files (starting from the provided ayah).
        for offset in range(count):
            current_ayah = self.current_start_ayah + offset
            file_path = os.path.join(audio_dir, f"{self.current_surah:03d}{current_ayah:03d}.mp3")
            if os.path.exists(file_path):
                self.sequence_files.append(os.path.abspath(file_path))
            else:
                # Optionally, notify that a file was not found and break out.
                self.showMessage(f"Audio file not found: {file_path}", 2000)
                break

        if not self.sequence_files:
            self.showMessage("No audio files found for sequence", 3000)
            return

        # Initialize sequence index and start playback.
        self.current_sequence_index = 0
        self.play_next_file()


    def play_next_file(self):
        """
        Play the next file in the current sequence (if any) and update the UI selection.
        When the current surah finishes, automatically load the next surah (or surah 1 if current is 114)
        and begin playback from ayah 1.
        """
        if self.current_sequence_index < len(self.sequence_files):
            # Continue playing the current surah.
            file_path = self.sequence_files[self.current_sequence_index]
            url = QUrl.fromLocalFile(file_path)
            self.player.setMedia(QMediaContent(url))
            self.player.play()
            self.status_bar.showMessage("Playing: audio", 2000)

            # Calculate the current ayah being played.
            current_ayah = self.current_start_ayah + self.current_sequence_index
            if self.results_view.isVisible():
                self._scroll_to_ayah(self.current_surah, current_ayah)
            self.current_sequence_index += 1
        else:
            # End of current surah reached: increment surah (wrap around if needed).
            if self.current_surah < 114:
                self.current_surah += 1
            else:
                self.current_surah = 1  # Wrap around to surah 1

            self.current_start_ayah = 1  # New surah always starts at ayah 1

            # Build new sequence for the next surah.
            audio_dir = get_audio_directory()
            new_sequence_files = []
            for ayah in range(1, 300):  # A safe upper bound for number of ayahs.
                file_path = os.path.join(audio_dir, f"{self.current_surah:03d}{ayah:03d}.mp3")
                if os.path.exists(file_path):
                    new_sequence_files.append(os.path.abspath(file_path))
                else:
                    break

            if new_sequence_files:
                self.handle_surah_selection(self.current_surah-1)
                self.surah_combo.setCurrentIndex(self.current_surah - 1)
                self.sequence_files = new_sequence_files
                self.current_sequence_index = 0
                self.status_bar.showMessage(f"Moving to surah {self.current_surah}", 5000)
                self.play_next_file()  # Start playback of the new surah.
            else:
                self.status_bar.showMessage(f"No audio files found for surah {self.current_surah}. Playback finished.", 2000)
                self.sequence_files = []
                self.current_sequence_index = 0



    def on_media_status_changed(self, status):
        """
        Monitor the media player's status. When the current media finishes,
        trigger playing the next file in the sequence.
        """
        from PyQt5.QtMultimedia import QMediaPlayer
        if status == QMediaPlayer.EndOfMedia:
            # Delay a bit to ensure the player is ready for the next file.
            QTimer.singleShot(100, self.play_next_file)

    def _scroll_to_ayah(self, surah, ayah):
        """
        Search the model for a result matching the given surah and ayah.
        If found, select and scroll to that item.
        Returns True if a match was found, otherwise False.
        """
        model = self.model
        found = False
        for row in range(model.rowCount()):
            index = model.index(row, 0)
            result = model.data(index, Qt.UserRole)
            if result:
                try:
                    res_surah = int(result.get('surah'))
                    res_ayah = int(result.get('ayah'))
                except Exception:
                    continue

                if res_surah == surah and res_ayah == ayah:
                    self.results_view.setCurrentIndex(index)
                    self.results_view.scrollTo(index, QtWidgets.QAbstractItemView.PositionAtCenter)
                    found = True
                    break
        return found


    def stop_playback(self):
        """Stop any current audio playback."""
        self.player.stop()
        self.status_bar.showMessage("Playback stopped", 2000)

    def backto_current_surah(self):
        self.handle_surah_selection(self.current_surah-1)
        current_ayah = self.current_start_ayah + self.current_sequence_index -1
        self._scroll_to_ayah(self.current_surah,current_ayah)

    def play_current_surah(self):
        """
        Play the entire surah of the currently selected verse.
        This method works only in the results view.
        It builds a sequence from ayah 1 upward until no file is found,
        then starts playback at the currently selected ayah.
        """
        # Ensure we are in results view.
        if not self.results_view.isVisible():
            self.showMessage("Switch to results view to play current surah", 2000)
            return

        index = self.results_view.currentIndex()
        if not index.isValid():
            self.showMessage("No verse selected", 2000)
            return

        result = self.model.data(index, Qt.UserRole)
        try:
            surah = int(result.get('surah'))
            selected_ayah = int(result.get('ayah'))
        except Exception as e:
            self.showMessage("Invalid surah or ayah information", 2000)
            return

        # Retrieve the audio directory from the INI file.
        audio_dir = get_audio_directory()
        sequence_files = []

        # Loop through possible ayahs (from 1 to 300 is a safe upper bound).
        for ayah in range(1, 300):
            file_path = os.path.join(audio_dir, f"{surah:03d}{ayah:03d}.mp3")
            if os.path.exists(file_path):
                sequence_files.append(os.path.abspath(file_path))
            else:
                # Stop adding files when an ayah is missing, assuming that's the end.
                break

        if not sequence_files:
            self.showMessage("No audio files found for current surah", 3000)
            return

        # Store the sequence and initialize the index.
        self.current_surah = surah
        self.sequence_files = sequence_files
        self.current_start_ayah = 1  # Our sequence is built from ayah 1.
        # Set the current sequence index to the selected ayah (adjusted for 0-based indexing).
        self.current_sequence_index = selected_ayah -1

        # Sanity check: if the selected ayah is out of range, default to 0.
        if self.current_sequence_index < 0 or self.current_sequence_index >= len(sequence_files):
            self.current_sequence_index = 0

        self.play_next_file()  # This method will chain playback for the sequence.


    def toggle_version(self):
        current = self.version_combo.currentIndex()
        new_index = 0 if current else 1
        self.version_combo.setCurrentIndex(new_index)
        self.handle_version_change()

    def toggle_theme(self):
        """
        Toggle between dark and light themes.
        This method inverts the current theme by toggling the theme_action's checked state,
        then updates the UI style by calling update_theme_style.
        """
        # Invert the current theme state.
        dark = not self.theme_action.isChecked()
        # Update the theme action's checked state.
        self.theme_action.setChecked(dark)
        # Apply the new theme.
        self.update_theme_style(dark)


    def update_theme_style(self, dark):
        if dark:
            self.setStyleSheet("""
                QWidget {
                    background: #333333;
                    color: #FFFFFF;
                }
                QListView {
                    background: #1e1e1e;
                }
                QLineEdit {
                    background: #222222;
                }
            """)
        else:
            self.setStyleSheet("")
        self.settings.setValue("darkMode", dark)

    def clear_search(self):
        self.search_input.clear()
        self.model.updateResults([])
        self.result_count.clear()
        self.surah_combo.setCurrentIndex(0)

    def about_dialog(self):
        QtWidgets.QMessageBox.about(
            self,
            "About Quran Search",
            """<b>Quran Search</b> v1.0<br><br>
            Developed by MOSAID<br>
            © 2025 All rights reserved<br><br>
            Quran text from Tanzil.net<br>
            GPL v3 Licensed<br><br>
            <a href="https://mosaid.xyz">https://mosaid.xyz</a>"""
        )

    def show_help_dialog(self):
        help_text = (
            "<h2>Quran Search Help</h2>"
            "<p>This application allows you to search and play audio for Quran verses. Features include:</p>"
            "<ul>"
            "<li><b>Surah Selection:</b> Use the dropdown to select a surah. The results list will display all verses of the selected surah.</li>"
            "<li><b>Search Methods:</b> Choose between"
                "<ul>"
                "<li><b>Text</b>: Input arabic word/words to search the quran text</li>"
                "<li><b>Surah search</b>: enter a surah number in the input field then Enter</li>"
                "<li><b>Surah FirstAyah LastAyah</b>: use numbers eg, 2 255 or 2 255 280 to directly load ayat</li>"
                "</ul>"
            "<li><b>Ayah context:</b> Double click or Enter on a selected ayah, will show its context; 5 verses before\
                and 5 after it, in text format that you can copy</li>"
            "<li><b>Audio Playback:</b> with auto scroll current playing verse"
                "<ul>"
                "<li><b>Space:</b> Play the audio for the currently selected verse.</li>"
                "<li><b>Ctrl+P:</b> Play the current ayah and the next five ayahs sequentially.</li>"
                "<li><b>Ctrl+S:</b> Stop playback.</li>"
                "<li><b>Ctrl+A:</b> (When in results view) Play the entire current surah. starting from selected verse</li>"
                "<li><b>Ctrl+K:</b> (When playing a sequence) Jump back to the current playing surah - ayah </li>"
                "</ul>"
            "</li>"
            "<li><b>UI Shortcuts:</b> "
                "<ul>"
                "<li><b>Ctrl+F:</b> Focus the search input.</li>"
                "<li><b>Ctrl+D:</b> Toggle between dark and light themes.</li>"
                "<li><b>Backspace:</b> Return from detail view to results view.</li>"
                "<li><b>Escape:</b> Toggle the text version, uthmani and simplified arabic.</li>"
                "<li><b>Ctrl+J:</b> Load surah from current Ayah.</li>"
                "<li><b>Ctrl+B:</b> Go back to current surah.</li>"
                "</ul>"
            "</li>"
            "<li><b>Audio Directory:</b> Use the 'Set Audio Directory' menu item to change where audio files are loaded from.\
                Files must be named like 002001.mp3.</li>"
            "</ul>"
            "<p syle='padding-left:10px;'>If you need further assistance, please visit our website : <a href='https://mosaid.xyz'>https://mosaid.xyz</a>.</p>"
        )
        # Create a custom dialog.
        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle("Help")
        dialog.setModal(True)
        dialog.setFixedSize(680, 500)  
        # Set up a vertical layout.
        layout = QtWidgets.QVBoxLayout(dialog)
        
        # Use a QLabel to display the help text.
        label = QtWidgets.QLabel(help_text, dialog)
        label.setWordWrap(True)
        layout.addWidget(label)
        
        # Add an OK button.
        button_box = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok)
        button_box.accepted.connect(dialog.accept)
        layout.addWidget(button_box)
        
        # Adjust the dialog's size.
        dialog.adjustSize()

        # Center the dialog relative to the parent window.
        parent_geom = self.frameGeometry()
        dialog_geom = dialog.frameGeometry()
        dialog_geom.moveCenter(parent_geom.center())
        dialog.move(dialog_geom.topLeft())
        
        dialog.exec_()

if __name__ == "__main__":
    from PyQt5.QtGui import QGuiApplication
    app = QtWidgets.QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setApplicationName("QuranSearch")
    app.setOrganizationName("MOSAID")
    window = QuranBrowser()
    window.setWindowTitle("Quran Search")  # Proper window title
    window.setWindowRole("QuranSearch")
    window.show()
    QGuiApplication.instance().setApplicationDisplayName("QuranSearch")
    sys.exit(app.exec_())
