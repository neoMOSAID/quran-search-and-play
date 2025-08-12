import sqlite3
from pathlib import Path
from datetime import datetime
import json

from PyQt5.QtCore import QStandardPaths


class DbManager:
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
                    id INTEGER PRIMARY KEY,
                    title TEXT,
                    items TEXT,  
                    created DATETIME,
                    modified DATETIME
                );
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
            # Add pinned_groups table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS pinned_groups (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    active BOOLEAN DEFAULT 0,
                    created TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Modify pinned_verses table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS pinned_verses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    surah INTEGER NOT NULL,
                    ayah INTEGER NOT NULL,
                    group_id INTEGER NOT NULL,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(group_id) REFERENCES pinned_groups(id) ON DELETE CASCADE
                )
            """)
            # enforce uniqueness (idempotent)
            conn.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS ux_pinned_verses_surah_ayah_group
                ON pinned_verses (surah, ayah, group_id)
            """)
            # Create default group if none exists
            conn.execute("""
                INSERT OR IGNORE INTO pinned_groups (name, active) 
                VALUES ('Default', 1)
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
        """Save course with new structure"""
        with sqlite3.connect(str(self.db_path)) as conn:
            items_json = json.dumps(items, sort_keys=True)  # Add sort_keys=True
            if course_id:
                conn.execute("""
                    UPDATE courses SET 
                        title = ?,
                        items = ?,
                        modified = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (title, items_json, course_id))
                return course_id
            else:
                cursor = conn.execute("""
                    INSERT INTO courses (title, items, created, modified)
                    VALUES (?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """, (title, items_json))
                return cursor.lastrowid

    def get_course(self, course_id):
        """Get course with full structure"""
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.execute("""
                SELECT title, items,created,modified FROM courses WHERE id = ?
            """, (course_id,))
            row = cursor.fetchone()
            return {
                'id': course_id,
                'title': row[0],
                'items': json.loads(row[1]),
                'created': row[2],
                'modified': row[3]
            }
                            
    def create_new_course(self, title=None):
        """Create a new empty course with deduplicated title"""
        base_title = "New Course" if not title else title
        counter = 1
        new_title = base_title
        
        while True:
            # Check both title and content
            if not any(c[1] == new_title for c in self.get_all_courses()):
                break
            new_title = f"{base_title} ({counter})"
            counter += 1
            
        return self.save_course(None, new_title, [])

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

    def items_exist(self, items):
        """Check if course items already exist in any course (regardless of title)"""
        items_json = json.dumps(items, sort_keys=True, ensure_ascii=False)
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM courses WHERE items = ?", (items_json,))
            return cursor.fetchone()[0] > 0

    
    # Pinned verses ----------------------------------------------------
    def is_pinned(self, surah, ayah, group_id=None):
        """Check if a (surah, ayah) is pinned in given group or in active group if group_id is None."""
        if group_id is None:
            group_id = self.get_active_group_id()
            if group_id is None:
                return False
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.execute(
                "SELECT COUNT(*) FROM pinned_verses WHERE surah=? AND ayah=? AND group_id=?",
                (surah, ayah, group_id)
            )
            return cursor.fetchone()[0] > 0

    def add_pinned_verse(self, surah, ayah, group_id=None):
        """
        Add a pinned verse to a group. Returns True if added or already exists, False on error.
        If group_id is None, use active group.
        """
        if group_id is None:
            group_id = self.get_active_group_id()
            if group_id is None:
                return False

        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute("PRAGMA foreign_keys = ON")
            try:
                # Use INSERT OR IGNORE to be idempotent; unique index enforces uniqueness.
                conn.execute(
                    "INSERT OR IGNORE INTO pinned_verses (surah, ayah, group_id) VALUES (?, ?, ?)",
                    (surah, ayah, group_id)
                )
                conn.commit()
                # Return True if row exists now
                return self.is_pinned(surah, ayah, group_id)
            except sqlite3.Error as e:
                print(f"Error adding pinned verse: {e}")
                return False
        
    def remove_pinned_verse(self, surah, ayah, group_id=None):
        """
        Remove a pinned verse from a group. If group_id is None, remove from active group.
        Returns True on success (even if row didn't exist), False on DB error.
        """
        if group_id is None:
            group_id = self.get_active_group_id()
            if group_id is None:
                return False
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute("PRAGMA foreign_keys = ON")
            try:
                conn.execute(
                    "DELETE FROM pinned_verses WHERE surah=? AND ayah=? AND group_id=?",
                    (surah, ayah, group_id)
                )
                conn.commit()
                return True
            except sqlite3.Error as e:
                print(f"Error removing pinned verse: {e}")
                return False
    
    # Add to DbManager class
    def create_pinned_group(self, name):
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute("PRAGMA foreign_keys = ON")
            try:
                cursor = conn.execute(
                    "INSERT INTO pinned_groups (name) VALUES (?)",
                    (name,)
                )
                return cursor.lastrowid
            except sqlite3.IntegrityError:
                return None

    def delete_pinned_group(self, group_id):
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute("PRAGMA foreign_keys = ON")
            conn.execute(
                "DELETE FROM pinned_groups WHERE id = ?",
                (group_id,)
            )
            
    def rename_pinned_group(self, group_id, new_name):
        """Rename a pinned group"""
        with sqlite3.connect(str(self.db_path)) as conn:
            try:
                conn.execute(
                    "UPDATE pinned_groups SET name = ? WHERE id = ?",
                    (new_name, group_id)
                )
                return True
            except sqlite3.IntegrityError:
                # Name already exists
                return False

    def get_pinned_groups(self):
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.execute(
                "SELECT id, name, active FROM pinned_groups ORDER BY created DESC"
            )
            return [{
                'id': row[0],
                'name': row[1],
                'active': bool(row[2])
            } for row in cursor]

    def set_active_group(self, group_id):
        with sqlite3.connect(str(self.db_path)) as conn:
            # Deactivate all groups
            conn.execute("UPDATE pinned_groups SET active = 0")
            # Activate selected group
            conn.execute(
                "UPDATE pinned_groups SET active = 1 WHERE id = ?",
                (group_id,)
            )

    def get_active_group_id(self):
        """Return active group id or None"""
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.execute("SELECT id FROM pinned_groups WHERE active = 1 LIMIT 1")
            row = cursor.fetchone()
            return row[0] if row else None

    def get_active_pinned_verses(self):
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.execute("""
                SELECT pv.surah, pv.ayah, pv.timestamp
                FROM pinned_verses pv
                JOIN pinned_groups pg ON pv.group_id = pg.id
                WHERE pg.active = 1
                ORDER BY pv.timestamp DESC
            """)
            return [{
                'surah': row[0],
                'ayah': row[1],
                'timestamp': row[2]
            } for row in cursor]

    # Add to DbManager
    def get_pinned_verses_by_group(self, group_id):
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.execute("""
                SELECT surah, ayah, timestamp 
                FROM pinned_verses 
                WHERE group_id = ?
                ORDER BY timestamp DESC
            """, (group_id,))
            return [{
                'surah': row[0],
                'ayah': row[1],
                'timestamp': row[2]
            } for row in cursor]