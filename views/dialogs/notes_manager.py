
from PyQt5 import QtWidgets, QtCore, QtGui


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
        self.splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        
        # Content area (80%)
        content_widget = QtWidgets.QWidget()
        content_layout = QtWidgets.QVBoxLayout(content_widget)
        
        # Note content editor
        self.note_content = QtWidgets.QTextEdit()
        self.note_content.textChanged.connect(self.on_content_changed)
        
        # Buttons
        button_box = QtWidgets.QDialogButtonBox(QtCore.Qt.Horizontal)
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
        self.notes_list.setLayoutDirection(QtCore.Qt.RightToLeft)
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
        self.setLayoutDirection(QtCore.Qt.RightToLeft)
        self.notes_list.setLayoutDirection(QtCore.Qt.RightToLeft)
        
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
            QListWidget::item:selected {
                color: black; 
            }
        """)

    def load_notes(self):
        self.notes_list.clear()
        notes = self.notes_manager.get_all_notes()
        
        for note in notes:
            surah_name = self.search_engine.get_chapter_name(note['surah'])
            item_text = f"{surah_name} - الآية {note['ayah']}"
            item = QtWidgets.QListWidgetItem(item_text)
            item.setTextAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
            item.setData(QtCore.Qt.UserRole, note)
            self.notes_list.addItem(item)

    def on_note_selected(self):
        selected = self.notes_list.currentItem()
        if selected:
            self.current_note = selected.data(QtCore.Qt.UserRole)
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
