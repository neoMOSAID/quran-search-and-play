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
import csv
import json
import logging
from datetime import datetime

from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtCore import QUrl, QSize, Qt, QSettings, QTimer
from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent
from PyQt5.QtCore import QStandardPaths, QSettings
from search import QuranSearch

import sqlite3
from pathlib import Path

# Configure logging for debugging and error reporting.
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')


class NotesManager:
    def __init__(self):
        # Get the writable location for application data
        app_data_path = Path(QStandardPaths.writableLocation(QStandardPaths.AppDataLocation))
        # Ensure the directory exists
        app_data_path.mkdir(parents=True, exist_ok=True)
        self.db_path = app_data_path / "quran_notes.db"
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS notes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    surah INTEGER NOT NULL,
                    ayah INTEGER NOT NULL,
                    content TEXT NOT NULL,
                    created TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_surah_ayah ON notes (surah, ayah)")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS courses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    items TEXT NOT NULL -- JSON-encoded list of items
                )
            """)

    def get_notes(self, surah, ayah):
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.execute("""
                SELECT id, content, created
                FROM notes
                WHERE surah=? AND ayah=?
                ORDER BY created DESC
            """, (surah, ayah))
            return [{"id": row[0], "content": row[1], "created": row[2]}
                    for row in cursor.fetchall()]

    def add_note(self, surah, ayah, content):
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.execute("""
                INSERT INTO notes (surah, ayah, content)
                VALUES (?, ?, ?)
            """, (surah, ayah, content))
            return cursor.lastrowid

    def update_note(self, note_id, new_content):
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute("""
                UPDATE notes
                SET content = ?, created = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (new_content, note_id))

    def delete_note(self, note_id):
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute("DELETE FROM notes WHERE id = ?", (note_id,))

    def delete_all_notes(self, surah, ayah):
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute("DELETE FROM notes WHERE surah=? AND ayah=?", (surah, ayah))

    def export_to_csv(self, file_path):
        """Exports all notes to a CSV file."""
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                cursor = conn.execute("""
                    SELECT surah, ayah, content, created
                    FROM notes
                    ORDER BY surah, ayah, created
                """)
                notes = cursor.fetchall()

            with open(file_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['Surah', 'Ayah', 'Content', 'Created'])
                writer.writerows(notes)
            return True
        except Exception as e:
            logging.error(f"Export error: {e}")
            raise

    def import_from_csv(self, file_path):
        """Imports notes from a CSV file, skipping duplicates."""
        imported = 0
        duplicates = 0
        errors = 0
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                header = next(reader, None)
                if header != ['Surah', 'Ayah', 'Content', 'Created']:
                    raise ValueError("Invalid CSV header. Expected: Surah, Ayah, Content, Created")

                for row in reader:
                    if len(row) < 4:
                        errors += 1
                        continue
                    try:
                        surah = int(row[0])
                        ayah = int(row[1])
                        content = row[2].strip()
                        # created is ignored, using current timestamp
                    except (ValueError, IndexError) as e:
                        errors += 1
                        continue

                    if self.note_exists(surah, ayah, content):
                        duplicates += 1
                    else:
                        self.add_note(surah, ayah, content)
                        imported += 1
            return (imported, duplicates, errors)
        except Exception as e:
            logging.error(f"Import error: {e}")
            raise

    def note_exists(self, surah, ayah, content):
        """Checks if a note with the same surah, ayah, and content exists."""
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.execute("""
                SELECT COUNT(*)
                FROM notes
                WHERE surah=? AND ayah=? AND content=?
            """, (surah, ayah, content))
            return cursor.fetchone()[0] > 0
        
    def has_note(self, surah, ayah):
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.execute(
                "SELECT COUNT(*) FROM notes WHERE surah=? AND ayah=?",
                (surah, ayah)
            )
            count = cursor.fetchone()[0]
            return count > 0
            
    def save_course(self, course_id, title, items):
        items_json = json.dumps(items)
        with sqlite3.connect(str(self.db_path)) as conn:
            if course_id:
                conn.execute("UPDATE courses SET title = ?, items = ? WHERE id = ?", (title, items_json, course_id))
                return course_id
            else:
                cursor = conn.execute("INSERT INTO courses (title, items) VALUES (?, ?)", (title, items_json))
                return cursor.lastrowid

    def delete_course(self, course_id):
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute("DELETE FROM courses WHERE id = ?", (course_id,))

    def get_new_course(self):
        return None, {"title": "", "items": []}

    def get_previous_course(self, current_id):
        with sqlite3.connect(str(self.db_path)) as conn:
            if current_id is None:
                # Return the last (most recent) course
                cursor = conn.execute("SELECT id, title, items FROM courses ORDER BY id DESC LIMIT 1")
            else:
                cursor = conn.execute(
                    "SELECT id, title, items FROM courses WHERE id < ? ORDER BY id DESC LIMIT 1",
                    (current_id,))
            row = cursor.fetchone()
            if row:
                return row[0], {"title": row[1], "items": json.loads(row[2])}
        return self.get_new_course()


    def get_next_course(self, current_id):
        with sqlite3.connect(str(self.db_path)) as conn:
            if current_id is None:
                # Return the first (oldest) course
                cursor = conn.execute("SELECT id, title, items FROM courses ORDER BY id ASC LIMIT 1")
            else:
                cursor = conn.execute(
                    "SELECT id, title, items FROM courses WHERE id > ? ORDER BY id ASC LIMIT 1",
                    (current_id,))
            row = cursor.fetchone()
            if row:
                return row[0], {"title": row[1], "items": json.loads(row[2])}
        return self.get_new_course()



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
    loading_complete = QtCore.pyqtSignal()
    def __init__(self, results=None, parent=None):
        super().__init__(parent)
        self.results = results or []
        self._displayed_results = 0

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid() or index.row() >= len(self.results):
            return None

        result = self.results[index.row()]

        if role == Qt.DisplayRole:
            return result.get('text_uthmani', '')
        elif role == Qt.UserRole:
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
        remaining = len(self.results) - self._displayed_results
        if remaining > 0:
            batch_size = min(50, remaining)
            self.beginInsertRows(QtCore.QModelIndex(),
                               self._displayed_results,
                               self._displayed_results + batch_size - 1)
            self._displayed_results += batch_size
            self.endInsertRows()

            if self._displayed_results < len(self.results):
                QtCore.QTimer.singleShot(50, self.load_remaining_results)
            else:
                self.loading_complete.emit()  # Emit signal when done


# =============================================================================
# STEP 2: Create a worker thread for asynchronous search operations.
# =============================================================================
class SearchWorker(QtCore.QThread):
    results_ready = QtCore.pyqtSignal(list)
    error_occurred = QtCore.pyqtSignal(str)

    def __init__(self, search_engine, method, query, parent=None):
        super().__init__(parent)
        self.parent = parent  
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

# =============================================================================
# STEP 3
# =============================================================================
class SearchLineEdit(QtWidgets.QLineEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.history_max = 50  # Increased from 20 to 50
        self.init_history()

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

    def select_history_item(self, item):
        self.setText(item.text())
        self.returnPressed.emit()

    def update_history(self, query):
        if query and query not in self.history:
            # Add to beginning and enforce max limit
            self.history.insert(0, query)
            self.history = self.history[:self.history_max]

            # Persist to QSettings
            settings = QtCore.QSettings("MOSAID", "QuranSearch")
            settings.setValue("searchHistory", self.history)

            self.update_history_list()

    def update_history_list(self):
        self.history_list.clear()
        for item in self.history:
            self.history_list.addItem(item)

    #still unused
    def clear_history(self):
        settings = QtCore.QSettings("MOSAID", "QuranSearch")
        settings.remove("searchHistory")
        self.history = []
        self.update_history_list()

    def keyPressEvent(self, event):
        if event.key() in (QtCore.Qt.Key_Up, QtCore.Qt.Key_Down):
            self.handle_history_navigation(event.key())
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
        if not result:  # Add null check
            return ""

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
        if not result:  # Handle null results
            return QSize(0, 0)
        doc = QtGui.QTextDocument()
        doc.setHtml(self._format_text(result, self.version))
        doc.setTextWidth(option.rect.width() - 20)
        return QSize(int(doc.idealWidth()) + 20, int(doc.size().height()))

class DetailView(QtWidgets.QWidget):
    backRequested = QtCore.pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.notes_widget = NotesWidget()
        self.initUI()


    def initUI(self):
        # Split view
        splitter = QtWidgets.QSplitter(Qt.Vertical)

        # Context View
        context_widget = QtWidgets.QWidget()
        context_layout = QtWidgets.QVBoxLayout(context_widget)
        self.back_button = QtWidgets.QPushButton("← Back to Results")
        self.text_browser = QtWidgets.QTextBrowser()
        context_layout.addWidget(self.back_button)
        context_layout.addWidget(self.text_browser)

        # Add widgets to splitter
        splitter.addWidget(context_widget)
        splitter.addWidget(self.notes_widget)
        splitter.setSizes([250, 350])  # Initial sizes

        # Main layout
        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(splitter)

        # Connections
        self.back_button.clicked.connect(self.backRequested.emit)

    def display_ayah(self, result, search_engine, version, is_dark_theme):
        verses = search_engine.get_ayah_with_context(result['surah'], result['ayah'])
        html = []

        # Set colors based on theme
        text_color = "#000000" if is_dark_theme else "#000000"
        link_color = "#90CAF9" if is_dark_theme else "#1565C0"
        bg_color = self.palette().window().color().name()

        for verse in verses:
            text = verse.get(f'text_{version}', "")
            current_class = "current-ayah" if verse['ayah'] == result['ayah'] else ""
            html.append(f"""
            <div class="verse {current_class}" dir="rtl" style="text-align:left;">
                <div style="font-family: 'Amiri';
                            font-size: 16pt;
                            margin: 5px;
                            color: {text_color};">
                    {text}
                    <span style="color: {link_color};
                                font-size: 14pt;
                                text-decoration: none;">
                        ({verse.get('surah', '')}-{verse.get('chapter', '')} {verse.get('ayah', '')})
                    </span>
                </div>
            </div>
            """)

        self.text_browser.setHtml(f"""
        <html>
            <style>
                body {{
                    background: {bg_color};
                    color: {text_color};
                }}
                a {{
                    color: {link_color};
                    text-decoration: none;
                }}
            </style>
            {''.join(html)}
        </html>
        """)

        # Update notes widget
        self.notes_widget.set_ayah(result['surah'], result['ayah'])

class NotesWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.statusBar = lambda: self.window().statusBar()
        self.notes_manager = NotesManager()
        self.current_surah = None
        self.current_ayah = None
        self.current_note_id = None
        self.search_engine = QuranSearch()
        self.init_ui()

    def init_ui(self):
        layout = QtWidgets.QVBoxLayout(self)

        # Toolbar
        toolbar = QtWidgets.QToolBar()
        toolbar_layout = QtWidgets.QHBoxLayout()
        toolbar_layout.setContentsMargins(0, 0, 0, 0)
        toolbar_layout.setSpacing(10)

        self.new_button = QtWidgets.QAction(QtGui.QIcon.fromTheme("document-new"), "New", self)
        self.save_button = QtWidgets.QAction(QtGui.QIcon.fromTheme("document-save"), "Save", self)
        self.delete_button = QtWidgets.QAction(QtGui.QIcon.fromTheme("edit-delete"), "Delete", self)
        toolbar.addAction(self.new_button)
        toolbar.addAction(self.save_button)
        toolbar.addAction(self.delete_button)

        # Spacer to push the label to the right
        spacer = QtWidgets.QWidget()
        spacer.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Preferred)
        toolbar.addWidget(spacer)

        # Add a small label for the notes list
        self.notes_label = QtWidgets.QLabel("تدبر الآية ")
        self.notes_label.setStyleSheet("font-size: 10pt; font-weight: bold; margin-right: 10px;")
        self.notes_label.setAlignment(QtCore.Qt.AlignVCenter)  # Vertically center the label
        toolbar.addWidget(self.notes_label)

        # Split view for notes list and editor
        splitter = QtWidgets.QSplitter(Qt.Horizontal)

        # Notes list
        self.notes_list = QtWidgets.QListWidget()
        self.notes_list.itemSelectionChanged.connect(self.on_note_selected)

        # Set font size and styling
        list_font = self.notes_list.font()
        list_font.setPointSize(12)  # Increased from default 9-10
        self.notes_list.setFont(list_font)

        # Optional: Add padding and set minimum row height
        self.notes_list.setStyleSheet("""
            QListWidget::item {
                padding: 6px;
                border-bottom: 1px solid #ddd;
            }
        """)
        self.notes_list.setMinimumHeight(100)

        # Editor
        self.editor = QtWidgets.QTextEdit()
        self.editor.setPlaceholderText("...أكتب هنا")
        editor_font = self.notes_list.font()
        editor_font.setPointSize(12)  # Increased from default 9-10
        self.editor.setFont(editor_font)

        splitter.addWidget(self.notes_list)
        splitter.addWidget(self.editor)

        # Set initial split ratio (1:3 ratio)
        splitter.setSizes([self.height()//4, self.height()//4*3])

        # Make editor resizing prioritized
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)

        # Ensure proper initial layout
        QtCore.QTimer.singleShot(100, lambda: splitter.setSizes([200, 300]))

        layout.addWidget(toolbar)
        layout.addWidget(splitter)

        # Connections
        self.new_button.triggered.connect(self.new_note)
        self.save_button.triggered.connect(self.save_note)
        self.delete_button.triggered.connect(self.delete_note)

    def set_ayah(self, surah, ayah):
        self.current_surah = surah
        self.current_ayah = ayah
        self.current_note_id = None
        chapter = self.search_engine.get_chapter_name(self.current_surah)
        self.notes_label.setText(f"تدبر الآية {self.current_ayah} من سورة {chapter}")
        self.load_notes()

    def load_notes(self):
        self.notes_list.clear()
        notes = self.notes_manager.get_notes(self.current_surah, self.current_ayah)
        for note in notes:
            # Display first 80 characters as preview
            preview = note['content'][:80]
            if len(note['content']) > 80:
                preview += "..."

            item = QtWidgets.QListWidgetItem(preview)
            item.setData(Qt.UserRole, note)
            self.notes_list.addItem(item)
        self.editor.clear()

    def on_note_selected(self):
        selected = self.notes_list.currentItem()
        if selected:
            note = selected.data(Qt.UserRole)
            self.current_note_id = note['id']
            self.editor.setPlainText(note['content'])

    def new_note(self):
        self.notes_list.clearSelection()
        self.current_note_id = None
        self.editor.clear()
        self.editor.setFocus()

    def save_note(self):
        if not (self.current_surah and self.current_ayah):
            return

        content = self.editor.toPlainText().strip()
        if not content:
            return

        if self.current_note_id:
            self.notes_manager.update_note(self.current_note_id, content)
        else:
            self.notes_manager.add_note(self.current_surah, self.current_ayah, content)

        self.load_notes()

    def delete_note(self):
        if self.current_note_id:
            # Get note preview text
            selected_item = self.notes_list.currentItem()
            note_preview = selected_item.text() if selected_item else "this note"

            # Create confirmation dialog
            msg = QtWidgets.QMessageBox(self)
            msg.setIcon(QtWidgets.QMessageBox.Warning)
            msg.setWindowTitle("Confirm Deletion")
            msg.setText(f"هل تريد حقا إزالة هذا التسجيل")
            msg.setInformativeText(note_preview)
            msg.setStandardButtons(
                QtWidgets.QMessageBox.Yes |
                QtWidgets.QMessageBox.No
            )
            msg.setDefaultButton(QtWidgets.QMessageBox.No)

            # Add keyboard shortcuts
            msg.button(QtWidgets.QMessageBox.Yes).setShortcut(QtGui.QKeySequence("Y"))
            msg.button(QtWidgets.QMessageBox.No).setShortcut(QtGui.QKeySequence("N"))

            # Show dialog and handle response
            response = msg.exec_()
            if response == QtWidgets.QMessageBox.Yes:
                self.notes_manager.delete_note(self.current_note_id)
                self.load_notes()
                self.statusBar().showMessage("Note deleted successfully", 2000)

    def delete_all_notes(self):
        if self.current_surah and self.current_ayah:
            self.notes_manager.delete_all_notes(self.current_surah, self.current_ayah)
            self.load_notes()


class AyahSelectorDialog(QtWidgets.QDialog):
    play_requested = QtCore.pyqtSignal(int, int, int)
    search_requested = QtCore.pyqtSignal(str)

    def __init__(self, notes_manager, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Ayah Selector")
        self.resize(250, 350)  # Set initial size but allow resizing
        self.notes_manager = notes_manager
        self.current_course_id = None
        self.init_ui()
        # Connect the itemChanged signal so edits are handled properly
        self.model.itemChanged.connect(self.on_item_changed)
        self.list_view.selectionModel().selectionChanged.connect(self.on_selection_changed)
        self.load_new_course()

        # Add shortcuts for navigation (left/right arrow keys)
        self.shortcut_prev = QtWidgets.QShortcut(QtGui.QKeySequence("Left"), self)
        self.shortcut_prev.activated.connect(self.load_previous_course_and_focus)
        self.shortcut_next = QtWidgets.QShortcut(QtGui.QKeySequence("Right"), self)
        self.shortcut_next.activated.connect(self.load_next_course_and_focus)

    def init_ui(self):
        layout = QtWidgets.QVBoxLayout(self)

        # Top input field with navigation buttons
        self.course_input = QtWidgets.QLineEdit()
        self.prev_button = QtWidgets.QPushButton("<-")
        self.next_button = QtWidgets.QPushButton("->")
        # Make navigation buttons as small as possible
        self.prev_button.setFixedSize(25, 25)
        self.next_button.setFixedSize(25, 25)
        nav_layout = QtWidgets.QHBoxLayout()
        nav_layout.addWidget(self.prev_button)
        nav_layout.addWidget(self.course_input)
        nav_layout.addWidget(self.next_button)
        layout.addLayout(nav_layout)

        # List view and model
        self.model = QtGui.QStandardItemModel()
        self.list_view = QtWidgets.QListView()
        self.list_view.setModel(self.model)
        self.list_view.setEditTriggers(
            QtWidgets.QAbstractItemView.DoubleClicked | QtWidgets.QAbstractItemView.EditKeyPressed
        )
        self.list_view.installEventFilter(self)
        layout.addWidget(self.list_view)

        # Status label (for validation and course messages)
        self.status_label = QtWidgets.QLabel("")
        layout.addWidget(self.status_label)

        # Custom button layout: Save on the left, OK on the right
        button_layout = QtWidgets.QHBoxLayout()
        self.save_button = QtWidgets.QPushButton("Save")
        ok_button = QtWidgets.QPushButton("OK")
        button_layout.addWidget(self.save_button)
        button_layout.addStretch()  # Pushes OK button to the right
        button_layout.addWidget(ok_button)
        layout.addLayout(button_layout)
        # Connect buttons:
        self.save_button.clicked.connect(self.save_course)
        ok_button.clicked.connect(self.accept)

        # Navigation button connections using helper functions for focus
        self.prev_button.clicked.connect(self.load_previous_course_and_focus)
        self.next_button.clicked.connect(self.load_next_course_and_focus)

    def load_previous_course_and_focus(self):
        self.load_previous_course()
        self.list_view.setFocus()

    def load_next_course_and_focus(self):
        self.load_next_course()
        self.list_view.setFocus()

    def update_status(self, message):
        self.status_label.setText(message)

    def add_empty_item(self):
        """Append an empty, editable item to the model."""
        empty_item = QtGui.QStandardItem("")
        empty_item.setEditable(True)
        self.model.appendRow(empty_item)

    def ensure_extra_row(self):
        """Ensure there is always an extra empty row at the bottom."""
        if self.model.rowCount() == 0:
            self.add_empty_item()
        else:
            last_item = self.model.item(self.model.rowCount() - 1)
            if last_item.text().strip() != "":
                self.add_empty_item()

    def remove_item(self, row):
        """Remove the item at the specified row and ensure an extra row exists."""
        self.model.blockSignals(True)
        self.model.removeRow(row)
        self.model.blockSignals(False)
        self.ensure_extra_row()

    def on_selection_changed(self, selected, deselected):
        # For newly selected items, update search items' text to include the query.
        for index in selected.indexes():
            item = self.model.itemFromIndex(index)
            data = item.data(Qt.UserRole)
            if data and data.get("type") == "search":
                new_text = "بحث عن " + data.get("query", "")
                self.model.blockSignals(True)
                item.setText(new_text)
                self.model.blockSignals(False)
        # For items that are no longer selected, revert search items' text back to "بحث".
        for index in deselected.indexes():
            item = self.model.itemFromIndex(index)
            data = item.data(Qt.UserRole)
            if data and data.get("type") == "search":
                self.model.blockSignals(True)
                item.setText("بحث")
                self.model.blockSignals(False)

    def on_item_changed(self, item):
        text = item.text().strip()
        row = self.model.indexFromItem(item).row()

        # If text is empty, remove it
        if text == "":
            QtCore.QTimer.singleShot(0, lambda r=row: self.remove_item(r))
            return

        # Validate input
        parts = text.split()
        if parts[0].lower() == "a":
            if len(parts) not in (3, 4):
                self.update_status("Invalid format. Use 'a surah ayah' or 'a surah start end'.")
                return
            try:
                surah = int(parts[1])
                start = int(parts[2])
                end = int(parts[3]) if len(parts) == 4 else start
                formatted = f"Surah {surah}: Ayah {start}-{end}" if start != end else f"Surah {surah}: Ayah {start}"
                item.setText(formatted)
                item.setData({'type': 'ayah', 'surah': surah, 'start': start, 'end': end}, Qt.UserRole)
                self.update_status("Valid input.")
            except ValueError:
                self.update_status("Invalid ayah numbers.")
        elif parts[0].lower() == "s":
            item.setText("بحث")
            item.setData({'type': 'search', 'query': " ".join(parts[1:])}, Qt.UserRole)
            self.update_status("Valid input.")
        else:
            self.update_status("Invalid input. Use 'a' or 's' as prefixes.")

        self.ensure_extra_row()

    def eventFilter(self, source, event):
        if source is self.list_view and event.type() == QtCore.QEvent.KeyPress:
            if event.key() in (QtCore.Qt.Key_Return, QtCore.Qt.Key_Enter):
                index = self.list_view.currentIndex()
                if index.isValid():
                    item = self.model.itemFromIndex(index)
                    if not item.text().strip():
                        self.list_view.edit(index)
                        return True
                    data = item.data(Qt.UserRole)
                    if data:
                        if data['type'] == 'ayah':
                            self.play_requested.emit(data['surah'], data['start'], data['end'])
                        elif data['type'] == 'search':
                            self.search_requested.emit(data['query'])
                return True
        return super().eventFilter(source, event)

    def load_new_course(self):
        self.current_course_id, course = self.notes_manager.get_new_course()
        self.load_course(course)

    def load_previous_course(self):
        self.current_course_id, course = self.notes_manager.get_previous_course(self.current_course_id)
        self.load_course(course)

    def load_next_course(self):
        self.current_course_id, course = self.notes_manager.get_next_course(self.current_course_id)
        self.load_course(course)

    def load_course(self, course):
        self.model.clear()
        self.course_input.setText(course['title'])
        for item_str in course['items']:
            try:
                # Try to parse the saved JSON data.
                item_data = json.loads(item_str)
                text = item_data.get("text", "")
                user_data = item_data.get("user_data", None)
            except Exception:
                # Fallback: treat it as plain text.
                text = item_str
                user_data = None
            list_item = QtGui.QStandardItem(text)
            list_item.setEditable(True)
            if user_data is not None:
                list_item.setData(user_data, Qt.UserRole)
            self.model.appendRow(list_item)
        self.add_empty_item()
        self.update_status(f"Loaded course ID: {self.current_course_id}")

    def save_course(self):
        title = self.course_input.text().strip() or f"درس رقم {self.current_course_id or 'NEW'}"
        items = []
        for row in range(self.model.rowCount()):
            item = self.model.item(row)
            if item.text().strip():
                user_data = item.data(Qt.UserRole)
                if user_data is not None:
                    items.append(json.dumps({"text": item.text(), "user_data": user_data}))
                else:
                    items.append(json.dumps({"text": item.text()}))
        if items:
            new_id = self.notes_manager.save_course(self.current_course_id, title, items)
            self.current_course_id = new_id
            self.update_status("Course saved.")
        else:
            self.notes_manager.delete_course(self.current_course_id)
            self.update_status("Course deleted (empty list).")

    def save_and_close(self):
        self.save_course()
        self.accept()


# =============================================================================
# STEP 4: Main application window with all improvements.
# =============================================================================
class QuranBrowser(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        icon_path = os.path.join(os.path.dirname(__file__), "icon.png")
        self.setWindowIcon(QtGui.QIcon(icon_path))
        self.search_engine = QuranSearch()
        self.ayah_selector = None
        self.current_detail_result = None
        self._status_msg = ""
        self.current_surah = 0
        self.current_start_ayah = 0
        self.sequence_files = []
        self.current_sequence_index = 0
        self.playing_one = False
        self.playing_context = 0
        self.playing_range = 0
        self.playing_range_max = 0
        self.results_count_int = 0
        self.playing_ayah_range = False

        self.notes_manager = NotesManager()

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
        center_label = QtWidgets.QLabel("© 2025 MOSAID, <a href='https://mosaid.xyz/quran-search'>https://mosaid.xyz</a>")
        center_label.setAlignment(QtCore.Qt.AlignCenter)
        center_label.setTextFormat(QtCore.Qt.RichText)
        center_label.setTextInteractionFlags(QtCore.Qt.TextBrowserInteraction)
        center_label.setOpenExternalLinks(True)
        self.status_bar.addWidget(center_label, 1)

        # Right widget: shortcuts info (no stretch)
        shortcuts = QtWidgets.QLabel("Help: Ctrl+H")
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


    @property
    def status_msg(self):
        return self._status_msg

    @status_msg.setter
    def status_msg(self, value):
        self._status_msg = value
        self.updatePermanentStatus()

    def updatePermanentStatus(self):
        self.result_count.setText(f"{self.results_count_int} نتائج، {self._status_msg}")

    def setup_shortcuts(self):
        QtWidgets.QShortcut(QtGui.QKeySequence("Space"), self, activated=self.handle_space)
        QtWidgets.QShortcut(QtGui.QKeySequence("Escape"), self, activated=self.toggle_version)
        QtWidgets.QShortcut(QtGui.QKeySequence("Backspace"), self, activated=self.show_results_view)
        QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+F"), self, activated=self.input_focus)
        QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+D"), self, activated=self.toggle_theme)
        QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+P"), self, activated=self.handle_ctrlp)
        QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+R"), self, activated=self.handle_ctrlr)
        QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+S"), self, activated=self.handle_ctrls)
        QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+W"), self, activated=self.handle_ctrlw)
        QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+A"), self.results_view, activated=self.play_current_surah)
        QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+B"), self, activated=self.backto_current_surah)
        QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+H"), self, activated=self.show_help_dialog)
        QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+J"), self, activated=self.load_surah_from_current_ayah)
        QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+K"), self, activated=self.load_surah_from_current_playback)
        QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+N"), self, activated=self.new_note)
        QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+Delete"), self, activated=self.delete_note)
        QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+Shift+A"), self, activated=self.show_ayah_selector)
        QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+Shift+P"), self, activated=self.play_all_results)
        QtWidgets.QShortcut(QtGui.QKeySequence("Left"), self, activated=self.navigate_surah_left)
        QtWidgets.QShortcut(QtGui.QKeySequence("Right"), self, activated=self.navigate_surah_right)


    def new_note(self):
        if self.detail_view.isVisible():
            self.detail_view.notes_widget.new_note()

    def delete_note(self):
        if self.detail_view.isVisible():
            self.detail_view.notes_widget.delete_note()

    def showMessage(self, message, timeout=7000):
        # Save the current style
        original_style = self.status_bar.styleSheet()
        # Set an error style (red background)
        self.status_bar.setStyleSheet("QStatusBar { background-color: red; }")
        # Show the temporary message
        self.status_bar.showMessage(message, timeout)
        # After timeout, reset the style and restore permanent message
        self.status_bar.setStyleSheet(original_style)

    def show_ayah_selector(self):
        if not self.ayah_selector:
            self.ayah_selector = AyahSelectorDialog(self.notes_manager, self)
            self.ayah_selector.play_requested.connect(self.play_ayah_range)
            self.ayah_selector.search_requested.connect(self.handle_course_search)
        self.ayah_selector.show()

    def handle_course_search(self, query):
        self.search_input.setText(query)
        self.search()

    def play_ayah_range(self, surah, start, end):
        #self.status_bar.showMessage(f"{surah}:{start}--{end}", 5000)
        try:
            results = self.search_engine.search_by_surah_ayah(surah, start, end)
            if results:
                for result in results:
                    if self.notes_manager.has_note(result['surah'], result['ayah']):
                        #bullet = "◉ "  # smaller bullet than "●" "• "
                        bullet = "<span style='font-size:32px;'>•</span> "
                        result['text_simplified'] = bullet + result['text_simplified']
                        result['text_uthmani'] = bullet + result['text_uthmani']
                self.model.updateResults(results)
                self.current_surah = surah
                self.current_start_ayah = start
                self.sequence_files = []

                # Build file list
                audio_dir = get_audio_directory()
                for ayah in range(start, end+1):
                    file_path = os.path.join(audio_dir, f"{surah:03d}{ayah:03d}.mp3")
                    if os.path.exists(file_path):
                        self.sequence_files.append(os.path.abspath(file_path))

                if self.sequence_files:
                    self.current_sequence_index = 0
                    self.playing_ayah_range = True
                    self.play_next_file()
                else:
                    self.status_bar.showMessage("No audio files found for selection", 5000)
        except Exception as e:
            logging.error(f"Error playing ayah range: {str(e)}")
            self.status_bar.showMessage("Error playing selection", 5000)

    def setup_menu(self):
        menu = self.menuBar().addMenu("&Menu")
        self.theme_action = QtWidgets.QAction("Dark Mode", self, checkable=True)
        self.theme_action.toggled.connect(self.update_theme_style)
        menu.addAction(self.theme_action)

        # New action: Set Audio Directory.
        audio_dir_action = QtWidgets.QAction("Set Audio Directory", self)
        audio_dir_action.triggered.connect(self.choose_audio_directory)
        menu.addAction(audio_dir_action)
        # Add Export/Import actions
        export_action = QtWidgets.QAction("Export Notes", self)
        export_action.triggered.connect(self.export_notes)
        menu.addAction(export_action)
        import_action = QtWidgets.QAction("Import Notes", self)
        import_action.triggered.connect(self.import_notes)
        menu.addAction(import_action)

        # Add About action
        about_action = QtWidgets.QAction("About", self)
        about_action.triggered.connect(self.about_dialog)
        menu.addAction(about_action)
        # Add Help action
        help_action = QtWidgets.QAction("Help", self)
        help_action.triggered.connect(self.show_help_dialog)
        menu.addAction(help_action)
        # Exit action
        exit_action = QtWidgets.QAction("Exit", self)
        exit_action.triggered.connect(self.close)
        menu.addAction(exit_action)


    def export_notes(self):
        """Handles exporting notes to a CSV file with suggested filename."""
        # Generate default filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        default_name = f"quran_notes_{timestamp}.csv"

        # Get default documents directory
        docs_dir = QStandardPaths.writableLocation(QStandardPaths.DocumentsLocation)

        file_path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Export Notes",
            os.path.join(docs_dir, default_name),  # Suggested path/name
            "CSV Files (*.csv)",
            options=QtWidgets.QFileDialog.DontConfirmOverwrite
        )

        if file_path:
            # Ensure .csv extension
            if not file_path.lower().endswith('.csv'):
                file_path += '.csv'

            try:
                self.notes_manager.export_to_csv(file_path)
                self.status_bar.showMessage(f"Notes exported to {file_path}", 5000)
            except Exception as e:
                self.showMessage(f"Export failed: {str(e)}", 5000)

    def import_notes(self):
        """Handles importing notes from a CSV file."""
        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Import Notes", "", "CSV Files (*.csv)")
        if file_path:
            try:
                imported, duplicates, errors = self.notes_manager.import_from_csv(file_path)
                msg = f"Imported {imported} notes. Skipped {duplicates} duplicates. {errors} errors."
                self.status_bar.showMessage(msg, 7000)

                # Refresh notes display if detail view is visible
                if self.detail_view.isVisible():
                    self.detail_view.notes_widget.load_notes()
            except ValueError as e:
                self.showMessage(str(e), 7000)
            except Exception as e:
                self.showMessage(f"Import failed: {str(e)}", 7000)
        if self.detail_view.isVisible():
            self.detail_view.notes_widget.load_notes()



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
            is_dark_theme = self.theme_action.isChecked()
            self.detail_view.display_ayah(self.current_detail_result, self.search_engine, version,is_dark_theme)

    def get_current_version(self):
        return "uthmani" if "Uthmani" in self.version_combo.currentText() else "simplified"

    def handle_surah_selection(self, index):
        if index < 0:
            index = self.surah_combo.currentIndex()
        surah = index + 1
        try:
            results = self.search_engine.search_by_surah(surah)
            for result in results:
                if self.notes_manager.has_note(result['surah'], result['ayah']):
                    #bullet = "◉ "  # smaller bullet than "●" "• "
                    bullet = "<span style='font-size:32px;'>•</span> "
                    result['text_simplified'] = bullet + result['text_simplified']
                    result['text_uthmani'] = bullet + result['text_uthmani']
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
            for result in results:
                if self.notes_manager.has_note(result['surah'], result['ayah']):
                    #bullet = "◉ "  # smaller bullet than "●" "• "
                    bullet = "<span style='font-size:32px;'>•</span> "
                    result['text_simplified'] = bullet + result['text_simplified']
                    result['text_uthmani'] = bullet + result['text_uthmani']
            self.update_results(results, f"Surah {surah} (Automatic Selection)")
        except Exception as e:
            logging.exception("Error loading surah")
            self.showMessage("Error loading surah", 3000)
            return

        # Show the results view.
        self.show_results_view()

        # Scroll to the specified ayah.
        self._scroll_to_ayah(surah, selected_ayah)

    def navigate_surah_left(self):
        current_index = self.surah_combo.currentIndex()
        if current_index > 0:
            self.surah_combo.setCurrentIndex(current_index - 1)
            self.handle_surah_selection(self.surah_combo.currentIndex())

    def navigate_surah_right(self):
        current_index = self.surah_combo.currentIndex()
        if current_index < self.surah_combo.count() - 1:
            self.surah_combo.setCurrentIndex(current_index + 1)
            self.handle_surah_selection(self.surah_combo.currentIndex())


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

    # def focus_notes(self):
    #     if self.detail_view.isVisible():
    #         self.detail_view.notes_widget.editor.setFocus()

    def search(self):
        if self.detail_view.isVisible():
            self.show_results_view()

        query = self.search_input.text().strip()
        method = self.search_method_combo.currentText()
        if not query and method == "Text":
            self.showMessage("Please enter a search query", 3000)
            return
        self.search_input.update_history(query)
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
        self.search_worker = SearchWorker(self.search_engine, method, query,parent=self)
        self.search_worker.results_ready.connect(self.handle_search_results)
        self.search_worker.error_occurred.connect(lambda error: self.showMessage(f"Search error: {error}", 3000))
        self.search_worker.start()

    def handle_search_results(self, results):
        self.model.updateResults(results)
        self.results_count_int = len(results)
        self.result_count.setText(f"Found {self.results_count_int} results")
        if results:
            self.results_view.setFocus()
        # Connect to the properly defined signal
        self.model.loading_complete.connect(self.finalize_results)

    def finalize_results(self):
        self.results_count_int = len(self.model.results)
        self.result_count.setText(f"Found {self.results_count_int} results.")
        self.model.loading_complete.disconnect()  # Clean up connection

    def update_results(self, results, query):
        self.model.updateResults(results)
        self.results_count_int = len(results)
        self.result_count.setText(f"Found {self.results_count_int} results.")
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
            is_dark_theme = self.theme_action.isChecked()
            self.detail_view.display_ayah(result, self.search_engine, version,is_dark_theme)
            self.detail_view.show()
            self.results_view.hide()

    def input_focus(self):
        self.search_input.setFocus()
        self.search_input.selectAll()

    def show_results_view(self):
        self.detail_view.hide()
        self.results_view.show()
        self.results_view.setFocus()

    def handle_space(self):
        self.playing_one = True
        self.playing_context = 0
        self.playing_range = 0
        self.status_msg = ""
        self.play_current()

    def handle_ctrlp(self):
        self.playing_context = 1
        self.status_msg = "إستماع الى الأية وخمسة بعدها"
        self.play_current(count=6)

    def handle_ctrlr(self):
        method = self.search_method_combo.currentText()
        if not method == "Surah FirstAyah LastAyah":
            self.showMessage("Please select a range to repeat using 'Surah FirstAyah LastAyah' search method", 10000)
            return
        self.playing_range = 1
        self.playing_range_max = self.results_count_int
        self.play_current(count=self.playing_range_max)

    def handle_ctrlw(self):
        """Handle Ctrl+Z: Set search method to Surah and focus search input"""
        try:
            # Set search method to "Surah"
            index = self.search_method_combo.findText("Surah", QtCore.Qt.MatchFixedString)
            if index >= 0:
                self.search_method_combo.setCurrentIndex(index)

            # Focus and select all text in search input
            self.search_input.setFocus()
            self.search_input.selectAll()

            # Optional: Trigger search if needed
            # self.search()

        except Exception as e:
            logging.error(f"Error in handle_ctrlw: {str(e)}")
            self.status_bar.showMessage("Error changing search mode", 3000)

    def handle_ctrls(self):
        if self.detail_view.isVisible():
            notes_widget = self.detail_view.notes_widget
            # Check if notes editor has focus
            if notes_widget.editor.hasFocus():
                notes_widget.save_note()
                return
        # Fallback to audio stop
        self.status_msg = ""
        self.stop_playback()

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

    def play_all_results(self):
        """Play all verses in the current search results list."""
        if not self.model.results:
            self.showMessage("No results to play", 3000)
            return

        audio_dir = get_audio_directory()
        self.sequence_files = []
        self.sequence_rows = []  # Track which model rows we're playing

        # Build list of valid audio files and their corresponding result rows
        for row in range(self.model.rowCount()):
            index = self.model.index(row, 0)
            result = self.model.data(index, Qt.UserRole)
            if not result:
                continue
            
            try:
                surah = int(result['surah'])
                ayah = int(result['ayah'])
            except (KeyError, ValueError):
                continue

            file_path = os.path.join(audio_dir, f"{surah:03d}{ayah:03d}.mp3")
            if os.path.exists(file_path):
                self.sequence_files.append(os.path.abspath(file_path))
                self.sequence_rows.append(row)
            else:
                self.showMessage(f"Audio not found: Surah {surah} Ayah {ayah}", 3000)

        if self.sequence_files:
            index = self.results_view.currentIndex()
            self.current_sequence_index = 0
            if index.isValid():
                result = self.model.data(index, Qt.UserRole)
                try:
                    selected_ayah = int(result.get('ayah'))
                    self.current_sequence_index = selected_ayah -1
                except Exception as e:
                    pass
            self.playing_ayah_range = True
            self.status_bar.showMessage(f"Playing {len(self.sequence_files)} results...", 3000)
            self.play_next_file()
        else:
            self.showMessage("No audio files found in results", 3000)

    def play_next_file(self):
        """
        Play the next file in the current sequence (if any) and update the UI selection.
        When the current surah finishes, automatically load the next surah (or surah 1 if current is 114)
        and begin playback from ayah 1.
        """
        maxx = len(self.sequence_files)
        if self.current_sequence_index < maxx:
            file_path = self.sequence_files[self.current_sequence_index]
            current_surah = int(os.path.basename(file_path)[:3])
            current_ayah = int(os.path.basename(file_path)[3:6])
            chapter = self.search_engine.get_chapter_name(current_surah)
            self.status_msg = f"<span dir='rtl' style='text-align: right'> إستماع إلى الآية {current_ayah}   من سورة {chapter}  {self.current_sequence_index+1}/{maxx}</span>"
            # Continue playing the current surah.
            url = QUrl.fromLocalFile(file_path)
            self.player.setMedia(QMediaContent(url))
            self.player.play()

            # Calculate the current ayah being played.
            if self.results_view.isVisible():
                self._scroll_to_ayah(current_surah, current_ayah)
            self.current_sequence_index += 1
        else:
            if self.playing_one:
                self.playing_one = False
                return
            if self.playing_context:
                if self.playing_context < 6:
                    self.playing_context += 1
                else:
                    self.playing_context = 0
                    self.status_msg = ""
                return
            if self.playing_range:
                if self.playing_range <= self.playing_range_max:
                    self.playing_range += 1
                else:
                    self.playing_range = 1
                return
            if self.playing_ayah_range:
                self.playing_ayah_range = False
                return
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
                self.status_msg = ""



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
            <a href="https://mosaid.xyz/quran-search">https://mosaid.xyz</a>"""
        )

    def show_help_dialog(self):
        """Display comprehensive user manual from external HTML file"""
        try:
            # Get path to help file
            base_dir = Path(__file__).parent
            help_path = base_dir / "help" / "help_ar.html"

            # Read HTML content
            with open(help_path, "r", encoding="utf-8") as f:
                help_content = f.read()
        except Exception as e:
            help_content = f"<h2>Error loading help file</h2><p>{str(e)}</p>"

        # Create dialog
        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle("دليل المستخدم - Quran Search")
        #dialog.setMinimumSize(1000, 700)
        dialog.setModal(True)
        dialog.setFixedSize(800, 400)

        # Main layout
        layout = QtWidgets.QVBoxLayout(dialog)

        # Create scroll area
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)

        # Create content widget
        content = QtWidgets.QWidget()
        scroll.setWidget(content)

        # Content layout
        content_layout = QtWidgets.QVBoxLayout(content)

        # HTML viewer
        html_label = QtWidgets.QLabel()
        html_label.setTextFormat(QtCore.Qt.RichText)
        html_label.setTextInteractionFlags(QtCore.Qt.TextBrowserInteraction)
        html_label.setOpenExternalLinks(True)
        html_label.setText(help_content)

        # Add elements to layout
        content_layout.addWidget(html_label)
        layout.addWidget(scroll)

        # Add close button
        btn_box = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok)
        btn_box.accepted.connect(dialog.accept)
        layout.addWidget(btn_box)

        # Style dialog based on theme
        if self.theme_action.isChecked():
            dialog.setStyleSheet("""
                QDialog {
                    background: #333;
                    color: white;
                }
                QScrollArea {
                    background: transparent;
                }
                QLabel {
                    background: transparent;
                    color: white;
                }
            """)

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

