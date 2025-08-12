### ./views/dialogs/pinned_dialog.py ###
from PyQt5 import QtWidgets, QtCore, QtGui

class PinnedVersesDialog(QtWidgets.QDialog):
    verseSelected = QtCore.pyqtSignal(int, int)  # surah, ayah
    activeGroupChanged = QtCore.pyqtSignal()
    def __init__(self, db, search_engine, parent=None):
        super().__init__(parent)
        self.db = db
        self.search_engine = search_engine
        self.setWindowTitle("الآيات المثبتة - المجموعات")
        self.resize(900, 600)
        self.init_ui()
        self.load_groups()
        
    def init_ui(self):
        # Create main layout
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        
        # Create splitter for groups and verses
        splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        splitter.setChildrenCollapsible(False)
        
        # ===== GROUPS PANEL =====
        group_frame = QtWidgets.QFrame()
        group_layout = QtWidgets.QVBoxLayout(group_frame)
        group_layout.setContentsMargins(5, 5, 5, 5)
        
        # Group list label
        group_label = QtWidgets.QLabel("المجموعات:")
        group_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        group_layout.addWidget(group_label)
        
        # Group list
        self.group_list = QtWidgets.QListWidget()
        self.group_list.setFont(QtGui.QFont("Amiri", 14))
        self.group_list.itemSelectionChanged.connect(self.group_selected)
        self.group_list.itemDoubleClicked.connect(self.edit_group_name)
        group_layout.addWidget(self.group_list)
        
        # Group buttons
        group_btn_layout = QtWidgets.QHBoxLayout()
        self.new_btn = QtWidgets.QPushButton("جديد")
        self.new_btn.setFont(QtGui.QFont("Amiri", 12))
        self.new_btn.setMinimumHeight(40)
        #self.new_btn.setStyleSheet("QPushButton { background-color: #4CAF50; color: white; }")
        self.new_btn.clicked.connect(self.new_group)
        group_btn_layout.addWidget(self.new_btn)
        
        self.delete_btn = QtWidgets.QPushButton("حذف")
        self.delete_btn.setFont(QtGui.QFont("Amiri", 12))
        self.delete_btn.setMinimumHeight(40)
        #self.delete_btn.setStyleSheet("QPushButton { background-color: #f44336; color: white; }")
        self.delete_btn.clicked.connect(self.delete_group)
        group_btn_layout.addWidget(self.delete_btn)
        group_layout.addLayout(group_btn_layout)
        
        # Active group 
        self.set_active_btn = QtWidgets.QPushButton("Set Default")
        self.set_active_btn.setFont(QtGui.QFont("Amiri", 12))
        self.set_active_btn.setMinimumHeight(40)
        self.set_active_btn.clicked.connect(self.set_active_group)
        group_layout.addWidget(self.set_active_btn)
        
        splitter.addWidget(group_frame)
        
        # ===== VERSES PANEL =====
        verse_frame = QtWidgets.QFrame()
        verse_layout = QtWidgets.QVBoxLayout(verse_frame)
        verse_layout.setContentsMargins(5, 5, 5, 5)
        
        # Verse list label
        verse_label = QtWidgets.QLabel("الآيات:")
        verse_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        verse_layout.addWidget(verse_label)
        
        # Verse list
        self.verse_list = QtWidgets.QListWidget()
        self.verse_list.setFont(QtGui.QFont("Amiri", 14))
        self.verse_list.setWordWrap(True)
        self.verse_list.doubleClicked.connect(self.on_verse_double_clicked)
        verse_layout.addWidget(self.verse_list)
        
        # Remove verse button
        self.remove_verse_btn = QtWidgets.QPushButton("إزالة الآية المحددة")
        self.remove_verse_btn.setFont(QtGui.QFont("Amiri", 12))
        self.remove_verse_btn.setMinimumHeight(40)
        #self.remove_verse_btn.setStyleSheet("QPushButton { background-color: #ff9800; color: white; }")
        self.remove_verse_btn.clicked.connect(self.remove_selected_verse)
        verse_layout.addWidget(self.remove_verse_btn)
        
        splitter.addWidget(verse_frame)
        
        # Set initial splitter sizes
        splitter.setSizes([250, 650])
        main_layout.addWidget(splitter)
        
        # Dialog buttons
        btn_box = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
        )
        btn_box.setFont(QtGui.QFont("Amiri", 12))

        # Force button order: OK right, Cancel left
        btn_box.setLayoutDirection(QtCore.Qt.LeftToRight)

        # Keep dialog RTL for labels
        self.setLayoutDirection(QtCore.Qt.RightToLeft)

        btn_box.accepted.connect(self.accept)
        btn_box.rejected.connect(self.reject)

        main_layout.addWidget(btn_box)
        
        # Set RTL layout direction
        self.setLayoutDirection(QtCore.Qt.RightToLeft)
        
    def load_groups(self):
        self.group_list.clear()
        groups = self.db.get_pinned_groups()
        self.groups = groups
        active_group_id = self.db.get_active_group_id()
        
        for group in groups:
            item = QtWidgets.QListWidgetItem(group['name'])
            item.setFont(QtGui.QFont("Amiri", 14))
            item.setData(QtCore.Qt.UserRole, group['id'])
            
            # Highlight active group
            if group['id'] == active_group_id:
                item.setForeground(QtGui.QColor("#1E88E5"))  # Blue color
                font = item.font()
                font.setBold(True)
                item.setFont(font)
                
            self.group_list.addItem(item)
            
        # Select the active group if any
        if active_group_id:
            for i in range(self.group_list.count()):
                item = self.group_list.item(i)
                if item.data(QtCore.Qt.UserRole) == active_group_id:
                    self.group_list.setCurrentItem(item)
                    break
    
    
    def group_selected(self):
        selected_items = self.group_list.selectedItems()
        if not selected_items:
            return
            
        group_id = selected_items[0].data(QtCore.Qt.UserRole)
        self.load_verses(group_id)
        
    
    def load_verses(self, group_id):
        self.verse_list.clear()
        verses = self.db.get_pinned_verses_by_group(group_id)
        
        for verse in verses:
            surah_name = self.search_engine.get_chapter_name(verse['surah'])
            verse_text = self.search_engine.get_verse(verse['surah'], verse['ayah'], 'uthmani')
            
            # Format the verse text with chapter and ayah number
            display_text = f"{verse_text} ({verse['surah']}-{surah_name} {verse['ayah']})"
            
            item = QtWidgets.QListWidgetItem(display_text)
            item.setData(QtCore.Qt.UserRole, verse)
            self.verse_list.addItem(item)
    
    def new_group(self):
        name, ok = QtWidgets.QInputDialog.getText(
            self, "مجموعة جديدة", "اسم المجموعة:",
            QtWidgets.QLineEdit.Normal, "", 
            QtCore.Qt.WindowTitleHint | QtCore.Qt.WindowCloseButtonHint
        )
        if ok and name:
            if self.db.create_pinned_group(name):
                self.load_groups()
    
    def delete_group(self):
        selected_items = self.group_list.selectedItems()
        if not selected_items:
            return
            
        group_id = selected_items[0].data(QtCore.Qt.UserRole)
        group_name = selected_items[0].text()
        
        reply = QtWidgets.QMessageBox.question(
            self,
            "تأكيد الحذف",
            f"هل أنت متأكد من حذف المجموعة '{group_name}' وجميع آياتها؟",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.No
        )
        if reply == QtWidgets.QMessageBox.Yes:
            self.db.delete_pinned_group(group_id)
            self.load_groups()
    
    def set_active_group(self):
        selected_items = self.group_list.selectedItems()
        if not selected_items:
            return
            
        group_id = selected_items[0].data(QtCore.Qt.UserRole)
        self.db.set_active_group(group_id)
        self.load_groups()
        self.activeGroupChanged.emit()
        self.showMessage(f"تم تعيين المجموعة كنشطة", 2000)

    def edit_group_name(self, item):
        old_name = item.text()
        new_name, ok = QtWidgets.QInputDialog.getText(
            self, "تعديل اسم المجموعة", "الاسم الجديد:",
            QtWidgets.QLineEdit.Normal, old_name
        )
        if ok and new_name and new_name != old_name:
            group_id = item.data(QtCore.Qt.UserRole)
            if self.db.rename_pinned_group(group_id, new_name):
                item.setText(new_name)
                self.showMessage(f"تم تعديل الاسم إلى '{new_name}'", 2000)

    def showMessage(self, message, timeout=3000):
        """Show a temporary message in the status bar"""
        # We don't have a status bar, so show a QMessageBox
        msg = QtWidgets.QMessageBox(self)
        msg.setWindowTitle(" ")
        msg.setText(message)
        msg.setStandardButtons(QtWidgets.QMessageBox.Ok)
        msg.setModal(False)  # Non-blocking
        msg.show()
        QtCore.QTimer.singleShot(timeout, msg.close)

    def remove_selected_verse(self):
        selected_items = self.verse_list.selectedItems()
        if not selected_items:
            return
            
        # Get group ID
        group_id = self.group_list.currentItem().data(QtCore.Qt.UserRole)
        
        # Collect verses to remove
        verses_to_remove = []
        for item in selected_items:
            verse = item.data(QtCore.Qt.UserRole)
            verses_to_remove.append(verse)
        
        # Remove from database
        for verse in verses_to_remove:
            self.db.remove_pinned_verse(verse['surah'], verse['ayah'], group_id)
        
        # Reload verses
        self.load_verses(group_id)
    
    def on_verse_double_clicked(self, item):
        verse = item.data(QtCore.Qt.UserRole)
        self.verseSelected.emit(verse['surah'], verse['ayah'])