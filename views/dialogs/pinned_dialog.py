from PyQt5 import QtWidgets, QtCore, QtGui

class PinnedVersesDialog(QtWidgets.QDialog):
    verseSelected = QtCore.pyqtSignal(int, int)  # Surah, Ayah
    
    def __init__(self, pinned_verses, search_engine, parent=None):
        super().__init__(parent)
        self.pinned_verses = pinned_verses
        self.search_engine = search_engine
        self.setWindowTitle("الآيات المثبتة")
        self.resize(600, 400)
        self.init_ui()
        
    def init_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        
        # List widget
        self.list_widget = QtWidgets.QListWidget()
        self.list_widget.setStyleSheet("""
            QListWidget {
                font-family: 'Amiri';
                font-size: 14pt;
            }
            QListWidget::item {
                padding: 10px;
                border-bottom: 1px solid #ddd;
            }
        """)
        self.list_widget.itemDoubleClicked.connect(self.on_item_double_clicked)
        layout.addWidget(self.list_widget)
        
        # Buttons
        btn_box = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
        )
        btn_box.accepted.connect(self.accept)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)
        
        self.load_verses()
        
    def load_verses(self):
        self.list_widget.clear()
        for verse in self.pinned_verses:
            surah_name = self.search_engine.get_chapter_name(verse['surah'])
            item = QtWidgets.QListWidgetItem(
                f"{surah_name} - الآية {verse['ayah']}"
            )
            item.setData(QtCore.Qt.UserRole, verse)
            self.list_widget.addItem(item)
            
    def on_item_double_clicked(self, item):
        verse = item.data(QtCore.Qt.UserRole)
        self.verseSelected.emit(verse['surah'], verse['ayah'])
        self.accept()