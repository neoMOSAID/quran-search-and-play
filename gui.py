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
import re
import sys
import csv
import json
import time
import logging
from datetime import datetime
from collections import OrderedDict

from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtCore import QUrl, QSize, Qt, QSettings, QTimer
from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent
from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEnginePage
from PyQt5.QtCore import QStandardPaths, QSettings
from PyQt5.QtGui import QColor, QDesktopServices

from search import QuranSearch, QuranWordCache

import sqlite3
from pathlib import Path

# Configure logging for debugging and error reporting.
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

class CustomWebEnginePage(QWebEnginePage):
    def acceptNavigationRequest(self, url, nav_type, isMainFrame):
        if nav_type == QWebEnginePage.NavigationTypeLinkClicked:
            # Open the URL in the default browser
            QDesktopServices.openUrl(url)
            return False  # Prevent the link from loading in the current view
        return super().acceptNavigationRequest(url, nav_type, isMainFrame)

def resource_path(relative_path):
    """Get absolute path to resource, works for dev and for PyInstaller."""
    try:
        # When bundled, PyInstaller stores files in sys._MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        # When running in development, use the directory of this script
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)


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
            conn.execute("""
                CREATE TABLE IF NOT EXISTS bookmarks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    surah INTEGER NOT NULL,
                    ayah INTEGER NOT NULL,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_bookmarks ON bookmarks (timestamp)")

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
        
    def get_all_notes(self):
        """Get all notes sorted by timestamp"""
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.execute("""
                SELECT id, surah, ayah, content, created 
                FROM notes 
                ORDER BY created DESC
            """)
            return [{
                'id': row[0],
                'surah': row[1],
                'ayah': row[2],
                'content': row[3],
                'created': row[4]
            } for row in cursor.fetchall()]

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
            
    def create_new_course(self, title=None):
        """Create a new empty course and return its ID"""
        if not title:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
            title = f"New Course {timestamp}"
            
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.execute(
                "INSERT INTO courses (title, items) VALUES (?, ?)",
                (title, json.dumps([]))
            )
            return cursor.lastrowid

    def delete_course(self, course_id):
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute("DELETE FROM courses WHERE id = ?", (course_id,))

    def get_new_course(self):
        return None, {"title": "", "items": []}

    def has_any_courses(self):
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.execute("SELECT EXISTS(SELECT 1 FROM courses)")
            return cursor.fetchone()[0] == 1
        
    def has_previous_course(self, current_id):
        with sqlite3.connect(str(self.db_path)) as conn:
            if current_id is None:
                return False  # New course can't have previous
            cursor = conn.execute(
                "SELECT EXISTS(SELECT 1 FROM courses WHERE id < ? ORDER BY id DESC LIMIT 1)",
                (current_id,)
            )
            return cursor.fetchone()[0] == 1

    def has_next_course(self, current_id):
        with sqlite3.connect(str(self.db_path)) as conn:
            if current_id is None:
                return False  # New course can't have next
            cursor = conn.execute(
                "SELECT EXISTS(SELECT 1 FROM courses WHERE id > ? ORDER BY id ASC LIMIT 1)",
                (current_id,)
            )
            return cursor.fetchone()[0] == 1

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

    def get_all_courses(self):
        """Return list of (id, title, items) for all courses"""
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.execute("""
                SELECT id, title, items FROM courses ORDER BY id DESC
            """)
            return [
                (row[0], row[1], json.loads(row[2]))
                for row in cursor.fetchall()
            ]
        
    def add_bookmark(self, surah, ayah):
        with sqlite3.connect(str(self.db_path)) as conn:
            # Remove duplicates first
            conn.execute("DELETE FROM bookmarks WHERE surah=? AND ayah=?", (surah, ayah))
            conn.execute("INSERT INTO bookmarks (surah, ayah) VALUES (?, ?)", (surah, ayah))
            # Keep only 2500 most recent
            conn.execute("""
                DELETE FROM bookmarks 
                WHERE id NOT IN (
                    SELECT id 
                    FROM bookmarks 
                    ORDER BY timestamp DESC 
                    LIMIT 2500
                )
            """)

    def get_all_bookmarks(self, search_engine):
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.execute("""
                SELECT surah, ayah, timestamp 
                FROM bookmarks 
                ORDER BY timestamp DESC
            """)
            return [{
                'surah': row[0],
                'ayah': row[1],
                'timestamp': row[2],
                'surah_name': search_engine.get_chapter_name(row[0])
            } for row in cursor.fetchall()]

    def delete_bookmark(self, surah, ayah):
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute("DELETE FROM bookmarks WHERE surah=? AND ayah=?", (surah, ayah))


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
# 
# =============================================================================
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


# =============================================================================
# 
# =============================================================================
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
# 
# =============================================================================
class SearchLineEdit(QtWidgets.QLineEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.history_max = 500  # 
        self.init_completer()
        self.init_history()

        # Setup text editing signals
        self.textEdited.connect(self.update_completion_prefix)

    def init_completer(self):
        # Create completer with dual models
        self.completer_model = QtCore.QStringListModel()
        
        self.completer = QtWidgets.QCompleter()
        self.completer.setCaseSensitivity(Qt.CaseInsensitive)
        self.completer.setFilterMode(QtCore.Qt.MatchContains)
        self.completer.setModel(self.completer_model)
        self.completer.setCompletionMode(QtWidgets.QCompleter.PopupCompletion)
        
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
        """Update both history and completer"""
        if query and query not in self.history:
            self.history.insert(0, query)
            self.history = self.history[:self.history_max]
            settings = QtCore.QSettings("MOSAID", "QuranSearch")
            settings.setValue("searchHistory", self.history)
            self.update_history_list()
            self.update_completer_model()
        

    def update_completer_model(self):
        """Combine search history and Quran words"""
        quran_words = QuranWordCache._words
        combined = self.history + ["── Quran Words ──"] + quran_words
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
    def __init__(self, version="uthmani", parent=None,is_dark=False):
        super().__init__(parent)
        self.version = version
        self.is_dark = is_dark
        self.query = ""
        self.update_theme(is_dark)
        self.settings = QSettings("MOSAID", "QuranSearch")
        self.base_font_size = self.settings.value("resultFontSize", 16, type=int)

    def update_font_size(self, new_size):
        self.base_font_size = new_size
        self.settings.setValue("resultFontSize", self.base_font_size)
        self.sizeHintChanged.emit(QtCore.QModelIndex())  # Notify view of size changes

    def update_theme(self, is_dark):
        self.is_dark = is_dark
        if self.is_dark:
            self.highlight_color = "#5D6D7E"
        else:
            self.highlight_color = "#a0c4ff"
        if self.parent():
            self.parent().viewport().update()

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
            option.palette.setColor(QtGui.QPalette.Highlight, QColor(self.highlight_color))
            option.palette.setColor(QtGui.QPalette.HighlightedText, QColor("#ffffff"))
            painter.fillRect(option.rect, option.palette.highlight())
            doc.setDefaultStyleSheet(f"body {{ color: {option.palette.highlightedText().color().name()}; }}")

        painter.translate(option.rect.topLeft())
        doc.drawContents(painter)
        painter.restore()

    def _format_text(self, result, version):
        text = result.get(f"text_{version}", "")
        return f"""
        <div dir="rtl" style="text-align:left;">
            <div style="font-family: 'Amiri'; 
                        font-size: {self.base_font_size}pt;
                        margin: 5px;">
                {text}
                <span style="color: #006400; 
                            font-size: {self.base_font_size - 2}pt;">
                    ({result.get('surah', '')}-{result.get('chapter', '')} {result.get('ayah', '')})
                </span>
            </div>
        </div>
        """

    def sizeHint(self, option, index):
        result = index.data(Qt.UserRole)
        if not result:
            return QSize(0, 0)
        
        doc = QtGui.QTextDocument()
        doc.setHtml(self._format_text(result, self.version))
        doc.setTextWidth(option.rect.width() - 20)
        return QSize(int(doc.idealWidth()) + 20, int(doc.size().height()))

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


class BookMarksDelegate(QtWidgets.QStyledItemDelegate):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.doc_cache = OrderedDict()
        self.max_cache_size = 100

    def paint(self, painter, option, index):
        painter.save()
        
        # Setup style options
        option = QtWidgets.QStyleOptionViewItem(option)
        self.initStyleOption(option, index)
        
        # Use style's drawing capabilities
        style = option.widget.style() if option.widget else QtWidgets.QApplication.style()
        
        # Draw background
        style.drawPrimitive(QtWidgets.QStyle.PE_PanelItemViewItem, option, painter, option.widget)
        
        # Setup HTML document
        doc = QtGui.QTextDocument()
        doc.setHtml(option.text)
        doc.setDocumentMargin(2)
        
        # Set text color based on state
        if option.state & QtWidgets.QStyle.State_Selected:
            doc.setDefaultStyleSheet(f"body {{ color: {option.palette.highlightedText().color().name()}; }}")
        else:
            doc.setDefaultStyleSheet(f"body {{ color: {option.palette.text().color().name()}; }}")
        
        # Calculate positioning
        text_rect = style.subElementRect(QtWidgets.QStyle.SE_ItemViewItemText, option, option.widget)
        painter.translate(text_rect.topLeft())
        doc.setTextWidth(text_rect.width())
        doc.drawContents(painter)
        
        painter.restore()

    def sizeHint(self, option, index):
        if not index.isValid():
            return QtCore.QSize(0, 0)
        
        # Use timestamp + surah + ayah as unique cache key
        bm_data = index.data(Qt.UserRole)
        cache_key = f"{bm_data['timestamp']}-{bm_data['surah']}-{bm_data['ayah']}"
        
        # Return cached size if available
        if cache_key in self.doc_cache:
            return self.doc_cache[cache_key]
        
        # Calculate new size
        doc = QtGui.QTextDocument()
        doc.setHtml(index.data(Qt.DisplayRole))
        doc.setDocumentMargin(2)
        doc.setTextWidth(option.rect.width() - 20)
        
        size = QtCore.QSize(
            int(doc.idealWidth()) + 20,
            int(doc.size().height()) + 8
        )
        
        # Manage cache size
        if len(self.doc_cache) >= self.max_cache_size:
            self.doc_cache.popitem(last=False)  # Remove oldest entry
        self.doc_cache[cache_key] = size
        
        return size

    def clear_cache(self):
        self.doc_cache.clear()


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

        #Optional: Add padding and set minimum row height
        self.notes_list.setStyleSheet("""
            QListWidget::item {
                padding: 8px;
            }
            QListWidget::item:selected {
                color: palette(highlighted-text);
                background: palette(highlight);
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
    #PLACEHOLDER_TEXT = "Enter 'a surah start [end]' or :  \n 's search terms' help: Ctrl+H"
    PLACEHOLDER_TEXT = "أكتب a رقم السورة رقم الآية [رقم الآية]"
    PLACEHOLDER_TEXT += "\n"
    PLACEHOLDER_TEXT += "أو أكتب s ثم كلمات البحث"
    PLACEHOLDER_TEXT += "\n للمزيد : Ctrl+Shift+H \n"
    PLACEHOLDER_TEXT += "مثال a 255 \n a 255 260 \n s بحر"


    def __init__(self, notes_manager, parent=None):
        super().__init__(parent)
        self.setWindowTitle("دروس القرآن")
        self.resize(250, 350)  # Set initial size but allow resizing
        self.notes_manager = notes_manager
        self.current_course_id = None
        self.init_ui()
        # Connect the itemChanged signal so edits are handled properly
        self.model.itemChanged.connect(self.on_item_changed)
        self.list_view.selectionModel().selectionChanged.connect(self.on_selection_changed)
        self.list_view.doubleClicked.connect(self.on_double_click)
        self.load_new_course()

        # Add shortcuts for navigation (left/right arrow keys)
        self.shortcut_prev = QtWidgets.QShortcut(QtGui.QKeySequence("Left"), self)
        self.shortcut_prev.activated.connect(self._handle_prev_shortcut)
        self.shortcut_next = QtWidgets.QShortcut(QtGui.QKeySequence("Right"), self)
        self.shortcut_next.activated.connect(self._handle_next_shortcut)
        
        self.load_previous_course_and_focus()
        

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
            QtWidgets.QAbstractItemView.DoubleClicked | 
            QtWidgets.QAbstractItemView.EditKeyPressed 
        )
        self.list_view.installEventFilter(self)
        layout.addWidget(self.list_view)
        #rtl 
        self.list_view.setLayoutDirection(QtCore.Qt.RightToLeft)
        self.list_view.setStyleSheet("""
            QListView {
                font-family: 'Amiri';
                font-size: 14pt;
                padding-right: 10px;
            }
        """)

        # Status label (for validation and course messages)
        self.status_label = QtWidgets.QLabel("")
        layout.addWidget(self.status_label)

        # Custom button layout: Save - New - OK
        button_layout = QtWidgets.QHBoxLayout()
        self.save_button = QtWidgets.QPushButton("Save")
        self.new_button = QtWidgets.QPushButton("New")  # Add new button
        ok_button = QtWidgets.QPushButton("OK")
        
        button_layout.addWidget(self.save_button)
        button_layout.addWidget(self.new_button)       # Add New button
        button_layout.addStretch()                     # Pushes OK to right
        button_layout.addWidget(ok_button)
        
        layout.addLayout(button_layout)

        # Connect buttons
        self.save_button.clicked.connect(self.save_course)
        self.new_button.clicked.connect(self.create_new_course)  # New connection
        ok_button.clicked.connect(self.accept)

        # Navigation button connections using helper functions for focus
        self.prev_button.clicked.connect(self.load_previous_course_and_focus)
        self.next_button.clicked.connect(self.load_next_course_and_focus)

    def on_double_click(self, index):
        """Handle double click to start editing"""
        if index.isValid():
            self.start_editing(index)

    def start_editing(self, index=None):
        """Safe editing with existence check"""
        if not index:
            index = self.list_view.currentIndex()
        
        if index.isValid():
            # Verify item still exists in model
            if index.row() >= self.model.rowCount():
                return
                
            item = self.model.itemFromIndex(index)
            if item:  # Additional null check
                current_text = item.text().strip()
                
                # Clear placeholder if needed
                if current_text == self.PLACEHOLDER_TEXT:
                    self.model.blockSignals(True)
                    item.setText("")
                    item.setForeground(QtGui.QColor(self.palette().text().color()))
                    self.model.blockSignals(False)
                
                # Start editing only if item exists
                self.list_view.edit(index)

    def load_previous_course_and_focus(self):
        self.load_previous_course()
        self.list_view.setFocus()

    def load_next_course_and_focus(self):
        self.load_next_course()
        self.list_view.setFocus()

    def _handle_prev_shortcut(self):
        if self.prev_button.isEnabled():
            self.load_previous_course_and_focus()

    def _handle_next_shortcut(self):
        if self.next_button.isEnabled():
            self.load_next_course_and_focus()

    def create_new_course(self):
        """Handle creation of new empty course"""
        # Create new course through manager
        new_id = self.notes_manager.create_new_course()
        
        # Load the newly created course
        self.current_course_id = new_id
        self.load_new_course()
        
        # Update UI
        self.course_input.clear()
        self.update_status("New course created")
        self.update_navigation_buttons()
        
    def update_status(self, message):
        self.status_label.setText(message)

    def add_empty_item(self):
        """Append an empty, editable item with placeholder text"""
        item = QtGui.QStandardItem(self.PLACEHOLDER_TEXT)
        item.setEditable(True)
        item.setForeground(QtGui.QColor(Qt.gray))
        self.model.appendRow(item)

    def ensure_extra_row(self):
        """Ensure there is always an extra empty row at the bottom."""
        if self.model.rowCount() == 0:
            self.add_empty_item()
        else:
            last_item = self.model.item(self.model.rowCount() - 1)
            if last_item.text().strip() != "" and last_item.text().strip() != self.PLACEHOLDER_TEXT:
                self.add_empty_item()

    def remove_item(self, row):
        """Remove the item at the specified row and ensure an extra row exists."""
        self.model.blockSignals(True)
        self.model.removeRow(row)
        self.model.blockSignals(False)
        self.model.layoutChanged.emit() 

    def safe_remove_item(self, row):
        """Safely remove item after validation"""
        try:
            # Check if row still exists
            if row < self.model.rowCount():
                self.remove_item(row)
                self.ensure_extra_row()
        except Exception as e:
            print(f"Error removing item: {str(e)}")

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

    def update_item_alignment(self, index):
        item = self.model.itemFromIndex(index)
        if item:
            item.setTextAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)

    def on_item_changed(self, item):
        text = item.text().strip()
        row = self.model.indexFromItem(item).row()

        # Handle placeholder text
        if text == self.PLACEHOLDER_TEXT:
            text = ""
        if text == "":
            QtCore.QTimer.singleShot(0, lambda r=row: self.safe_remove_item(r))
            return

        # Validate input
        parts = text.split()
        if len(parts) == 0:
            return

        try:
            if parts[0].lower() == "a":
                if len(parts) not in (3, 4):
                    self.update_status("Invalid format. Use 'a surah ayah' or 'a surah start end'.")
                    return

                self.model.blockSignals(True)
                try:
                    surah = int(parts[1])
                    start = int(parts[2])
                    end = int(parts[3]) if len(parts) == 4 else start
                    chapter_name = self.parent().search_engine.get_chapter_name(surah)
                    formatted = f"{chapter_name} آية {start}-{end}" if start != end else f"{chapter_name} آية {start}"
                    item.setText(formatted)
                    item.setData({'type': 'ayah', 'surah': surah, 'start': start, 'end': end}, Qt.UserRole)
                    #item.setForeground(QtGui.QColor(self.palette().text().color()))
                    self.update_status("Valid input.")
                finally:
                    self.model.blockSignals(False)
            elif parts[0].lower() == "s":
                self.model.blockSignals(True)
                try:
                    query = " ".join(parts[1:])
                    item.setText("بحث")
                    item.setData({'type': 'search', 'query': query}, Qt.UserRole)
                    #item.setForeground(QtGui.QColor(self.palette().text().color()))
                    self.update_status("Valid input.")
                finally:
                    self.model.blockSignals(False)
            else:
                self.update_status("Invalid input. Use 'a' or 's' as prefixes.")

        except ValueError as e:
            self.update_status(f"Invalid numbers: {str(e)}")
        except Exception as e:
            self.update_status(f"Error: {str(e)}")

        self.ensure_extra_row()

    def handle_f2_edit(self):
        index = self.list_view.currentIndex()
        if index.isValid():
            item = self.model.itemFromIndex(index)
            if item.text() == self.PLACEHOLDER_TEXT:
                item.setText("")
                item.setForeground(QtGui.QColor(self.palette().text().color()))
            self.list_view.edit(index)

    def eventFilter(self, source, event):
        if source is self.list_view and event.type() == QtCore.QEvent.KeyPress:
            # Check for Ctrl+Delete first
            if event.key() == QtCore.Qt.Key_Delete and event.modifiers() & QtCore.Qt.ControlModifier:
                self.delete_current_course()
                return True
            if event.key() in (QtCore.Qt.Key_Return, QtCore.Qt.Key_Enter):
                index = self.list_view.currentIndex()
                if index.isValid():
                    item = self.model.itemFromIndex(index)
                    current_text = item.text().strip()
                    
                    if current_text == self.PLACEHOLDER_TEXT:
                        # Clear placeholder and start editing
                        self.model.blockSignals(True)
                        item.setText("")
                        item.setForeground(QtGui.QColor(self.palette().text().color()))
                        self.model.blockSignals(False)
                        self.list_view.edit(index)
                        return True
                    
                    # # Validate before closing editor
                    # self.validate_and_format_item(item)
                    # return True
                    
                    data = item.data(Qt.UserRole)
                    if data:
                        if data['type'] == 'ayah':
                            self.play_requested.emit(data['surah'], data['start'], data['end'])
                        elif data['type'] == 'search':
                            self.search_requested.emit(data['query'])
                return True
            if event.key() == QtCore.Qt.Key_F2:
                self.handle_f2_edit()
                return True
            if event.key() == QtCore.Qt.Key_Delete:
                index = self.list_view.currentIndex()
                if index.isValid():
                    row = index.row()
                    self.safe_remove_item(row)
                return True
            # Add Ctrl+Up/Down handling
            if event.modifiers() & QtCore.Qt.ControlModifier:
                if event.key() == QtCore.Qt.Key_Up:
                    self.move_item_up()
                    return True
                elif event.key() == QtCore.Qt.Key_Down:
                    self.move_item_down()
                    return True
        return super().eventFilter(source, event)

    def load_new_course(self):
        self.current_course_id, course = self.notes_manager.get_new_course()
        self.load_course(course)
    
    def load_course_by_id(self, course_id):
        """Load a course by its ID"""
        courses = self.notes_manager.get_all_courses()
        for c in courses:
            if c[0] == course_id:
                self.current_course_id = c[0]
                self.load_course({'title': c[1], 'items': c[2]})
                break

    def load_previous_course(self):
        prev_id, prev_course = self.notes_manager.get_previous_course(self.current_course_id)
        if prev_id == self.current_course_id:  # No more previous courses
            return
        self.current_course_id = prev_id
        self.load_course(prev_course)
        self.update_navigation_buttons()

    def load_next_course(self):
        next_id, next_course = self.notes_manager.get_next_course(self.current_course_id)
        if next_id == self.current_course_id:  # No more next courses
            return
        self.current_course_id = next_id
        self.load_course(next_course)
        self.update_navigation_buttons()

    def update_navigation_buttons(self):
        """Enable/disable buttons based on course position"""
        # Handle new course (ID None) case
        if self.current_course_id is None:
            # Check if any courses exist at all
            has_any = self.notes_manager.has_any_courses()
            self.prev_button.setEnabled(has_any)  # Can go to last existing course
            self.next_button.setEnabled(False)    # No next after new course
        else:
            # Existing course logic
            has_prev = self.notes_manager.has_previous_course(self.current_course_id)
            has_next = self.notes_manager.has_next_course(self.current_course_id)
            self.prev_button.setEnabled(has_prev)
            self.next_button.setEnabled(has_next)

    def load_course(self, course):
        self.model.clear()
        self.course_input.setText(course['title'])
        
        for item_str in course['items']:
            try:
                item_data = json.loads(item_str)
                user_data = item_data.get("user_data")
                text = self.format_display_text(item_data)
            except Exception:
                text = item_str
                user_data = None

            list_item = QtGui.QStandardItem(text)
            if user_data:
                list_item.setData(user_data, Qt.UserRole)
            self.model.appendRow(list_item)
        
        self.add_empty_item()
        self.update_status(f"Loaded course ID: {self.current_course_id}")
        self.update_navigation_buttons()

    def format_display_text(self, item_data):
        """Convert stored data to display text with chapter names"""
        user_data = item_data.get("user_data")
        if not user_data:
            return item_data.get("text", "")
            
        if user_data.get('type') == 'ayah':
            surah = user_data['surah']
            chapter_name = self.parent().search_engine.get_chapter_name(surah)
            start = user_data['start']
            end = user_data.get('end', start)
            
            if start == end:
                return f"{chapter_name} آية {start}"
            return f"{chapter_name} آية {start}-{end}"
            
        if user_data.get('type') == 'search':
            return f"بحث عن {user_data.get('query', '')}"
            
        return item_data.get("text", "")

    def save_course(self):
        title = self.course_input.text().strip() or f"درس رقم {self.current_course_id or 'NEW'}"
        items = []
        has_valid_items = False
        
        for row in range(self.model.rowCount()):
            item = self.model.item(row)
            text = item.text().strip()
            
            # Skip placeholder text and empty items
            if text == self.PLACEHOLDER_TEXT or not text:
                continue
                
            # Track if we have any valid items
            has_valid_items = True
            
            user_data = item.data(Qt.UserRole)
            if user_data is not None:
                items.append(json.dumps({"text": item.text(), "user_data": user_data}))
            else:
                items.append(json.dumps({"text": item.text()}))
        
        if has_valid_items:
            new_id = self.notes_manager.save_course(self.current_course_id, title, items)
            self.current_course_id = new_id
            self.update_status("Course saved.")
        else:
            self.notes_manager.delete_course(self.current_course_id)
            self.update_status("Course deleted (no valid items).")

    def save_and_close(self):
        self.save_course()
        self.accept()

    def delete_current_course(self):
        if self.current_course_id is not None:
            reply = QtWidgets.QMessageBox.question(
                self,
                "Confirm Deletion",
                f"هل تريد حقا حذف درس :  {self.course_input.text()} ؟",
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                QtWidgets.QMessageBox.No
            )
            if reply == QtWidgets.QMessageBox.Yes:
                self.notes_manager.delete_course(self.current_course_id)
                self.update_status("Current course deleted.")
                self.load_new_course()  # Load a new course after deletion
            else:
                self.update_status("Course deletion canceled.")
        else:
            self.update_status("No current course to delete.")

    
    def move_item_up(self):
        current_row = self.list_view.currentIndex().row()
        if current_row > 0:
            self._swap_items(current_row, current_row - 1)
            self.list_view.setCurrentIndex(self.model.index(current_row - 1, 0))

    def move_item_down(self):
        current_row = self.list_view.currentIndex().row()
        if current_row < self.model.rowCount() - 1:
            self._swap_items(current_row, current_row + 1)
            self.list_view.setCurrentIndex(self.model.index(current_row + 1, 0))

    def _swap_items(self, row1, row2):
        # Handle downward movement adjustment
        if row2 > row1:
            row2 -= 1
        
        # Swap rows using model methods
        item1 = self.model.takeRow(row1)
        item2 = self.model.takeRow(row2)
        self.model.insertRow(row2, item1)
        self.model.insertRow(row1, item2)


class CourseSelectionDialog(QtWidgets.QDialog):
    def __init__(self, notes_manager, parent=None):
        super().__init__(parent)
        self.notes_manager = notes_manager
        self.selected_course_id = None
        self.init_ui()
        self.load_courses()

    def init_ui(self):
        self.setWindowTitle("Add to Course")
        self.resize(400, 400)
        
        layout = QtWidgets.QVBoxLayout()
        
        # Course list
        self.course_list = QtWidgets.QListWidget()
        self.course_list.itemDoubleClicked.connect(self.accept)
        layout.addWidget(self.course_list)
        
        # Button layout
        button_layout = QtWidgets.QHBoxLayout()
        
        # New Course button
        self.new_btn = QtWidgets.QPushButton("New Course")
        self.new_btn.clicked.connect(self.create_new_course)
        button_layout.addWidget(self.new_btn)
        
        # Spacer
        button_layout.addStretch()
        
        # Dialog buttons
        self.button_box = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
        )
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        button_layout.addWidget(self.button_box)
        
        layout.addLayout(button_layout)
        self.setLayout(layout)

    def create_new_course(self):
        """Create a new course and refresh the list"""
        new_id = self.notes_manager.create_new_course()
        self.load_courses()
        
        # Select the new course
        for i in range(self.course_list.count()):
            item = self.course_list.item(i)
            if item.data(Qt.UserRole) == new_id:
                self.course_list.setCurrentItem(item)
                break

    def load_courses(self):
        self.course_list.clear()
        courses = self.notes_manager.get_all_courses()
        for course_id, title, _ in courses:
            item = QtWidgets.QListWidgetItem(title)
            item.setData(Qt.UserRole, course_id)
            self.course_list.addItem(item)

    def get_selected_course(self):
        selected = self.course_list.currentItem()
        if selected:
            return selected.data(Qt.UserRole)
        return None
            

class BookmarkDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.setWindowTitle("الآيات المرجعية")
        self.resize(600, 400)
        self.setWindowModality(QtCore.Qt.NonModal)
        
        # Create model and delegate
        self.model = BookmarkModel()
        self.delegate = BookMarksDelegate()
        
        # Setup UI
        self.list_view = QtWidgets.QListView()
        self.list_view.setItemDelegate(self.delegate)
        self.list_view.setModel(self.model)
        self.list_view.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.list_view.setFocusPolicy(QtCore.Qt.StrongFocus)
        self.list_view.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.list_view.setFocus()
        self.list_view.setVerticalScrollMode(QtWidgets.QAbstractItemView.ScrollPerPixel)
        self.list_view.verticalScrollBar().setSingleStep(20)
        self.list_view.setStyleSheet("""
            QListView {
                show-decoration-selected: 1;
            }
            QListView::item {
                padding-right: 25px;
            }
            QListView::item:selected {
                background: palette(highlight);
                color: palette(highlighted-text);
            }
            QScrollBar:vertical {
                width: 12px;
            }
        """)

        # Connect scrollbar to load more
        self.list_view.verticalScrollBar().valueChanged.connect(
            self.check_scroll_position
        )
        
        # Buttons
        self.remove_btn = QtWidgets.QPushButton("حذف المحدد")
        self.close_btn = QtWidgets.QPushButton("إغلاق")
        
        # Layout
        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(self.list_view)
        
        btn_layout = QtWidgets.QHBoxLayout()
        btn_layout.addWidget(self.remove_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(self.close_btn)
        layout.addLayout(btn_layout)
        
        # Connections
        self.close_btn.clicked.connect(self.hide)
        self.remove_btn.clicked.connect(self.remove_selected)
        self.list_view.doubleClicked.connect(self.load_and_close)

        self.list_view.installEventFilter(self)


    def check_scroll_position(self):
        if self.model._loaded_count < len(self.model._bookmarks):
            self.model.load_next_chunk()

    def eventFilter(self, source, event):
        if source is self.list_view and event.type() == QtCore.QEvent.KeyPress:
            if event.key() in (QtCore.Qt.Key_Return, QtCore.Qt.Key_Enter):
                self.load_and_close()
                return True
            elif event.key() == QtCore.Qt.Key_Delete:
                self.remove_selected()
                return True
            elif event.key() in (QtCore.Qt.Key_Up, QtCore.Qt.Key_Down):
                # Allow default navigation
                return False
        return super().eventFilter(source, event)
    
    def showEvent(self, event):
        self.load_bookmarks()
        # Auto-select first item if exists
        if self.model.rowCount() > 0:
            index = self.model.index(0)
            self.list_view.setCurrentIndex(index)

    def load_bookmarks(self):
        bookmarks = self.parent.notes_manager.get_all_bookmarks(self.parent.search_engine)
        self.model.load_bookmarks(bookmarks)
        # Show first items immediately
        self.model._loaded_count = min(50, len(bookmarks))
        self.model.layoutChanged.emit()

    def load_and_close(self):
        self.parent.load_selected_bookmark()
        #self.hide()

    def remove_selected(self):
        selected = self.list_view.selectionModel().selectedIndexes()
        if not selected:
            return
            
        # Remove in reverse order
        for index in sorted(selected, reverse=True):
            row = index.row()
            if row >= len(self.model._bookmarks):
                continue  # Prevent invalid access
                
            bm = self.model.data(index, Qt.UserRole)
            self.parent.notes_manager.delete_bookmark(bm['surah'], bm['ayah'])
            
            self.model.beginRemoveRows(QtCore.QModelIndex(), row, row)
            del self.model._bookmarks[row]
            self.model._loaded_count = min(self.model._loaded_count, len(self.model._bookmarks))
            self.model.endRemoveRows()


class NoteDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("إضافة تسجيل")
        self.setWindowModality(QtCore.Qt.NonModal)  # Non-modal
        self.resize(400, 300)
        
        # Main vertical layout
        layout = QtWidgets.QVBoxLayout(self)
        
        # Text editor for note entry
        self.editor = QtWidgets.QTextEdit()
        self.editor.setPlaceholderText("Enter your note here...")
        self.editor.setStyleSheet("""
            font-family: 'Amiri';
            font-size: 14pt;
        """)

        layout.addWidget(self.editor)

        
        # Create a horizontal layout for the label and buttons
        h_layout = QtWidgets.QHBoxLayout()
        
        # Label to display verse information
        self.info_label = QtWidgets.QLabel("")
        h_layout.addWidget(self.info_label)
        
        # Dialog buttons
        button_box = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        h_layout.addWidget(button_box)
        
        # Add the horizontal layout to the main layout
        layout.addLayout(h_layout)

class NotesManagerDialog(QtWidgets.QDialog):
    show_ayah_requested = QtCore.pyqtSignal(int, int)  # Surah, Ayah

    def __init__(self, notes_manager, search_engine, parent=None):
        super().__init__(parent)
        self.notes_manager = notes_manager
        self.search_engine = search_engine
        self.current_note = None
        self.init_ui()
        self.setup_rtl()

    def init_ui(self):
        self.setWindowTitle("إدارة التسجيلات")
        self.resize(1000, 600)
        
        # Main layout
        main_layout = QtWidgets.QVBoxLayout(self)
        
        # Splitter with 20%-80% initial ratio
        self.splitter = QtWidgets.QSplitter(Qt.Horizontal)
        
        # Content area (80%)
        content_widget = QtWidgets.QWidget()
        content_layout = QtWidgets.QVBoxLayout(content_widget)
        
        # Note content editor
        self.note_content = QtWidgets.QTextEdit()
        self.note_content.textChanged.connect(self.on_content_changed)
        
        # Buttons
        button_box = QtWidgets.QDialogButtonBox(Qt.Horizontal)
        self.save_btn = button_box.addButton("حفظ", QtWidgets.QDialogButtonBox.ActionRole)
        self.delete_btn = button_box.addButton("حذف", QtWidgets.QDialogButtonBox.DestructiveRole)
        self.show_btn = button_box.addButton("عرض الآية", QtWidgets.QDialogButtonBox.HelpRole)
        
        self.save_btn.setEnabled(False)
        self.delete_btn.setEnabled(False)
        
        content_layout.addWidget(QtWidgets.QLabel("المحتوى:"))
        content_layout.addWidget(self.note_content)
        content_layout.addWidget(button_box)
        
        # Notes list (20%)
        self.notes_list = QtWidgets.QListWidget()
        self.notes_list.setLayoutDirection(Qt.RightToLeft)
        self.notes_list.itemSelectionChanged.connect(self.on_note_selected)
        
        # Add widgets to splitter
        self.splitter.addWidget(self.notes_list)
        self.splitter.addWidget(content_widget)
        self.splitter.setSizes([200, 800])  # 80%-20% ratio
        
        main_layout.addWidget(self.splitter)
        
        # Connections
        self.save_btn.clicked.connect(self.save_note)
        self.delete_btn.clicked.connect(self.delete_note)
        self.show_btn.clicked.connect(self.show_ayah)

    def setup_rtl(self):
        # Set RTL layout direction
        self.setLayoutDirection(Qt.RightToLeft)
        self.notes_list.setLayoutDirection(Qt.RightToLeft)
        
        # Arabic font styling
        arabic_font = QtGui.QFont("Amiri", 12)
        self.notes_list.setFont(arabic_font)
        self.note_content.setFont(arabic_font)
        
        self.notes_list.setStyleSheet("""
            QListWidget {
                font-family: 'Amiri';
                font-size: 14pt;
            }
            QListWidget::item {
                padding: 8px;
                border-bottom: 1px solid #ddd;
            }
        """)

    def load_notes(self):
        self.notes_list.clear()
        notes = self.notes_manager.get_all_notes()
        
        for note in notes:
            surah_name = self.search_engine.get_chapter_name(note['surah'])
            item_text = f"{surah_name} - الآية {note['ayah']}"
            item = QtWidgets.QListWidgetItem(item_text)
            item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            item.setData(Qt.UserRole, note)
            self.notes_list.addItem(item)

    def on_note_selected(self):
        selected = self.notes_list.currentItem()
        if selected:
            self.current_note = selected.data(Qt.UserRole)
            self.note_content.setPlainText(self.current_note['content'])
            self.delete_btn.setEnabled(True)
            self.show_btn.setEnabled(True)
        else:
            self.current_note = None
            self.note_content.clear()
            self.delete_btn.setEnabled(False)
            self.show_btn.setEnabled(False)

    def on_content_changed(self):
        self.save_btn.setEnabled(True)

    def save_note(self):
        if self.current_note:
            new_content = self.note_content.toPlainText().strip()
            if new_content:
                self.notes_manager.update_note(self.current_note['id'], new_content)
                self.load_notes()
                self.save_btn.setEnabled(False)
                self.showMessage("تم حفظ التغييرات", 2000)

    def delete_note(self):
        if self.current_note:
            confirm = QtWidgets.QMessageBox.question(
                self,
                "تأكيد الحذف",
                "هل أنت متأكد من حذف هذا التسجيل؟",
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
            )
            if confirm == QtWidgets.QMessageBox.Yes:
                self.notes_manager.delete_note(self.current_note['id'])
                self.load_notes()
                self.current_note = None
                self.note_content.clear()
                self.showMessage("تم حذف التسجيل", 2000)

    def show_ayah(self):
        if self.current_note:
            self.show_ayah_requested.emit(
                self.current_note['surah'], 
                self.current_note['ayah']
            )
            self.accept()

    def showMessage(self, message, timeout):
        QtWidgets.QToolTip.showText(
            self.mapToGlobal(QtCore.QPoint(0,0)),
            message,
            self,
            QtCore.QRect(),
            timeout
        )

    def showEvent(self, event):
        self.load_notes()
        super().showEvent(event)


class ShortsTableDelegate(QtWidgets.QStyledItemDelegate):
    def __init__(self, left=25, right=25, parent=None):
        super().__init__(parent)
        self.left = left
        self.right = right

    def paint(self, painter, option, index):
        # Make a copy of the option and adjust the rectangle for padding.
        new_option = QtWidgets.QStyleOptionViewItem(option)
        new_option.palette.setColor(QtGui.QPalette.HighlightedText, QColor("#000"))
        new_option.rect = option.rect.adjusted(self.left, 0, -self.right, 0)

        super().paint(painter, new_option, index)

class CompactHelpDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("اختصارات لوحة المفاتيح")
        self.resize(700, 600)
        self.init_ui()

    def init_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        
        # Create table with 2 columns
        self.table = QtWidgets.QTableWidget()
        self.table.setColumnCount(2)
        self.table.setLayoutDirection(QtCore.Qt.RightToLeft)
        self.table.setHorizontalHeaderLabels(["الاختصار", "الوظيفة"])
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        # Column 0 resizes to fit contents, column 1 stretches to fill the remaining space
        #self.table.horizontalHeader().setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QtWidgets.QHeaderView.Stretch)
        self.setStyleSheet("""
            font-family: Amiri;
            font-size: 14pt;
            color: #000;
        """)
        
        self.table.setItemDelegate(ShortsTableDelegate(15, 15, self.table))
        # Data structure:
        # For header rows, tuple: (True, "Category header text")
        # For normal rows, tuple: (False, (category, shortcut, function))
        rows = [
            (True, " لمزيد من التفاصيل : Ctrl + Shift + H"),
            (False,("","","")),

            (True, "التنقل والبحث"),
            (False, ("التنقل", "Ctrl + F", "الانتقال إلى حقل البحث")),
            (False, ("التنقل", "Ctrl + W", "التحول الى \"البحث بالسورة\" ثم الانتقال إلى حقل البحث")),
            (False, ("التنقل", "Ctrl + Shift + W", "التحول الى \"البحث بنطاق الآيات\" ثم الانتقال إلى حقل البحث")),
            (False, ("التنقل", "Ctrl + J", "الانتقال إلى سورة الآية المحددة")),
            (False, ("التنقل", "Ctrl + K", "العودة إلى سورة التشغيل الحالية")),
            (False, ("التنقل", "Ctrl + M", "العودة إلى السورة الحالية")),
            (False, ("التنقل", "← Left / Right →", "التنقل بين السور")),
            (False, ("التنقل", "↑ Up / Down ↓", "التنقل بين الآيات")),
            (False, ("التنقل", "Backspace", "العودة الى النتائج من سياق الآية")),
            (False, ("التنقل", "Ctrl + C", " نسخ الآيات المحددة")),
            (False, ("التنقل", "Ctrl + Shift + C", " نسخ جميع النتائج ")),

            (True, "التشغيل الصوتي"),
            (False, ("الصوت", "Space", "تلاوة الآية المحددة أو توقيف/تشغيل التلاوة")),
            (False, ("الصوت", "Ctrl + P", "تلاوة الآية و 5 بعدها")),
            (False, ("الصوت", "Ctrl + A", "تلاوة السورة كاملة و الاستمرار في تلاوة القرآن")),
            (False, ("الصوت", "Ctrl + Shift + P", "تلاوة جميع النتائج")),
            (False, ("الصوت", "Ctrl + R", "تكرار الإستماع لجميع النتائج")),
            (False, ("الصوت", "Ctrl + Shift + R", "تكرار الإستماع لجميع النتائج عددا محددا من المرات")),
            (False, ("الصوت", "Ctrl + S", "توقيف وإنهاء التلاوة")),
            
            (True, "إدارة الملاحظات"),
            (False, ("الملاحظات", "Ctrl + Shift + N", " إظهار نافذة إدارة الملاحظات")),
            (False, ("الملاحظات", "Ctrl + N", "ملاحظة جديدة")),
            (False, ("الملاحظات", "Ctrl + Alt + N", "ملاحظة جديدة")),
            (False, ("الملاحظات", "Ctrl + S", "حفظ الملاحظة")),
            (False, ("الملاحظات", "Delete", "حذف الملاحظة")),
            (False, ("الملاحظات", "Ctrl + E", "تصدير الملاحظات")),
            (False, ("الملاحظات", "Ctrl + I", "استيراد الملاحظات")),
            
            (True, "إدارة الدروس"),
            (False, ("الدروس", "Ctrl + Shift + T", "إظهار نافذة الدروس")),
            (False, ("الدروس", "← Left / Right →", "التنقل بين الدروس")),
            (False, ("الدروس", "↑ Up / Down ↓", "التنقل بين التسجيلات")),
            (False, ("الدروس", "Delete", "حذف التسجيل المحدد  ")),
            (False, ("الدروس", "Ctrl + Delete", "حذف الدرس الحالي  ")),
            (False, ("الدروس", "↑ Ctrl + Up / Ctrl + Down ↓", "تغيير ترتيب التسجيلات")),
            (False, ("الدروس", "Ctrl + T", "إضافة الآية المحددة إلى أحد الدروس")),
            
            (True, "إدارة المرجعيات"),
            (False, ("المرجعيات", "Ctrl + Shift + B", "فتح نافذة المرجعيات")),
            (False, ("المرجعيات", "Ctrl + B", "إضافة الآية المحددة الى قائمة المرجعيات")),
            (False, ("المرجعيات", "Delete", "حذف الآية المحددة من قائمة المرجعيات")),
            
            (True, "الإعدادات العامة"),
            (False, ("التخصيص", "Ctrl + D", "تبديل الوضع الليلي")),
            (False, ("المساعدة", "Ctrl + H", "إظهار نافذة اختصارات لوحة المفاتيح")),
            (False, ("المساعدة", "Ctrl + Shift + H", "إظهار نافذة المساعدة")),
            (False, ("التخصيص", "Esc", "تبديل نوع الخط : عثماني / مبسط")),
            (False, ("التخصيص", "Ctrl + =", "زيادة حجم الخط")),
            (False, ("التخصيص", "Ctrl + +", "زيادة حجم الخط")),
            (False, ("التخصيص", "Ctrl + -", "نقصان حجم الخط"))
        ]
        
        self.table.setRowCount(len(rows))
        
        # Colors: header rows get a distinct background.
        header_bg = QtGui.QColor("#5D6D7E")
        
        row_index = 0
        for is_header, data in rows:
            if is_header:
                # Create header row spanning both columns.
                item = QtWidgets.QTableWidgetItem(data)
                item.setBackground(header_bg)
                item.setTextAlignment(QtCore.Qt.AlignCenter)
                self.table.setItem(row_index, 0, item)
                self.table.setSpan(row_index, 0, 1, 2)
                row_index += 1
            else:
                # Only add the shortcut and function columns.
                category, shortcut, function = data
                item_short = QtWidgets.QTableWidgetItem("\u202A" + shortcut + "\u202C")
                item_short.setTextAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
                item_func = QtWidgets.QTableWidgetItem(function)
                self.table.setItem(row_index, 0, item_short)
                self.table.setItem(row_index, 1, item_func)
                row_index += 1

        layout.addWidget(self.table)
        close_btn = QtWidgets.QPushButton("إغلاق")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)


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
    _file_path = Path(resource_path(os.path.join("help", "help_ar.html")))
    
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



# =============================================================================
# Main application window
# =============================================================================
class QuranBrowser(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        icon_path = resource_path("icon.png")
        self.setWindowIcon(QtGui.QIcon(icon_path))
        self.search_engine = QuranSearch()
        QuranWordCache(self.search_engine)
        self.ayah_selector = None
        self.bookmark_dialog = None
        self.notes_dialog = None
        self.compact_help_dialog = None
        self.current_detail_result = None
        self._status_msg = ""
        self.temporary_message_active = False
        self.message_timer = QtCore.QTimer()
        self.message_timer.timeout.connect(self.revert_status_message)
        self.current_surah = 0
        self.current_start_ayah = 0
        self.sequence_files = []
        self.current_sequence_index = 0
        self.playing_one = False
        self.playing_context = 0
        self.playing_range = 0
        self.repeat_all = False
        self.repeat_count = 0
        self.max_repeats = 0
        self.playing_range_max = 0
        self.results_count_int = 0
        self.playing_ayah_range = False
        self.pending_scroll = None  
        self.scroll_retries = 0
        self.MAX_SCROLL_RETRIES = 5

        self.notes_manager = NotesManager()

        self.settings = QtCore.QSettings("MOSAID", "QuranSearch")
        self.theme_action = None
        self.init_ui()
        self.setup_connections()
        self.setup_menu()
        self.setup_shortcuts()
        self.load_settings()
        self.trigger_initial_search()
        self.player = QMediaPlayer()  # For audio playback
        self.player.mediaStatusChanged.connect(self.on_media_status_changed)

    def __del__(self):
        try:
            self.model.loading_complete.disconnect(self.handle_pending_scroll)
        except:
            pass

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
        self.model.loading_complete.connect(self.handle_pending_scroll, QtCore.Qt.UniqueConnection)
        self.results_view.setModel(self.model)
        self.delegate = None 
        self.results_view.setUniformItemSizes(False)
        self.results_view.activated.connect(self.show_detail_view)
        self.results_view.setWordWrap(True)
        self.results_view.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.results_view.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)  


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
        
        # Create container widget
        status_container = QtWidgets.QWidget()
        status_layout = QtWidgets.QHBoxLayout(status_container)
        status_layout.setContentsMargins(0, 0, 0, 0)
        status_layout.setSpacing(10)

        # Left section (fixed width)
        self.center_label = QtWidgets.QLabel()
        self.center_label.setFixedWidth(250)
        self.center_label.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
        self.center_label.setTextFormat(QtCore.Qt.RichText)
        self.center_label.setTextInteractionFlags(QtCore.Qt.TextBrowserInteraction)
        self.center_label.setOpenExternalLinks(True)
        status_layout.addWidget(self.center_label)
        self.center_label.setText("© 2025 MOSAID, <a href='https://mosaid.xyz/quran-search'>https://mosaid.xyz</a>")

        # Center section (fixed width)
        self.result_count = QtWidgets.QLabel()
        self.result_count.setAlignment(QtCore.Qt.AlignCenter)
        self.result_count.setFixedWidth(400)
        status_layout.addWidget(self.result_count)

        # Right section (fixed width)
        self.shortcuts_label = QtWidgets.QLabel()
        self.shortcuts_label.setFixedWidth(250)
        self.shortcuts_label.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        status_layout.addWidget(self.shortcuts_label)
        self.shortcuts_label.setText("Help: Ctrl+H")

        # Add container to status bar
        self.status_bar.addPermanentWidget(status_container, 1)
        
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
        if not self.temporary_message_active:
            self.result_count.setText(f"{self.results_count_int} نتائج، {self._status_msg}")
            self.result_count.setStyleSheet("")


    def setup_shortcuts(self):
        QtWidgets.QShortcut(QtGui.QKeySequence("Space"), self, activated=self.handle_space)
        QtWidgets.QShortcut(QtGui.QKeySequence("Escape"), self, activated=self.toggle_version)
        QtWidgets.QShortcut(QtGui.QKeySequence("Backspace"), self, activated=self.handle_backspace)
        QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+F"), self, activated=self.input_focus)
        QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+D"), self, activated=self.toggle_theme)
        QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+P"), self, activated=self.handle_ctrlp)
        #QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+R"), self, activated=self.handle_ctrlr)
        QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+R"), self, activated=self.handle_repeat_all_results)
        QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+Shift+R"), self, 
                            activated=lambda: self.handle_repeat_all_results(limited=True))
        QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+S"), self, activated=self.handle_ctrls)
        QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+W"), self, activated=self.handle_ctrlw)
        QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+Shift+W"), self, activated=self.handle_ctrlsw)
        QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+A"), self.results_view, activated=self.play_current_surah)
        QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+M"), self, activated=self.backto_current_surah)
        QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+Shift+H"), self, activated=self.show_help_dialog)
        QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+H"), self, activated=self.show_compact_help)
        QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+J"), self, activated=self.handle_ctrlj)
        QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+K"), self, activated=self.load_surah_from_current_playback)
        QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+N"), self, activated=self.new_note)
        QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+Shift+N"), self, activated=self.show_notes_manager)
        QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+E"), self, activated=self.export_notes)
        QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+I"), self, activated=self.import_notes)
        QtWidgets.QShortcut(QtGui.QKeySequence("Delete"), self, activated=self.delete_note)
        QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+Shift+P"), self, activated=self.play_all_results)
        QtWidgets.QShortcut(QtGui.QKeySequence("Left"), self, activated=self.navigate_surah_left)
        QtWidgets.QShortcut(QtGui.QKeySequence("Right"), self, activated=self.navigate_surah_right)
        QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+Shift+T"), self, activated=self.show_ayah_selector)
        QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+T"), self, activated=self.add_ayah_to_course)
        QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+Shift+B"), self, activated=self.show_bookmarks)
        QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+B"), self, activated=self.bookmark_current_ayah)
        QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+="), self, activated=self.increase_font_size)  # Ctrl++
        QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl++"), self, activated=self.increase_font_size) 
        QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+-"), self, activated=self.decrease_font_size)
        QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+MouseWheelUp"), self, activated=self.increase_font_size)
        QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+MouseWheelDown"), self, activated=self.decrease_font_size)
        QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+Shift+C"), self, activated=self.copy_all_results)
        QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+C"), self, activated=self.copy_selected_results)
        QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+Alt+N"), self, activated=self.show_quick_note_dialog)

    def increase_font_size(self):
        new_size = self.delegate.base_font_size + 1
        if new_size <= 38:
            self.delegate.update_font_size(new_size)
            self.results_view.reset()
            self.showMessage(f"Font size: {self.delegate.base_font_size}",2000)

    def decrease_font_size(self):
        new_size = self.delegate.base_font_size - 1
        if new_size >= 10:
            self.delegate.update_font_size(new_size)
            self.results_view.reset()
            self.showMessage(f"Font size: {self.delegate.base_font_size}",2000)


    def copy_selected_results(self):
        """Copy selected results to clipboard with verse references"""
        selected = self.results_view.selectionModel().selectedIndexes()
        
        if not selected:
            self.showMessage("No verses selected", 3000, bg="red")
            return
            
        version = self.get_current_version()
        text_list = []
        
        for index in selected:
            result = self.model.data(index, Qt.UserRole)
            if result:
                # Remove span tags
                raw_text = result.get(f'text_{version}', '')
                clean_text = re.sub(r'<span[^>]*>|</span>', '', raw_text)
                
                surah_num = result.get('surah', '')
                ayah = result.get('ayah', '')
                chapter = self.search_engine.get_chapter_name(surah_num)
                text_list.append(f"{clean_text} ({chapter} {ayah})")

        full_text = "\n".join(text_list)
        clipboard = QtWidgets.QApplication.clipboard()
        clipboard.setText(full_text)
        self.showMessage(f"Copied {len(selected)} selected verses", 3000)



    def copy_all_results(self):
        """Copy all search results to clipboard with verse references (without span tags)"""
        if not self.model.results:
            self.showMessage("No results to copy", 3000, bg="red")
            return
            
        version = self.get_current_version()
        text_list = []
        
        for result in self.model.results:
            # Remove span tags using regular expression
            raw_text = result.get(f'text_{version}', '')
            clean_text = re.sub(r'<span[^>]*>|</span>', '', raw_text)
            
            surah_num = result.get('surah', '')
            ayah = result.get('ayah', '')
            chapter = self.search_engine.get_chapter_name(surah_num)
            text_list.append(f"{clean_text} ({chapter} {ayah})")
        
        full_text = "\n".join(text_list)
        clipboard = QtWidgets.QApplication.clipboard()
        clipboard.setText(full_text)
        self.showMessage("Copied all results to clipboard", 3000)

    def new_note(self):
        if self.detail_view.isVisible():
            self.detail_view.notes_widget.new_note()

    def show_notes_manager(self):
        if not self.notes_dialog:
            self.notes_dialog = NotesManagerDialog(self.notes_manager, self.search_engine, self)
            self.notes_dialog.show_ayah_requested.connect(self.load_and_show_ayah)
        self.notes_dialog.show()

    def load_and_show_ayah(self, surah, ayah):
        self.load_surah_from_current_ayah(surah, ayah)
        self.show_results_view()

    def show_compact_help(self):
        if not self.compact_help_dialog:
            self.compact_help_dialog = CompactHelpDialog(self)
        self.compact_help_dialog.show()

    def delete_note(self):
        if self.detail_view.isVisible():
            self.detail_view.notes_widget.delete_note()

    def showMessage(self, message, timeout=3000, bg="#4CAF50"):
        """Temporarily override the left status label"""
        # Cancel any pending reverts
        self.message_timer.stop()
        
        # Store current permanent text if not already in override
        if not self.temporary_message_active:
            self.original_style = self.result_count.styleSheet()
            
        self.temporary_message_active = True
        self.result_count.setText(message)
        self.result_count.setStyleSheet(f"background: {bg}; color: black;")  # Visual distinction
        
        if timeout > 0:
            self.message_timer.start(timeout)

    def revert_status_message(self):
        """Revert to permanent status message"""
        self.message_timer.stop()
        self.temporary_message_active = False
        self.status_msg = ""
        self.result_count.setStyleSheet(self.original_style)

    def show_ayah_selector(self):
        if not self.ayah_selector:
            self.ayah_selector = AyahSelectorDialog(self.notes_manager, self)
            self.ayah_selector.play_requested.connect(self.play_ayah_range)
            self.ayah_selector.search_requested.connect(self.handle_course_search)
        self.ayah_selector.show()

    def handle_course_search(self, query):
        self.search_input.setText(query)
        self.search()

    def show_quick_note_dialog(self):
        index = self.results_view.currentIndex()
        if not index.isValid():
            self.showMessage("No verse selected", 3000, bg="red")
            return
        
        result = self.model.data(index, Qt.UserRole)
        if not result:
            return
        
        try:
            surah = int(result['surah'])
            ayah = int(result['ayah'])
        except (KeyError, ValueError):
            self.showMessage("Invalid verse data", 3000, bg="red")
            return
        
        if not hasattr(self, 'note_dialog'):
            self.note_dialog = NoteDialog(self)
            self.note_dialog.accepted.connect(self.save_quick_note)
        
        self.note_dialog.surah = surah
        self.note_dialog.ayah = ayah
        self.note_dialog.chapter = self.search_engine.get_chapter_name(surah)
        self.note_dialog.editor.clear()
        
        # Update the label with the desired text
        self.note_dialog.info_label.setText(
            f"إضافة تسجيل الى الآية {ayah} من سورة {self.note_dialog.chapter}"
        )
        
        self.note_dialog.show()
        self.note_dialog.raise_()
        self.note_dialog.activateWindow()


    def save_quick_note(self):
        content = self.note_dialog.editor.toPlainText().strip()
        if not content:
            return
        
        self.notes_manager.add_note(
            self.note_dialog.surah,
            self.note_dialog.ayah,
            content
        )
        
        # Refresh notes if detail view is visible
        if self.detail_view.isVisible():
            self.detail_view.notes_widget.load_notes()
        
        self.showMessage("Note saved successfully", 2000)

    def play_ayah_range(self, surah, start, end):
        #self.showMessage(f"{surah}:{start}--{end}", 5000)
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
                    self.showMessage("No audio files found for selection", 5000, bg="red")
        except Exception as e:
            logging.error(f"Error playing ayah range: {str(e)}")
            self.showMessage("Error playing selection", 5000, bg="red")

    def setup_menu(self):
        menu = self.menuBar().addMenu("&Menu")
        self.theme_action = QtWidgets.QAction("Dark Mode", self, checkable=True)
        self.theme_action.toggled.connect(self.update_theme_style)
        menu.addAction(self.theme_action)
        
        # Initialize delegate now that theme_action exists
        self.delegate = QuranDelegate(parent=self.results_view, 
                                    is_dark=self.theme_action.isChecked())
        self.results_view.setItemDelegate(self.delegate)

        # New action: Set Audio Directory.
        audio_dir_action = QtWidgets.QAction("Set Audio Directory", self)
        audio_dir_action.triggered.connect(self.choose_audio_directory)
        menu.addAction(audio_dir_action)

        # bookmark action
        bookmark_action = QtWidgets.QAction("Bookmark Manager", self)
        bookmark_action.triggered.connect(self.show_bookmarks)
        menu.addAction(bookmark_action)

        # notes manager
        notes_action = QtWidgets.QAction("Notes Manager", self)
        notes_action.triggered.connect(self.show_notes_manager)
        menu.addAction(notes_action)

        # bookmark action
        course_action = QtWidgets.QAction("Course Manager", self)
        course_action.triggered.connect(self.show_ayah_selector)
        menu.addAction(course_action)

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
                self.showMessage(f"Notes exported to {file_path}", 5000)
            except Exception as e:
                self.showMessage(f"Export failed: {str(e)}", 5000, bg="red")

    def import_notes(self):
        """Handles importing notes from a CSV file."""
        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Import Notes", "", "CSV Files (*.csv)")
        if file_path:
            try:
                imported, duplicates, errors = self.notes_manager.import_from_csv(file_path)
                msg = f"Imported {imported} notes. Skipped {duplicates} duplicates. {errors} errors."
                self.showMessage(msg, 7000)

                # Refresh notes display if detail view is visible
                if self.detail_view.isVisible():
                    self.detail_view.notes_widget.load_notes()
            except ValueError as e:
                self.showMessage(str(e), 7000, bg="red")
            except Exception as e:
                self.showMessage(f"Import failed: {str(e)}", 7000, bg="red")
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
            self.showMessage(f"Audio directory set to: {chosen_dir}", 3000)


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
            self.showMessage("Error loading surah", 3000, bg="red")
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
                self.showMessage("No verse selected", 2000, bg="red")
                return

            result = self.model.data(index, Qt.UserRole)
            try:
                surah = int(result.get('surah'))
                selected_ayah = int(result.get('ayah'))
            except Exception as e:
                self.showMessage("Invalid surah/ayah information", 3000, bg="red")
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
            self.pending_scroll = (surah, selected_ayah)
            self.scroll_retries = 0
            try:
                self.model.loading_complete.disconnect(self.handle_pending_scroll)
            except TypeError:
                pass  # No connection existed
            
            # Create fresh connection
            self.model.loading_complete.connect(
                self.handle_pending_scroll, 
                QtCore.Qt.UniqueConnection
            )
        except Exception as e:
            logging.exception("Error loading surah")
            self.showMessage("Error loading surah", 3000, bg="red")
            return

        # Show the results view.
        self.show_results_view()


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

    def backto_current_surah(self):
        self.handle_surah_selection(self.current_surah-1)
        current_ayah = self.current_start_ayah + self.current_sequence_index -1
        self._scroll_to_ayah(self.current_surah,current_ayah)

    def load_surah_from_current_playback(self):
        """
        If a playback sequence is active, use its current surah and the
        last played (or currently playing) ayah to load that surah and scroll to it.
        Bind this method to Ctrl+K.
        """
        current_media = self.player.media()
        if current_media is not None:
            url = current_media.canonicalUrl()
            if url.isLocalFile():
                file_path = url.toLocalFile()
                current_surah = int(os.path.basename(file_path)[:3])
                current_ayah = int(os.path.basename(file_path)[3:6])
                self.load_surah_from_current_ayah(surah=current_surah, selected_ayah=current_ayah)

    # def focus_notes(self):
    #     if self.detail_view.isVisible():
    #         self.detail_view.notes_widget.editor.setFocus()

    def search(self):
        if self.detail_view.isVisible():
            self.show_results_view()

        query = self.search_input.text().strip()
        method = self.search_method_combo.currentText()
        if not query and method == "Text":
            self.showMessage("Please enter a search query", 3000, bg="red")
            return
        self.search_input.update_history(query)
        self.showMessage("Searching...", 2000)

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
        is_dark = self.theme_action.isChecked()
        self.search_worker = SearchWorker(
            search_engine=self.search_engine,
            method=method,
            query=query,
            is_dark_theme=is_dark,  
            parent=self
        )
        self.search_worker.results_ready.connect(self.handle_search_results)
        self.search_worker.error_occurred.connect(lambda error: self.showMessage(f"Search error: {error}", 3000, bg="red"))
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
        # Force immediate scroll check
        QtCore.QTimer.singleShot(500, self.handle_pending_scroll)

    def show_detail_view(self, index):
        if isinstance(index, QtCore.QModelIndex):
            result = self.model.data(index, Qt.UserRole)
        else:
            result = None
        if result:
            self.current_detail_result = result
            version = self.get_current_version()
            is_dark_theme = self.theme_action.isChecked()
            self.update_theme_style(is_dark_theme)
            self.detail_view.display_ayah(result, self.search_engine, version,is_dark_theme)
            self.detail_view.show()
            self.results_view.hide()

    def input_focus(self):
        self.search_input.setFocus()
        self.search_input.selectAll()

    def handle_backspace(self):
        # Switch to results view if in detail view
        if self.detail_view.isVisible():
            self.show_results_view()
        
        # Get current selection
        index = self.results_view.currentIndex()
        if not index.isValid():
            return

        result = self.model.data(index, Qt.UserRole)
        if not result:
            return

        try:
            surah = int(result.get('surah'))
            ayah = int(result.get('ayah'))
        except (ValueError, TypeError):
            return

        # Direct scroll without loading logic
        QtCore.QTimer.singleShot(50, lambda: self._scroll_to_ayah_immediate(surah, ayah))

    def _scroll_to_ayah_immediate(self, surah, ayah):
        # Search through all loaded items
        for row in range(self.model.rowCount()):
            index = self.model.index(row, 0)
            result = self.model.data(index, Qt.UserRole)
            if result and result['surah'] == surah and result['ayah'] == ayah:
                self.results_view.setCurrentIndex(index)
                self.results_view.scrollTo(index, 
                    QtWidgets.QAbstractItemView.PositionAtCenter)
                break


    def show_results_view(self):
        self.detail_view.hide()
        self.results_view.show()
        self.results_view.setFocus()

    def handle_space(self):
        # Check if player has media loaded and is in a playable state
        if self.player.mediaStatus() != QMediaPlayer.NoMedia:
            if self.player.state() == QMediaPlayer.PlayingState:
                # Pause if currently playing
                self.player.pause()
                self.showMessage("Playback paused", 2000)
                self.status_msg = "Paused"
            else:
                # Resume if paused or stopped
                self.player.play()
                self.showMessage("Playback resumed", 2000)
                self.status_msg = "Resumed"
        else:
            # Original behavior - start new playback
            self.playing_one = True
            self.playing_context = 0
            self.playing_range = 0
            self.status_msg = ""
            self.play_current()
            
        # Force UI update
        #self.updatePermanentStatus()

    def handle_ctrlp(self):
        self.playing_context = 1
        self.status_msg = "إستماع الى الأية وخمسة بعدها"
        self.play_current(count=6)

    def handle_ctrlr(self):
        method = self.search_method_combo.currentText()
        if not method == "Surah FirstAyah LastAyah":
            self.showMessage("Please select a range to repeat using 'Surah FirstAyah LastAyah' search method", 10000, bg="red")
            return
        self.playing_range = 1
        self.playing_range_max = self.results_count_int
        self.play_current(count=self.playing_range_max)

    def handle_repeat_all_results(self, limited=False):
        """Handle repeating with optional limit"""
        if limited:
            # Get repeat count from user
            count, ok = QtWidgets.QInputDialog.getInt(
                self, 
                "Repeat Settings",
                "Number of repeats:",
                value=2, min=1, max=100, step=1
            )
            
            if not ok or count < 1:
                self.showMessage("Invalid repeat count", 2000, bg="red")
                return
                
            self.max_repeats = count
            self.repeat_count = 0
            self.showMessage(f"Repeating {self.max_repeats} times", 3000)
        else:
            # Original infinite repeat behavior
            self.max_repeats = 0  
            self.repeat_count = 0
            self.showMessage("Repeating all results continuously", 3000)
        
        # Common playback start logic
        self.repeat_all = True
        self.play_all_results()

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
            self.showMessage("Error changing search mode", 3000, bg="red")
    
    def handle_ctrlsw(self):
        """Handle Ctrl+shift+w: Set search method to Surah and focus search input"""
        try:
            # Set search method to "Surah"
            index = self.search_method_combo.findText("Surah FirstAyah LastAyah", QtCore.Qt.MatchFixedString)
            if index >= 0:
                self.search_method_combo.setCurrentIndex(index)

            # Focus and select all text in search input
            self.search_input.setFocus()
            self.search_input.selectAll()

            # Optional: Trigger search if needed
            # self.search()

        except Exception as e:
            logging.error(f"Error in handle_ctrlsw: {str(e)}")
            self.showMessage("Error changing search mode", 3000, bg="red")

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
                self.showMessage("No verse selected", 7000, bg="red")
                return
            result = self.model.data(index, Qt.UserRole)
            try:
                surah = int(result.get('surah'))
                ayah = int(result.get('ayah'))
            except Exception as e:
                self.showMessage("Invalid verse data", 2000, bg="red")
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
                self.showMessage(f"Playing audio for Surah {surah}, Ayah {ayah}", 2000)
            else:
                self.showMessage("Audio file not found", 3000, bg="red")
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
                self.showMessage(f"Audio file not found: {file_path}", 2000, bg="red")
                break

        if not self.sequence_files:
            self.showMessage("No audio files found for sequence", 3000, bg="red")
            return

        # Initialize sequence index and start playback.
        self.current_sequence_index = 0
        self.play_next_file()

    def play_all_results(self):
        """Play all verses in the current search results list."""
        if not self.model.results:
            self.showMessage("No results to play", 3000, bg="red")
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
                self.showMessage(f"Audio not found: Surah {surah} Ayah {ayah}", 3000, bg="red")

        if self.sequence_files:
            index = self.results_view.currentIndex()
            self.current_sequence_index = 0
            if index.isValid():
                result = self.model.data(index, Qt.UserRole)
                try:
                    surah = int(result.get('surah'))
                    ayah = int(result.get('ayah'))
                    expected_filename = f"{surah:03d}{ayah:03d}.mp3"
                    # Iterate over the list of sequence files to find a match
                    for idx, file_path in enumerate(self.sequence_files):
                        if os.path.basename(file_path) == expected_filename:
                            self.current_sequence_index = idx
                            break
                except Exception as e:
                    pass
            self.playing_ayah_range = True
            self.showMessage(f"Playing {len(self.sequence_files)} results...", 3000)
            self.play_next_file()
        else:
            self.showMessage("No audio files found in results", 3000, bg="red")

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
            if self.repeat_all or self.playing_range:
                self.status_msg += " repeating"
                if self.max_repeats > 0:
                    self.status_msg += f" ({self.repeat_count+1}/{self.max_repeats}) "
            # Continue playing the current surah.
            url = QUrl.fromLocalFile(file_path)
            self.player.setMedia(QMediaContent(url))
            self.player.play()

            # Calculate the current ayah being played.
            if self.results_view.isVisible():
                self._scroll_to_ayah(current_surah, current_ayah)
            self.current_sequence_index += 1
        else:
#             print(
#                 f"""
#                 self.playing_one : {self.playing_one}\n
#                 self.playing_context: {self.playing_context}\n
#                 self.playing_range: {self.playing_range}\n
#                 self.playing_ayah_range: {self.playing_ayah_range}\n
#                 self.current_surah : {self.current_surah }\n
#                 self.current_start_ayah: {self.current_start_ayah}\n
#                 self.current_sequence_index: {self.current_sequence_index}\n
#                 self.repeat_all: {self.repeat_all}\n
# ==============================================================================\n
#                 """
#             )
            if self.repeat_all: 
                if self.max_repeats > 0:
                    self.repeat_count += 1
                    if self.repeat_count >= self.max_repeats:
                        self.repeat_all = False
                        self.repeat_count = 0
                        self.max_repeats = 0
                        self.showMessage("Repeat limit reached", 3000)
                        return
                self.current_sequence_index = 0
                self.play_next_file()
                return 
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
                    self.current_sequence_index = 0
                self.play_next_file()
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
                self.showMessage(f"Moving to surah {self.current_surah}", 5000)
                self.play_next_file()  # Start playback of the new surah.
            else:
                self.showMessage(f"No audio files found for surah {self.current_surah}. Playback finished.", 2000)
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


    def handle_pending_scroll(self):
        if not self.pending_scroll:
            return
            
        surah, ayah = self.pending_scroll
        found = self._scroll_to_ayah(surah, ayah)
        
        if not found and self.scroll_retries < self.MAX_SCROLL_RETRIES:
            self.scroll_retries += 1
            # Load more results and try again
            self.model.load_remaining_results()
            QtCore.QTimer.singleShot(100, self.handle_pending_scroll)
        else:
            self.pending_scroll = None
            self.scroll_retries = 0
            try:
                self.model.loading_complete.disconnect(self.handle_pending_scroll)
            except TypeError:
                pass 

    def _scroll_to_ayah(self, surah, ayah):
        """Enhanced scroll function with progressive loading"""
        self.results_view.selectionModel().clearSelection()
        # First try existing items
        for row in range(self.model.rowCount()):
            index = self.model.index(row, 0)
            result = self.model.data(index, Qt.UserRole)
            if (result['surah'] == surah and 
                result['ayah'] == ayah):
                self.results_view.setCurrentIndex(index)
                self.results_view.scrollTo(index, 
                    QtWidgets.QAbstractItemView.PositionAtCenter)
                return True
                
        # If not found, check if more results need loading
        if self.model._displayed_results < len(self.model.results):
            self.model.load_remaining_results()
            
        return False


    def stop_playback(self):
        """Stop any current audio playback."""
        self.repeat_all = False
        self.player.stop()
        self.player.setMedia(QMediaContent())  # Clear current media
        self.showMessage("Playback stopped", 2000)

    def play_current_surah(self):
        """
        Play the entire surah of the currently selected verse.
        This method works only in the results view.
        It builds a sequence from ayah 1 upward until no file is found,
        then starts playback at the currently selected ayah.
        """
        # Ensure we are in results view.
        if not self.results_view.isVisible():
            self.showMessage("Switch to results view to play current surah", 2000, bg="red")
            return

        index = self.results_view.currentIndex()
        if not index.isValid():
            self.showMessage("No verse selected", 2000, bg="red")
            return

        result = self.model.data(index, Qt.UserRole)
        try:
            surah = int(result.get('surah'))
            selected_ayah = int(result.get('ayah'))
        except Exception as e:
            self.showMessage("Invalid surah or ayah information", 2000, bg="red")
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
            self.showMessage("No audio files found for current surah", 3000, bg="red")
            return

        # Store the sequence and initialize the index.
        self.current_surah = surah
        self.sequence_files = sequence_files
        self.playing_ayah_range = False
        self.current_start_ayah = 1  # Our sequence is built from ayah 1.
        # Set the current sequence index to the selected ayah (adjusted for 0-based indexing).
        self.current_sequence_index = selected_ayah -1

        # Sanity check: if the selected ayah is out of range, default to 0.
        if self.current_sequence_index < 0 or self.current_sequence_index >= len(sequence_files):
            self.current_sequence_index = 0

        self.play_next_file()  # This method will chain playback for the sequence.

    def add_ayah_to_course(self):
        index = self.results_view.currentIndex()
        if not index.isValid():
            self.showMessage("No verse selected", 3000, bg="red")
            return
            
        result = self.model.data(index, Qt.UserRole)
        try:
            surah = int(result['surah'])
            ayah = int(result['ayah'])
        except (KeyError, ValueError):
            self.showMessage("Invalid verse data", 3000, bg="red")
            return

        dialog = CourseSelectionDialog(self.notes_manager, self)
        if dialog.exec_() == QtWidgets.QDialog.Accepted:
            course_id = dialog.get_selected_course()
            if course_id:
                self._add_to_course(course_id, surah, ayah)
                self.show_ayah_selector()
                self.ayah_selector.load_course_by_id(course_id)

    def _add_to_course(self, course_id, surah, ayah):
        # Get existing course data
        courses = self.notes_manager.get_all_courses()
        course = next((c for c in courses if c[0] == course_id), None)
        if not course:
            return

        # Create new item entry
        new_entry = {
            "text": f"Surah {surah}: Ayah {ayah}",
            "user_data": {
                "type": "ayah",
                "surah": surah,
                "start": ayah,
                "end": ayah
            }
        }

        # Update course items
        _, title, items = course
        updated_items = items.copy()
        updated_items.append(json.dumps(new_entry))

        # Save updated course
        self.notes_manager.save_course(course_id, title, updated_items)
        self.showMessage(f"Added to course: {title}", 3000)


    def bookmark_current_ayah(self):
        index = self.results_view.currentIndex()
        if index.isValid():
            result = self.model.data(index, Qt.UserRole)
            if result:
                self.notes_manager.add_bookmark(result['surah'], result['ayah'])
                self.showMessage("تم حفظ الآية في المرجعية", 2000)

    def show_bookmarks(self):
        if not hasattr(self, 'bookmark_dialog') or not self.bookmark_dialog:
            self.bookmark_dialog = BookmarkDialog(self)
            self.bookmark_dialog.list_view.doubleClicked.connect(self.load_and_close_dialog)
        
        self.bookmark_dialog.show()
        self.bookmark_dialog.raise_()
        self.bookmark_dialog.activateWindow()

    def load_and_close_dialog(self):
        self.load_selected_bookmark()
        self.bookmark_dialog.hide()

    def load_selected_bookmark(self):
        index = self.bookmark_dialog.list_view.currentIndex()
        if index.isValid():
            bookmark = self.bookmark_dialog.model.data(index, QtCore.Qt.UserRole)
            self.load_surah_from_current_ayah(
                surah=bookmark['surah'],
                selected_ayah=bookmark['ayah']
            )

    def handle_ctrlj(self):
        index = self.results_view.currentIndex()
        if not index.isValid():
            self.showMessage("No verse selected", 2000,bg="red")
            return

        result = self.model.data(index, Qt.UserRole)
        try:
            surah = int(result.get('surah'))
            selected_ayah = int(result.get('ayah'))
        except Exception as e:
            self.showMessage("Invalid surah/ayah information", 3000, bg="red")
            return
        self.load_surah_from_current_ayah(
            surah=surah,
            selected_ayah=selected_ayah
        )

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
        splitter_handle = """
        QSplitter::handle {{
            background: {background};
            border: 1px solid {border_color};
            margin: 2px;
        }}
        QSplitter::handle:hover {{
            background: {hover_color};
        }}
        """

        if dark:
            style = f"""
            QWidget {{
                background: #333333;
                color: #FFFFFF;
            }}
            {splitter_handle.format(
                background="#555555",
                border_color="#444444",
                hover_color="#666666"
            )}
            QListView {{
                background: #1e1e1e;
            }}
            QLineEdit {{
                background: #222222;
            }}
            """
        else:
            style = f"""
            {splitter_handle.format(
                background="#cccccc",
                border_color="#aaaaaa",
                hover_color="#999999"
            )}
            """
        
        self.setStyleSheet(style)
        self.delegate.update_theme(dark)
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


    # Then modify your show_help_dialog method:
    def show_help_dialog(self):
        if not hasattr(self, '_help_dialog'):
            self._help_dialog = HelpDialog(self)
            
        if self._help_dialog.isVisible():
            self._help_dialog.hide()
        else:
            self._help_dialog.show()
            self._help_dialog.raise_()
            self._help_dialog.activateWindow()

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

