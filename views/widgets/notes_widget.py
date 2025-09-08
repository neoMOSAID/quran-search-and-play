from PyQt5 import QtWidgets, QtGui, QtCore
from utils.settings import AppSettings

from models.database import DbManager
from models.search_engine import QuranSearch

class NotesWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.db = DbManager()
        self.current_surah = None
        self.current_ayah = None
        self.original_content = ""
        self.settings = AppSettings()
        self.init_ui()

    def init_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)

        # Verse label
        self.verse_label = QtWidgets.QLabel()
        self.verse_label.setStyleSheet("font-size: 10pt; font-weight: bold;")
        layout.addWidget(self.verse_label)

        # Editor
        self.editor = QtWidgets.QTextEdit()
        self.editor.setPlaceholderText("...أكتب هنا")
        font = self.editor.font()
        font.setPointSize(12)
        self.editor.setFont(font)
        self.editor.setReadOnly(True)  # Default to read-only
        self.editor.textChanged.connect(self.handle_text_change)
        layout.addWidget(self.editor, 1)  # Take all available space

        # Button container - single row for all controls
        button_container = QtWidgets.QWidget()
        button_layout = QtWidgets.QHBoxLayout(button_container)
        button_layout.setContentsMargins(0, 0, 0, 0)
        
        # Status label - left aligned
        self.status_label = QtWidgets.QLabel()
        self.status_label.setStyleSheet("font-size: 9pt; color: #666666;")
        button_layout.addWidget(self.status_label)
        
        # Spacer to push other controls to the right
        button_layout.addStretch(1)

        # Font size controls - new buttons
        self.decrease_font_btn = QtWidgets.QPushButton("A-")
        self.decrease_font_btn.setFixedSize(30, 30)
        self.decrease_font_btn.clicked.connect(self.decrease_font_size)
        button_layout.addWidget(self.decrease_font_btn)
        
        self.increase_font_btn = QtWidgets.QPushButton("A+")
        self.increase_font_btn.setFixedSize(30, 30)
        self.increase_font_btn.clicked.connect(self.increase_font_size)
        button_layout.addWidget(self.increase_font_btn)

        # Edit checkbox - middle right
        self.edit_checkbox = QtWidgets.QCheckBox("تمكين التعديل")
        self.edit_checkbox.stateChanged.connect(self.toggle_edit_mode)
        button_layout.addWidget(self.edit_checkbox)
        
        # Back button
        self.back_button = QtWidgets.QPushButton("رجوع")
        self.back_button.setFixedSize(80, 30)
        button_layout.addWidget(self.back_button)
        
        # Save button
        self.save_button = QtWidgets.QPushButton("حفظ")
        self.save_button.setFixedSize(80, 30)
        self.save_button.setEnabled(False)  # Disabled by default
        self.save_button.clicked.connect(self.save_note)
        button_layout.addWidget(self.save_button)

        layout.addWidget(button_container)

        self.load_font_setting() 

    def increase_font_size(self):
        if self.font_size < 24:  # Set maximum size as needed
            self.font_size += 1
            self.update_editor_font()
            self.save_font_setting()

    def decrease_font_size(self):
        if self.font_size > 8:  # Set minimum size as needed
            self.font_size -= 1
            self.update_editor_font()
            self.save_font_setting()

    def update_editor_font(self):
        font = self.editor.font()
        font.setPointSize(self.font_size)
        self.editor.setFont(font)

    def save_font_setting(self):
        self.settings.set("notes_font_size", self.font_size)

    def load_font_setting(self):
        saved_size = self.settings.value("notes_font_size", 12, type=int)
        self.font_size = saved_size
        self.update_editor_font()

    def set_ayah(self, surah, ayah):
        self.current_surah = surah
        self.current_ayah = ayah
        self.search_engine = QuranSearch()
        chapter = self.search_engine.get_chapter_name(self.current_surah)
        self.verse_label.setText(f"تدبر الآية {self.current_ayah} من سورة {chapter}")
        self.load_note()
        self.status_label.clear()
        self.edit_checkbox.setChecked(False)  # Reset to read-only mode

    def load_note(self):
        """Load the single note for this verse"""
        notes = self.db.get_notes(self.current_surah, self.current_ayah)
        if notes:
            # Use the most recent note
            self.original_content = notes[0]['content']
            self.editor.setPlainText(self.original_content)
        else:
            self.original_content = ""
            self.editor.clear()
        self.save_button.setEnabled(False)

    def toggle_edit_mode(self, state):
        """Toggle between read-only and edit mode"""
        is_editable = state == QtCore.Qt.Checked
        self.editor.setReadOnly(not is_editable)
        
        # Set visual indication of edit mode
        if is_editable:
            #self.editor.setStyleSheet("background-color: #FFFFCC;")  # Light yellow
            self.status_label.setText("وضع التعديل مفعل")
            self.back_button.setEnabled(False)
        else:
            self.editor.setStyleSheet("")  # Reset to default
            self.status_label.clear()
            self.back_button.setEnabled(True)
            
            # Revert to original content if not saved
            current_content = self.editor.toPlainText().strip()
            if current_content != self.original_content:
                self.editor.setPlainText(self.original_content)
            
            self.save_button.setEnabled(False)

    def handle_text_change(self):
        """Enable save button only when content has changed"""
        if self.editor.isReadOnly():
            return
            
        current_content = self.editor.toPlainText().strip()
        self.save_button.setEnabled(current_content != self.original_content)

    def enable_editing(self):
        """Enable editing and focus on the editor"""
        self.edit_checkbox.setChecked(True)
        self.editor.setFocus()

    def delete_note(self):
        if not (self.current_surah and self.current_ayah):
            return
            
        # Check if there's a note to delete
        notes = self.db.get_notes(self.current_surah, self.current_ayah)
        if not notes:
            return
            
        # Show confirmation dialog
        reply = QtWidgets.QMessageBox.question(
            self,
            "تأكيد الحذف",
            "هل أنت متأكد من حذف هذا التسجيل؟",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
        )
        
        if reply == QtWidgets.QMessageBox.Yes:
            # Delete the note
            self.db.delete_all_notes(self.current_surah, self.current_ayah)
            self.original_content = ""
            self.editor.clear()
            self.status_label.setText("تم حذف التسجيل")
            
            # Clear status message after 2 seconds
            QtCore.QTimer.singleShot(2000, lambda: self.status_label.clear())
            
            # Reset edit mode
            self.edit_checkbox.setChecked(False)

    def save_note(self):
        if not (self.current_surah and self.current_ayah):
            return

        current_content = self.editor.toPlainText().strip()
        
        # Check if content has actually changed
        if current_content == self.original_content:
            self.status_label.setText("لا يوجد تغيير!")
            QtCore.QTimer.singleShot(2000, lambda: self.status_label.clear())
            return
            
        # Show confirmation dialog
        reply = QtWidgets.QMessageBox.question(
            self,
            "تأكيد الحفظ",
            "هل تريد حفظ التغييرات؟",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
        )
        
        if reply == QtWidgets.QMessageBox.No:
            self.status_label.setText("تم الإلغاء")
            QtCore.QTimer.singleShot(2000, lambda: self.status_label.clear())
            return
            
        # Delete any existing notes for this verse
        self.db.delete_all_notes(self.current_surah, self.current_ayah)
        
        if current_content:
            # Create new note
            self.db.add_note(self.current_surah, self.current_ayah, current_content)
            self.original_content = current_content
            self.status_label.setText("تم الحفظ!")
            self.save_button.setEnabled(False)
            
            # Clear status message after 2 seconds
            QtCore.QTimer.singleShot(2000, lambda: self.status_label.clear())