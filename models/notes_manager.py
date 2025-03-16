import sqlite3
from pathlib import Path
from datetime import datetime
import json

from PyQt5.QtCore import QStandardPaths


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

    def course_exists(self, title, items):
        items_json = json.dumps(items, sort_keys=True)
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.execute("""
                SELECT COUNT(*) 
                FROM courses 
                WHERE title = ? AND items = ?
            """, (title, items_json))
            return cursor.fetchone()[0] > 0


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


