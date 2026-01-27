
# Add at the top of notes_manager.py after existing imports
import re
import csv
import logging
from datetime import datetime
from PyQt5 import QtWidgets, QtCore, QtGui



class DefinitionHighlighter(QtGui.QSyntaxHighlighter):
    def __init__(self, document, is_dark_theme):
        super().__init__(document)

        # Invisible marker format
        self.hidden_format = QtGui.QTextCharFormat()
        self.hidden_format.setForeground(QtCore.Qt.transparent)

        self.is_dark_theme = is_dark_theme

        # Determine note color based on theme
        if is_dark_theme:
            note_fg = "#D66A2C"       # orange for dark background
            note_bg = None
        else:
            note_fg = "#9C2A00"   # deep burnt-orange, low saturation, easy on the eyes
            note_bg = "#FFF3E8"   # very light warm background, barely noticeable but guides the eye

        # Marker → format mapping
        self.rules = {
            "**": self._make_format("#1565C0", bold=True),   # main header
            "##": self._make_format("#2E7D32", bold=True),   # sub header
            "--": self._make_format(fg=note_fg, bg=note_bg, bold=False),  # note
            "!!": self._make_format("#C62828", bold=True),   # warning
        }

    def _make_format(self, fg, bg=None, bold=False):
        fmt = QtGui.QTextCharFormat()
        fmt.setForeground(QtGui.QColor(fg))
        if bg:
            fmt.setBackground(QtGui.QColor(bg))
            fmt.setProperty(QtGui.QTextFormat.FullWidthSelection, True)
        if bold:
            fmt.setFontWeight(QtGui.QFont.Bold)
        return fmt

    def highlightBlock(self, text):
        for marker, fmt in self.rules.items():
            if text.startswith(marker):
                marker_len = len(marker)

                # Hide marker
                self.setFormat(0, marker_len, self.hidden_format)

                # Style rest of line
                self.setFormat(
                    marker_len,
                    len(text) - marker_len,
                    fmt
                )
                break

class NotesManagerDialog(QtWidgets.QDialog):
    show_ayah_requested = QtCore.pyqtSignal(int, int)  # Surah, Ayah

    def __init__(self, db, search_engine, parent=None):
        super().__init__(parent)
        self.db = db
        self.main_window = parent
        self.search_engine = search_engine
        self.current_note = None
        self.original_content = ""  # To track changes

        self.is_dark_theme = False
        if self.main_window and hasattr(self.main_window, 'theme_action'):
            self.is_dark_theme = self.main_window.theme_action.isChecked()
            self.main_window.theme_action.toggled.connect(self.handle_theme_change)
        
        self.init_ui()
        self.setup_rtl()
        self.apply_theme_styles()  # Apply initial theme
        self.setWindowTitle("إدارة التسجيلات")
        self.resize(1000, 600)

    

    def init_ui(self):
        main_layout = QtWidgets.QVBoxLayout(self)

        # Splitter for side-by-side notes list and content
        self.splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)

        # ======================
        # === Content panel ====
        # ======================
        content_widget = QtWidgets.QWidget()
        content_layout = QtWidgets.QVBoxLayout(content_widget)

        # QTextEdit for verse display
        self.verse_display = QtWidgets.QTextEdit()
        self.verse_display.setReadOnly(True)
        self.verse_display.setAlignment(QtCore.Qt.AlignRight)
        self.verse_display.setLayoutDirection(QtCore.Qt.RightToLeft)
        self.verse_display.setStyleSheet("""
            QTextEdit {
                font-family: 'Amiri';
                font-size: 16pt;
                border: 1px solid #ddd;
                padding: 10px;
            }
        """)
        self.verse_display.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding
        )

        # QTextEdit for notes
        self.note_content = QtWidgets.QTextEdit()
        self.note_content.setReadOnly(True)
        self.note_content.setLayoutDirection(QtCore.Qt.RightToLeft)
        self.note_content.setAlignment(QtCore.Qt.AlignRight)

        # Create and set the highlighter
        self.highlighter = DefinitionHighlighter(self.note_content.document(), self.is_dark_theme)

        # Create a vertical splitter for verse + note
        self.content_splitter = QtWidgets.QSplitter(QtCore.Qt.Vertical)
        self.content_splitter.setChildrenCollapsible(False)
        self.content_splitter.addWidget(self.verse_display)
        self.content_splitter.addWidget(self.note_content)
        self.content_splitter.setSizes([120, 480])  # Initial ratio

        # Buttons and editor toggle checkbox on same row
        button_row = QtWidgets.QHBoxLayout()
        self.edit_checkbox = QtWidgets.QCheckBox("تمكين التعديل")
        self.save_btn = QtWidgets.QPushButton("حفظ")
        self.delete_btn = QtWidgets.QPushButton("حذف")
        self.show_btn = QtWidgets.QPushButton("عرض الآية")
        self.close_btn = QtWidgets.QPushButton("إغلاق")

        self.save_btn.setEnabled(False)
        self.delete_btn.setEnabled(False)

        button_row.addWidget(self.edit_checkbox)
        button_row.addStretch()
        button_row.addWidget(self.save_btn)
        button_row.addWidget(self.show_btn)
        button_row.addWidget(self.delete_btn)
        button_row.addWidget(self.close_btn)

        # Assemble content layout
        content_layout.addWidget(self.content_splitter)
        content_layout.addLayout(button_row)

        # ======================
        # === Notes list panel ==
        # ======================
        self.notes_list = QtWidgets.QListWidget()
        self.notes_list.setLayoutDirection(QtCore.Qt.RightToLeft)
        self.notes_list.itemSelectionChanged.connect(self.on_note_selected)

        # Add widgets to main splitter
        self.splitter.addWidget(self.notes_list)
        self.splitter.addWidget(content_widget)
        self.splitter.setSizes([200, 800])

        # Add splitter to the main layout
        main_layout.addWidget(self.splitter)

        # Connect buttons
        self.save_btn.clicked.connect(self.save_note)
        self.delete_btn.clicked.connect(self.delete_note)
        self.show_btn.clicked.connect(self.show_ayah)
        self.close_btn.clicked.connect(self.check_unsaved_changes_before_close)
        self.edit_checkbox.toggled.connect(self.toggle_editing)
        self.note_content.textChanged.connect(self.on_content_changed)

        self.close_btn.setFocus()


    def apply_theme_styles(self):
        """Apply theme-specific styling to note_content"""
        # Determine base colors based on theme
        if self.is_dark_theme:
            base_bg = "#252525"
            base_fg = "#FFFFFF"
            border_color = "#555555"
            read_only_bg = "#2A2A2A"
            edit_bg = "#3A2A00"  # Dark orange-brown for edit mode
        else:
            base_bg = "white"
            base_fg = "black"
            border_color = "#CCCCCC"
            read_only_bg = "#F9F9F9"
            edit_bg = "#FFF8E1"  # Light orange for edit mode

        # Apply to note_content - use property-based styling
        self.note_content.setStyleSheet(f"""
            QTextEdit {{
                font-family: 'Amiri';
                font-size: 14pt;
                background-color: {base_bg};
                color: {base_fg};
                border: 1px solid {border_color};
                border-radius: 5px;
                padding: 10px;
                text-align: right;
            }}
        """)
        
        # Also update the verse display
        self.verse_display.setStyleSheet(f"""
            QTextEdit {{
                font-family: 'Amiri';
                font-size: 16pt;
                background-color: {base_bg};
                color: {base_fg};
                border: 1px solid {border_color};
                border-radius: 5px;
                padding: 10px;
                text-align: right;
            }}
        """)

    def handle_theme_change(self, dark):
        """Handle theme changes from main window"""
        self.is_dark_theme = dark
        self.highlighter.is_dark_theme = dark
        self.apply_theme_styles()
        self.highlighter.rehighlight()

    def setup_rtl(self):
        self.setLayoutDirection(QtCore.Qt.RightToLeft)

        arabic_font = QtGui.QFont("Amiri", 12)
        self.notes_list.setFont(arabic_font)
        self.note_content.setFont(arabic_font)
        self.verse_display.setFont(arabic_font)

        self.notes_list.setStyleSheet("""
            QListWidget {
                font-family: 'Amiri';
                font-size: 14pt;
            }
            QListWidget::item {
                padding: 8px;
                border-bottom: 1px solid #ddd;
            }
            QListWidget::item:selected {
                color: black;
            }
        """)

    def load_notes(self):
        self.notes_list.clear()
        notes = self.db.get_all_notes()
        for note in notes:
            surah_name = self.search_engine.get_chapter_name(note['surah'])
            item_text = f"{surah_name} - الآية {note['ayah']}"
            item = QtWidgets.QListWidgetItem(item_text)
            item.setTextAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
            item.setData(QtCore.Qt.UserRole, note)
            self.notes_list.addItem(item)

    def on_note_selected(self):
        if self.edit_checkbox.isChecked():
            # If we're in edit mode, prevent changing selection
            self.show_status_message("الرجاء حفظ أو إلغاء التعديلات قبل تغيير التسجيل", 3000)
            # Restore previous selection
            if self.current_note:
                for i in range(self.notes_list.count()):
                    item = self.notes_list.item(i)
                    if item.data(QtCore.Qt.UserRole)['id'] == self.current_note['id']:
                        self.notes_list.setCurrentItem(item)
                        break
            return
        
        selected = self.notes_list.currentItem()
        if selected:
            self.current_note = selected.data(QtCore.Qt.UserRole)

            # Show verse
            verse_text = self.get_verse_text(
                self.current_note['surah'],
                self.current_note['ayah']
            )
            self.verse_display.setPlainText(verse_text)

            # Show note content
            self.note_content.setPlainText(self.current_note['content'])
            self.original_content = self.current_note['content']  # Store for change detection
            self.delete_btn.setEnabled(True)
            self.show_btn.setEnabled(True)

            # Reset editing
            self.edit_checkbox.setChecked(False)
            self.note_content.setReadOnly(True)
            self.save_btn.setEnabled(False)
            self.show_btn.setFocus()
        else:
            self.current_note = None
            self.verse_display.clear()
            self.note_content.clear()
            self.delete_btn.setEnabled(False)
            self.show_btn.setEnabled(False)

    def get_verse_text(self, surah, ayah):
        try:
            verse = self.search_engine.get_verse(surah, ayah, version='uthmani')
            surah_name = self.search_engine.get_chapter_name(surah)
            return f"{verse} ({surah_name} {ayah})"
        except Exception as e:
            print(f"Error loading verse: {e}")
            return ""

    def on_content_changed(self):
        if self.edit_checkbox:
            self.save_btn.setEnabled(True)

    def toggle_editing(self, enabled):
        if enabled:
            if not self.current_note:
                self.edit_checkbox.setChecked(False)
                self.show_status_message("الرجاء اختيار تسجيل أولاً", 2000)
                return
                
            # Store original content for change detection
            self.original_content = self.note_content.toPlainText()
            
            # Disable UI elements during editing
            self.notes_list.setEnabled(False)
            self.delete_btn.setEnabled(False)
            self.show_btn.setEnabled(False)
            self.close_btn.setEnabled(False)
            
            # Enable editing
            self.note_content.setReadOnly(False)
            
            # Apply edit mode styling
            if self.is_dark_theme:
                edit_bg = "#3A2A00"
                border_color = "#FFA000"
            else:
                edit_bg = "#FFF8E1"
                border_color = "#FFA000"
                
            self.note_content.setStyleSheet(f"""
                QTextEdit {{
                    font-family: 'Amiri';
                    font-size: 14pt;
                    background-color: {edit_bg};
                    color: {'#FFFFFF' if self.is_dark_theme else 'black'};
                    border: 2px solid {border_color};
                    border-radius: 5px;
                    padding: 10px;
                    text-align: right;
                }}
            """)
            
            self.note_content.setFocus()
            self.show_status_message("تم تمكين التعديل", 2000)
        else:
            # Check if content has changed
            current_content = self.note_content.toPlainText()
            if current_content != self.original_content:
                # Prompt user to save changes
                reply = QtWidgets.QMessageBox.question(
                    self,
                    "تغييرات غير محفوظة",
                    "هناك تغييرات غير محفوظة. هل تريد حفظها قبل الإغلاق؟",
                    QtWidgets.QMessageBox.Save | 
                    QtWidgets.QMessageBox.Discard | 
                    QtWidgets.QMessageBox.Cancel,
                    QtWidgets.QMessageBox.Save
                )
                
                if reply == QtWidgets.QMessageBox.Save:
                    self.save_note()
                elif reply == QtWidgets.QMessageBox.Cancel:
                    # Stay in edit mode
                    self.edit_checkbox.setChecked(True)
                    return
            
            # Re-enable UI elements after editing
            self.notes_list.setEnabled(True)
            self.delete_btn.setEnabled(True)
            self.show_btn.setEnabled(True)
            self.close_btn.setEnabled(True)
            self.note_content.setReadOnly(True)
            
            # Apply read-only styling
            self.apply_theme_styles()
            
            self.save_btn.setEnabled(False)
            self.show_status_message("تم تعطيل التعديل", 2000)


    def save_note(self):
        if self.current_note and self.edit_checkbox.isChecked():
            new_content = self.note_content.toPlainText().strip()
            if new_content:
                self.db.update_note(self.current_note['id'], new_content)
                self.original_content = new_content  # Update original content
                self.load_notes()
                self.save_btn.setEnabled(False)
                self.show_status_message("تم حفظ التغييرات بنجاح", 2000)
                
                # Exit edit mode after saving
                self.edit_checkbox.setChecked(False)    
                # Re-highlight the content
                self.highlighter.rehighlight()      

    def delete_note(self):
        if self.current_note and not self.edit_checkbox.isChecked():
            confirm = QtWidgets.QMessageBox.question(
                self,
                "تأكيد الحذف",
                "هل أنت متأكد من حذف هذا التسجيل؟",
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
            )
            if confirm == QtWidgets.QMessageBox.Yes:
                self.db.delete_note(self.current_note['id'])
                self.load_notes()
                self.current_note = None
                self.verse_display.clear()
                self.note_content.clear()
                self.show_status_message("تم حذف التسجيل بنجاح", 2000)

    def show_ayah(self):
        if self.current_note and not self.edit_checkbox.isChecked():
            self.show_ayah_requested.emit(
                self.current_note['surah'],
                self.current_note['ayah']
            )
            self.hide()

    def check_unsaved_changes_before_close(self):
        if self.edit_checkbox.isChecked():
            current_content = self.note_content.toPlainText()
            if current_content != self.original_content:
                # Prompt user to save changes
                reply = QtWidgets.QMessageBox.question(
                    self,
                    "تغييرات غير محفوظة",
                    "هناك تغييرات غير محفوظة. هل تريد حفظها قبل الإغلاق؟",
                    QtWidgets.QMessageBox.Save | 
                    QtWidgets.QMessageBox.Discard | 
                    QtWidgets.QMessageBox.Cancel,
                    QtWidgets.QMessageBox.Save
                )
                
                if reply == QtWidgets.QMessageBox.Save:
                    self.save_note()
                    self.hide()
                elif reply == QtWidgets.QMessageBox.Discard:
                    self.hide()
                # If Cancel, do nothing
            else:
                self.hide()
        else:
            self.hide()
            
    def closeEvent(self, event):
        """Handle window close event (X button)"""
        if self.edit_checkbox.isChecked():
            current_content = self.note_content.toPlainText()
            if current_content != self.original_content:
                # Prompt user to save changes
                reply = QtWidgets.QMessageBox.question(
                    self,
                    "تغييرات غير محفوظة",
                    "هناك تغييرات غير محفوظة. هل تريد حفظها قبل الإغلاق؟",
                    QtWidgets.QMessageBox.Save | 
                    QtWidgets.QMessageBox.Discard | 
                    QtWidgets.QMessageBox.Cancel,
                    QtWidgets.QMessageBox.Save
                )
                
                if reply == QtWidgets.QMessageBox.Save:
                    self.save_note()
                    event.accept()
                elif reply == QtWidgets.QMessageBox.Discard:
                    event.accept()
                else:
                    event.ignore()
            else:
                event.accept()
        else:
            event.accept()

    def show_status_message(self, message, timeout):
        QtWidgets.QToolTip.showText(
            self.mapToGlobal(QtCore.QPoint(0, 0)),
            message,
            self,
            QtCore.QRect(),
            timeout
        )

    def showEvent(self, event):
        self.load_notes()
        super().showEvent(event)