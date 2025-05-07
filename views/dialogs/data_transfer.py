
import json
import zipfile
from functools import partial
from datetime import datetime

from PyQt5 import QtWidgets, QtCore, QtGui
from utils.settings import AppSettings


class DataTransferDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.operation_in_progress = False
        self.app_settings = AppSettings() 
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("Data Transfer")
        self.setMinimumSize(600, 400)
        layout = QtWidgets.QVBoxLayout()
        
        # Progress Area
        self.progress_area = QtWidgets.QTextEdit()
        self.progress_area.setReadOnly(True)
        self.progress_area.setStyleSheet("""
            QTextEdit {
                border: 1px solid #cccccc;
                padding: 5px;
            }
        """)
        
        # Progress Bar
        self.progress_bar = QtWidgets.QProgressBar()
        self.progress_bar.hide()

        # Export Section
        export_group = QtWidgets.QGroupBox("Export Data")
        export_layout = QtWidgets.QGridLayout()
        
        self.export_buttons = {
            'courses': QtWidgets.QPushButton("Courses"),
            'notes': QtWidgets.QPushButton("Notes"),
            'bookmarks': QtWidgets.QPushButton("Bookmarks"),
            'all': QtWidgets.QPushButton("Full Backup")
        }
        
        export_layout.addWidget(QtWidgets.QLabel("Select data to export:"), 0, 0)
        for i, (key, btn) in enumerate(self.export_buttons.items(), start=1):
            export_layout.addWidget(btn, 0, i)
            btn.clicked.connect(partial(self.export_data, key))

        export_group.setLayout(export_layout)

        # Import Section
        import_group = QtWidgets.QGroupBox("Import Data")
        import_layout = QtWidgets.QGridLayout()
        
        self.import_buttons = {
            'courses': QtWidgets.QPushButton("Courses"),
            'notes': QtWidgets.QPushButton("Notes"),
            'bookmarks': QtWidgets.QPushButton("Bookmarks"),
            'all': QtWidgets.QPushButton("Full Backup")
        }
        
        import_layout.addWidget(QtWidgets.QLabel("Select data to import:"), 0, 0)
        for i, (key, btn) in enumerate(self.import_buttons.items(), start=1):
            import_layout.addWidget(btn, 0, i)
            btn.clicked.connect(partial(self.import_data, key))

        import_group.setLayout(import_layout)

        layout.addWidget(export_group)
        layout.addWidget(import_group)
        layout.addWidget(QtWidgets.QLabel("Operation Progress:"))
        layout.addWidget(self.progress_area)
        layout.addWidget(self.progress_bar)
        
        # Close Button
        self.close_btn = QtWidgets.QPushButton("Close")
        self.close_btn.clicked.connect(self.accept)
        layout.addWidget(self.close_btn)

        self.setLayout(layout)
        self.update_button_states()

    def update_progress(self, message):
        self.progress_area.append(f"• {message}")
        QtWidgets.QApplication.processEvents()

    def update_button_states(self):
        enabled = not self.operation_in_progress
        for btn in self.export_buttons.values():
            btn.setEnabled(enabled)
        for btn in self.import_buttons.values():
            btn.setEnabled(enabled)
        self.close_btn.setEnabled(enabled)

    def get_default_filename(self, data_type):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        return f"QuranData_{data_type}_{timestamp}.zip"

    def export_data(self, data_type):
        last_dir = self.app_settings.get_last_directory()
        file_path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Export Data", 
            f"{last_dir}/{self.get_default_filename(data_type)}",
             "ZIP Files (*.zip)"
        )

        if not file_path:
            return

        self.app_settings.set_last_directory(file_path)
        
        self.operation_in_progress = True
        self.update_button_states()
        self.progress_bar.show()
        self.progress_area.clear()

        try:
            with zipfile.ZipFile(file_path, 'w') as zipf:
                manifest = {
                    'version': 1,
                    'types': [],
                    'created': datetime.now().isoformat(),
                    'source': 'QuranBrowser'
                }

                # Export courses
                if data_type in ['courses', 'all']:
                    self.update_progress("Exporting courses...")
                    courses = self.db.get_all_courses()
                    zipf.writestr('courses.json', json.dumps(courses, ensure_ascii=False))
                    manifest['types'].append('courses')

                # Export notes
                if data_type in ['notes', 'all']:
                    self.update_progress("Exporting notes...")
                    notes = self.db.get_all_notes()
                    zipf.writestr('notes.json', json.dumps(notes, ensure_ascii=False))
                    manifest['types'].append('notes')

                # Export bookmarks
                if data_type in ['bookmarks', 'all']:
                    self.update_progress("Exporting bookmarks...")
                    bookmarks = self.db.get_all_bookmarks(self.parent.search_engine)
                    zipf.writestr('bookmarks.json', json.dumps(bookmarks, ensure_ascii=False))
                    manifest['types'].append('bookmarks')

                # Add manifest
                zipf.writestr('manifest.json', json.dumps(manifest))
                self.update_progress(f"Export completed successfully to:\n{file_path}")

        except Exception as e:
            self.update_progress(f"Export failed: {str(e)}")
        finally:
            self.operation_in_progress = False
            self.update_button_states()
            self.progress_bar.hide()

    def import_data(self, data_type):
        last_dir = self.app_settings.get_last_directory()
        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Import Data", 
            f"{last_dir}/{self.get_default_filename(data_type)}",
             "ZIP Files (*.zip)"
        )

        if not file_path:
            return

        self.app_settings.set_last_directory(file_path)

        self.operation_in_progress = True
        self.update_button_states()
        self.progress_bar.show()
        self.progress_area.clear()

        try:
            with zipfile.ZipFile(file_path, 'r') as zipf:
                # Check manifest
                if 'manifest.json' not in zipf.namelist():
                    raise ValueError("Invalid file format - missing manifest")

                manifest = json.loads(zipf.read('manifest.json').decode('utf-8'))
                if manifest.get('source') != 'QuranBrowser':
                    raise ValueError("Invalid file format - unrecognized source")

                # Validate import type compatibility
                if data_type != 'all' and data_type not in manifest['types']:
                    raise ValueError(f"Selected import type ({data_type}) not present in file")

                # Import courses
                if data_type in ['courses', 'all'] and 'courses.json' in zipf.namelist():
                    self.update_progress("Importing courses...")
                    courses = json.loads(zipf.read('courses.json').decode('utf-8'))
                    for course in courses:
                        title = course[1]
                        items = course[2]  

                        if not self.db.course_exists(title, items):
                            self.db.save_course(None, title, items)
                            self.update_progress(f"Added new course: {title}")
                        else:
                            self.update_progress(f"Skipped duplicate course: {title}")


                # Import notes
                if data_type in ['notes', 'all'] and 'notes.json' in zipf.namelist():
                    self.update_progress("Importing notes...")
                    notes = json.loads(zipf.read('notes.json').decode('utf-8'))
                    for note in notes:
                        if not self.db.note_exists(note['surah'], note['ayah'], note['content']):
                            self.db.add_note(note['surah'], note['ayah'], note['content'])
                            self.update_progress(f"Added note for {note['surah']}:{note['ayah']}")
                
                # Import bookmarks
                if data_type in ['bookmarks', 'all'] and 'bookmarks.json' in zipf.namelist():
                    self.update_progress("Importing bookmarks...")
                    bookmarks = json.loads(zipf.read('bookmarks.json').decode('utf-8'))
                    for bm in bookmarks:
                        self.db.add_bookmark(bm['surah'], bm['ayah'])
                        self.update_progress(f"Added bookmark for {bm['surah']}:{bm['ayah']}")

                self.update_progress("Import completed successfully")

        except Exception as e:
            self.update_progress(f"Import failed: {str(e)}")
        finally:
            self.operation_in_progress = False
            self.update_button_states()
            self.progress_bar.hide()
            # Refresh UI components
            if self.parent.detail_view.isVisible():
                self.parent.detail_view.notes_widget.load_notes()
