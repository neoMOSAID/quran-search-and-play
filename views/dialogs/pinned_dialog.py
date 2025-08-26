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
        self.current_group_id = None
        self.verse_items = []  # To store verse items for reordering
        self.pending_changes = []  # Track changes before saving
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
        self.new_btn.clicked.connect(self.new_group)
        group_btn_layout.addWidget(self.new_btn)
        
        self.delete_btn = QtWidgets.QPushButton("حذف")
        self.delete_btn.setFont(QtGui.QFont("Amiri", 12))
        self.delete_btn.setMinimumHeight(40)
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
        
        # Action buttons for verses
        action_layout = QtWidgets.QHBoxLayout()
        
        self.remove_verse_btn = QtWidgets.QPushButton("إزالة الآية المحددة")
        self.remove_verse_btn.setFont(QtGui.QFont("Amiri", 12))
        self.remove_verse_btn.setMinimumHeight(40)
        self.remove_verse_btn.clicked.connect(self.remove_selected_verse)
        action_layout.addWidget(self.remove_verse_btn)
        
        self.move_up_btn = QtWidgets.QPushButton("Move Up")
        self.move_up_btn.setFont(QtGui.QFont("Amiri", 12))
        self.move_up_btn.setMinimumHeight(40)
        self.move_up_btn.clicked.connect(self.move_verse_up)
        action_layout.addWidget(self.move_up_btn)
        
        self.move_down_btn = QtWidgets.QPushButton("Move Down")
        self.move_down_btn.setFont(QtGui.QFont("Amiri", 12))
        self.move_down_btn.setMinimumHeight(40)
        self.move_down_btn.clicked.connect(self.move_verse_down)
        action_layout.addWidget(self.move_down_btn)
        
        self.save_btn = QtWidgets.QPushButton("Save Changes")
        self.save_btn.setFont(QtGui.QFont("Amiri", 12))
        self.save_btn.setMinimumHeight(40)
        #self.save_btn.setStyleSheet("QPushButton { background-color: #4CAF50; color: white; }")
        self.save_btn.clicked.connect(self.save_changes)
        action_layout.addWidget(self.save_btn)
        
        verse_layout.addLayout(action_layout)
        
        splitter.addWidget(verse_frame)
        
        # Set initial splitter sizes
        splitter.setSizes([250, 650])
        main_layout.addWidget(splitter)
        
        # Dialog buttons
        btn_box = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
        )
        btn_box.setFont(QtGui.QFont("Amiri", 12))
        btn_box.setLayoutDirection(QtCore.Qt.LeftToRight)
        self.setLayoutDirection(QtCore.Qt.RightToLeft)
        btn_box.accepted.connect(self.accept)
        btn_box.rejected.connect(self.reject)
        main_layout.addWidget(btn_box)
        
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
            
        self.current_group_id = selected_items[0].data(QtCore.Qt.UserRole)
        self.load_verses(self.current_group_id)
        self.pending_changes = []  # Reset pending changes when switching groups
        
    def load_verses(self, group_id):
        self.verse_list.clear()
        self.verse_items = []
        verses = self.db.get_pinned_verses_by_group_ordered(group_id)
        
        for verse in verses:
            surah_name = self.search_engine.get_chapter_name(verse['surah'])
            verse_text = self.search_engine.get_verse(verse['surah'], verse['ayah'], 'uthmani')
            
            # Format the verse text with chapter and ayah number
            display_text = f"{verse_text} ({verse['surah']}-{surah_name} {verse['ayah']})"
            
            item = QtWidgets.QListWidgetItem(display_text)
            item.setData(QtCore.Qt.UserRole, verse)
            self.verse_list.addItem(item)
            self.verse_items.append((verse['surah'], verse['ayah']))
    
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
        rows_to_remove = []
        for item in selected_items:
            verse = item.data(QtCore.Qt.UserRole)
            verses_to_remove.append(verse)
            rows_to_remove.append(self.verse_list.row(item))
        
        # Add to pending changes instead of immediate database operation
        for verse in verses_to_remove:
            self.pending_changes.append(('remove', verse['surah'], verse['ayah'], group_id))
        
        # Remove from list widget (in reverse order to avoid index issues)
        for row in sorted(rows_to_remove, reverse=True):
            self.verse_list.takeItem(row)
            if row < len(self.verse_items):
                self.verse_items.pop(row)
    
    def on_verse_double_clicked(self, item):
        verse = item.data(QtCore.Qt.UserRole)
        self.verseSelected.emit(verse['surah'], verse['ayah'])

    def move_verse_up(self):
        current_row = self.verse_list.currentRow()
        if current_row <= 0:
            return
            
        # Swap items in the list
        item = self.verse_list.takeItem(current_row)
        self.verse_list.insertItem(current_row - 1, item)
        self.verse_list.setCurrentRow(current_row - 1)
        
        # Update the internal order tracking
        self.verse_items.insert(current_row - 1, self.verse_items.pop(current_row))
        
        # Add to pending changes
        self.pending_changes.append(('reorder', self.current_group_id, self.verse_items.copy()))
        
    def move_verse_down(self):
        current_row = self.verse_list.currentRow()
        if current_row < 0 or current_row >= self.verse_list.count() - 1:
            return
            
        # Swap items in the list
        item = self.verse_list.takeItem(current_row)
        self.verse_list.insertItem(current_row + 1, item)
        self.verse_list.setCurrentRow(current_row + 1)
        
        # Update the internal order tracking
        self.verse_items.insert(current_row + 1, self.verse_items.pop(current_row))
        
        # Add to pending changes
        self.pending_changes.append(('reorder', self.current_group_id, self.verse_items.copy()))

    def save_changes(self):
        """Apply all pending changes to the database"""
        if not self.pending_changes:
            self.showMessage("لا توجد تغييرات لحفظها", 2000)
            return
            
        try:
            # Process all pending changes
            for change in self.pending_changes:
                if change[0] == 'remove':
                    _, surah, ayah, group_id = change
                    self.db.remove_pinned_verse(surah, ayah, group_id)
                elif change[0] == 'reorder':
                    _, group_id, new_order = change
                    self.db.reorder_pinned_verses(group_id, new_order)
            
            # Clear pending changes after successful save
            self.pending_changes = []
            self.showMessage("تم حفظ التغييرات بنجاح", 2000)
            
        except Exception as e:
            self.showMessage(f"خطأ في حفظ التغييرات: {str(e)}", 3000)