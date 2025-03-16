from PyQt5 import QtWidgets, QtGui, QtCore
from models.notes_manager import NotesManager
from models.search_engine import QuranSearch

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
        splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)

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
            item.setData(QtCore.Qt.UserRole, note)
            self.notes_list.addItem(item)
        self.editor.clear()

    def on_note_selected(self):
        selected = self.notes_list.currentItem()
        if selected:
            note = selected.data(QtCore.Qt.UserRole)
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

