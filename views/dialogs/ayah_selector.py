
import json

from PyQt5 import QtWidgets, QtCore, QtGui
from utils.settings import AppSettings


class AyahSelectorDialog(QtWidgets.QDialog):
    play_requested = QtCore.pyqtSignal(int, int, int)
    search_requested = QtCore.pyqtSignal(str)
    #PLACEHOLDER_TEXT = "Enter 'a surah start [end]' or :  \n 's search terms' help: Ctrl+H"
    PLACEHOLDER_TEXT = "أكتب a رقم السورة رقم الآية [رقم الآية]"
    PLACEHOLDER_TEXT += "\n"
    PLACEHOLDER_TEXT += "أو أكتب s ثم كلمات البحث"
    PLACEHOLDER_TEXT += "\n للمزيد : Ctrl+Shift+H \n"
    PLACEHOLDER_TEXT += "مثال a 255 \n a 255 260 \n s لا اله الا الله"


    def __init__(self, notes_manager, parent=None):
        super().__init__(parent)
        self.setWindowTitle("دروس القرآن")
        self.resize(250, 350)  # Set initial size but allow resizing
        self.notes_manager = notes_manager
        self.current_course_id = None
        self.app_settings = AppSettings() 
        self.init_ui()
        # Connect the itemChanged signal so edits are handled properly
        self.model.itemChanged.connect(self.on_item_changed)
        self.list_view.selectionModel().selectionChanged.connect(self.on_selection_changed)
        self.list_view.doubleClicked.connect(self.on_double_click)
        self.load_new_course()

        # Add shortcuts for navigation (left/right arrow keys)
        self.shortcut_prev = QtWidgets.QShortcut(QtGui.QKeySequence("Left"), self)
        self.shortcut_prev.activated.connect(self._handle_prev_shortcut)
        self.shortcut_next = QtWidgets.QShortcut(QtGui.QKeySequence("Right"), self)
        self.shortcut_next.activated.connect(self._handle_next_shortcut)
        
        self.load_previous_course_and_focus()
        

    def init_ui(self):
        layout = QtWidgets.QVBoxLayout(self)

        # Top input field with navigation buttons
        self.course_input = QtWidgets.QLineEdit()
        self.prev_button = QtWidgets.QPushButton("<-")
        self.next_button = QtWidgets.QPushButton("->")
        # Make navigation buttons as small as possible
        self.prev_button.setFixedSize(25, 25)
        self.next_button.setFixedSize(25, 25)
        nav_layout = QtWidgets.QHBoxLayout()
        nav_layout.addWidget(self.prev_button)
        nav_layout.addWidget(self.course_input)
        nav_layout.addWidget(self.next_button)
        layout.addLayout(nav_layout)

        # List view and model
        self.model = QtGui.QStandardItemModel()
        self.list_view = QtWidgets.QListView()
        self.list_view.setModel(self.model)
        self.list_view.setEditTriggers(
            QtWidgets.QAbstractItemView.DoubleClicked | 
            QtWidgets.QAbstractItemView.EditKeyPressed 
        )
        self.list_view.installEventFilter(self)
        layout.addWidget(self.list_view)
        #rtl 
        self.list_view.setLayoutDirection(QtCore.Qt.RightToLeft)
        self.list_view.setStyleSheet("""
            QListView {
                font-family: 'Amiri';
                font-size: 14pt;
                padding-right: 10px;
            }
        """)

        # Status label (for validation and course messages)
        self.status_label = QtWidgets.QLabel("")
        layout.addWidget(self.status_label)

        # Custom button layout: Save - New - OK
        button_layout = QtWidgets.QHBoxLayout()
        self.save_button = QtWidgets.QPushButton("Save")
        self.new_button = QtWidgets.QPushButton("New")  # Add new button
        ok_button = QtWidgets.QPushButton("OK")


        
        button_layout.addWidget(self.save_button)
        button_layout.addWidget(self.new_button)       # Add New button
        button_layout.addStretch()                     # Pushes OK to right
        button_layout.addWidget(ok_button)

        self.print_button = QtWidgets.QPushButton("Print")
        button_layout.addWidget(self.print_button)
        self.print_button.clicked.connect(self.print_course)

        
        layout.addLayout(button_layout)

        # Connect buttons
        self.save_button.clicked.connect(self.save_course)
        self.new_button.clicked.connect(self.create_new_course)  # New connection
        ok_button.clicked.connect(self.accept)

        # Navigation button connections using helper functions for focus
        self.prev_button.clicked.connect(self.load_previous_course_and_focus)
        self.next_button.clicked.connect(self.load_next_course_and_focus)

    def on_double_click(self, index):
        """Handle double click to start editing"""
        if index.isValid():
            self.start_editing(index)

    def start_editing(self, index=None):
        """Safe editing with existence check"""
        if not index:
            index = self.list_view.currentIndex()
        
        if index.isValid():
            # Verify item still exists in model
            if index.row() >= self.model.rowCount():
                return
                
            item = self.model.itemFromIndex(index)
            if item:  # Additional null check
                current_text = item.text().strip()
                
                # Clear placeholder if needed
                if current_text == self.PLACEHOLDER_TEXT:
                    self.model.blockSignals(True)
                    item.setText("")
                    item.setForeground(QtGui.QColor(self.palette().text().color()))
                    self.model.blockSignals(False)
                
                # Start editing only if item exists
                self.list_view.edit(index)

    def load_previous_course_and_focus(self):
        self.load_previous_course()
        self.list_view.setFocus()

    def load_next_course_and_focus(self):
        self.load_next_course()
        self.list_view.setFocus()

    def _handle_prev_shortcut(self):
        if self.prev_button.isEnabled():
            self.load_previous_course_and_focus()

    def _handle_next_shortcut(self):
        if self.next_button.isEnabled():
            self.load_next_course_and_focus()

    def create_new_course(self):
        """Handle creation of new empty course"""
        # Create new course through manager
        new_id = self.notes_manager.create_new_course()
        
        # Load the newly created course
        self.current_course_id = new_id
        self.load_new_course()
        
        # Update UI
        self.course_input.clear()
        self.update_status("New course created")
        self.update_navigation_buttons()
        
    def update_status(self, message):
        self.status_label.setText(message)

    def add_empty_item(self):
        """Append an empty, editable item with placeholder text"""
        item = QtGui.QStandardItem(self.PLACEHOLDER_TEXT)
        item.setEditable(True)
        item.setForeground(QtGui.QColor(QtCore.Qt.gray))
        self.model.appendRow(item)

    def ensure_extra_row(self):
        """Ensure there is always an extra empty row at the bottom."""
        if self.model.rowCount() == 0:
            self.add_empty_item()
        else:
            last_item = self.model.item(self.model.rowCount() - 1)
            if last_item.text().strip() != "" and last_item.text().strip() != self.PLACEHOLDER_TEXT:
                self.add_empty_item()

    def remove_item(self, row):
        """Remove the item at the specified row and ensure an extra row exists."""
        self.model.blockSignals(True)
        self.model.removeRow(row)
        self.model.blockSignals(False)
        self.model.layoutChanged.emit() 

    def safe_remove_item(self, row):
        """Safely remove item after validation"""
        try:
            # Check if row still exists
            if row < self.model.rowCount():
                self.remove_item(row)
                self.ensure_extra_row()
        except Exception as e:
            print(f"Error removing item: {str(e)}")

    def on_selection_changed(self, selected, deselected):
        # For newly selected items, update search items' text to include the query.
        for index in selected.indexes():
            item = self.model.itemFromIndex(index)
            data = item.data(QtCore.Qt.UserRole)
            if data and data.get("type") == "search":
                new_text = "بحث عن " + data.get("query", "")
                self.model.blockSignals(True)
                item.setText(new_text)
                self.model.blockSignals(False)
        # For items that are no longer selected, revert search items' text back to "بحث".
        for index in deselected.indexes():
            item = self.model.itemFromIndex(index)
            data = item.data(QtCore.Qt.UserRole)
            if data and data.get("type") == "search":
                self.model.blockSignals(True)
                item.setText("بحث")
                self.model.blockSignals(False)

    def update_item_alignment(self, index):
        item = self.model.itemFromIndex(index)
        if item:
            item.setTextAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)

    def on_item_changed(self, item):
        text = item.text().strip()
        row = self.model.indexFromItem(item).row()

        # Handle placeholder text
        if text == self.PLACEHOLDER_TEXT:
            text = ""
        if text == "":
            QtCore.QTimer.singleShot(0, lambda r=row: self.safe_remove_item(r))
            return

        # Validate input
        parts = text.split()
        if len(parts) == 0:
            return

        try:
            if parts[0].lower() == "a":
                if len(parts) not in (3, 4):
                    self.update_status("Invalid format. Use 'a surah ayah' or 'a surah start end'.")
                    return

                self.model.blockSignals(True)
                try:
                    surah = int(parts[1])
                    start = int(parts[2])
                    end = int(parts[3]) if len(parts) == 4 else start
                    chapter_name = self.parent().search_engine.get_chapter_name(surah)
                    formatted = f"{chapter_name} آية {start}-{end}" if start != end else f"{chapter_name} آية {start}"
                    item.setText(formatted)
                    item.setData({'type': 'ayah', 'surah': surah, 'start': start, 'end': end}, QtCore.Qt.UserRole)
                    #item.setForeground(QtGui.QColor(self.palette().text().color()))
                    self.update_status("Valid input.")
                finally:
                    self.model.blockSignals(False)
            elif parts[0].lower() == "s":
                self.model.blockSignals(True)
                try:
                    query = " ".join(parts[1:])
                    item.setText("بحث")
                    item.setData({'type': 'search', 'query': query}, QtCore.Qt.UserRole)
                    #item.setForeground(QtGui.QColor(self.palette().text().color()))
                    self.update_status("Valid input.")
                finally:
                    self.model.blockSignals(False)
            else:
                self.update_status("Invalid input. Use 'a' or 's' as prefixes.")

        except ValueError as e:
            self.update_status(f"Invalid numbers: {str(e)}")
        except Exception as e:
            self.update_status(f"Error: {str(e)}")

        self.ensure_extra_row()

    def handle_f2_edit(self):
        index = self.list_view.currentIndex()
        if index.isValid():
            item = self.model.itemFromIndex(index)
            if item.text() == self.PLACEHOLDER_TEXT:
                item.setText("")
                item.setForeground(QtGui.QColor(self.palette().text().color()))
            self.list_view.edit(index)

    def eventFilter(self, source, event):
        if source is self.list_view and event.type() == QtCore.QEvent.KeyPress:
            # Check for Ctrl+Delete first
            if event.key() == QtCore.Qt.Key_Delete and event.modifiers() & QtCore.Qt.ControlModifier:
                self.delete_current_course()
                return True
            if event.key() in (QtCore.Qt.Key_Return, QtCore.Qt.Key_Enter):
                index = self.list_view.currentIndex()
                if index.isValid():
                    item = self.model.itemFromIndex(index)
                    current_text = item.text().strip()
                    
                    if current_text == self.PLACEHOLDER_TEXT:
                        # Clear placeholder and start editing
                        self.model.blockSignals(True)
                        item.setText("")
                        item.setForeground(QtGui.QColor(self.palette().text().color()))
                        self.model.blockSignals(False)
                        self.list_view.edit(index)
                        return True
                    
                    # # Validate before closing editor
                    # self.validate_and_format_item(item)
                    # return True
                    
                    data = item.data(QtCore.Qt.UserRole)
                    if data:
                        if data['type'] == 'ayah':
                            self.play_requested.emit(data['surah'], data['start'], data['end'])
                        elif data['type'] == 'search':
                            self.search_requested.emit(data['query'])
                return True
            if event.key() == QtCore.Qt.Key_F2:
                self.handle_f2_edit()
                return True
            if event.key() == QtCore.Qt.Key_Delete:
                index = self.list_view.currentIndex()
                if index.isValid():
                    row = index.row()
                    self.safe_remove_item(row)
                return True
            # Add Ctrl+Up/Down handling
            if event.modifiers() & QtCore.Qt.ControlModifier:
                if event.key() == QtCore.Qt.Key_Up:
                    self.move_item_up()
                    return True
                elif event.key() == QtCore.Qt.Key_Down:
                    self.move_item_down()
                    return True
        return super().eventFilter(source, event)

    def load_new_course(self):
        self.current_course_id, course = self.notes_manager.get_new_course()
        self.load_course(course)
    
    def load_course_by_id(self, course_id):
        """Load a course by its ID"""
        courses = self.notes_manager.get_all_courses()
        for c in courses:
            if c[0] == course_id:
                self.current_course_id = c[0]
                self.load_course({'title': c[1], 'items': c[2]})
                break

    def load_previous_course(self):
        prev_id, prev_course = self.notes_manager.get_previous_course(self.current_course_id)
        if prev_id == self.current_course_id:  # No more previous courses
            return
        self.current_course_id = prev_id
        self.load_course(prev_course)
        self.update_navigation_buttons()

    def load_next_course(self):
        next_id, next_course = self.notes_manager.get_next_course(self.current_course_id)
        if next_id == self.current_course_id:  # No more next courses
            return
        self.current_course_id = next_id
        self.load_course(next_course)
        self.update_navigation_buttons()

    def update_navigation_buttons(self):
        """Enable/disable buttons based on course position"""
        # Handle new course (ID None) case
        if self.current_course_id is None:
            # Check if any courses exist at all
            has_any = self.notes_manager.has_any_courses()
            self.prev_button.setEnabled(has_any)  # Can go to last existing course
            self.next_button.setEnabled(False)    # No next after new course
        else:
            # Existing course logic
            has_prev = self.notes_manager.has_previous_course(self.current_course_id)
            has_next = self.notes_manager.has_next_course(self.current_course_id)
            self.prev_button.setEnabled(has_prev)
            self.next_button.setEnabled(has_next)

    def load_course(self, course):
        self.model.clear()
        self.course_input.setText(course['title'])
        
        for item_str in course['items']:
            try:
                item_data = json.loads(item_str)
                user_data = item_data.get("user_data")
                text = self.format_display_text(item_data)
            except Exception:
                text = item_str
                user_data = None

            list_item = QtGui.QStandardItem(text)
            if user_data:
                list_item.setData(user_data, QtCore.Qt.UserRole)
            self.model.appendRow(list_item)
        
        self.add_empty_item()
        self.update_status(f"Loaded course ID: {self.current_course_id}")
        self.update_navigation_buttons()

    def format_display_text(self, item_data):
        """Convert stored data to display text with chapter names"""
        user_data = item_data.get("user_data")
        if not user_data:
            return item_data.get("text", "")
            
        if user_data.get('type') == 'ayah':
            surah = user_data['surah']
            chapter_name = self.parent().search_engine.get_chapter_name(surah)
            start = user_data['start']
            end = user_data.get('end', start)
            
            if start == end:
                return f"{chapter_name} آية {start}"
            return f"{chapter_name} آية {start}-{end}"
            
        if user_data.get('type') == 'search':
            return f"بحث عن {user_data.get('query', '')}"
            
        return item_data.get("text", "")

    def save_course(self):
        title = self.course_input.text().strip() or f"درس رقم {self.current_course_id or 'NEW'}"
        items = []
        has_valid_items = False
        
        for row in range(self.model.rowCount()):
            item = self.model.item(row)
            text = item.text().strip()
            
            # Skip placeholder text and empty items
            if text == self.PLACEHOLDER_TEXT or not text:
                continue
                
            # Track if we have any valid items
            has_valid_items = True
            
            user_data = item.data(QtCore.Qt.UserRole)
            if user_data is not None:
                items.append(json.dumps({"text": item.text(), "user_data": user_data}))
            else:
                items.append(json.dumps({"text": item.text()}))
        
        if has_valid_items:
            new_id = self.notes_manager.save_course(self.current_course_id, title, items)
            self.current_course_id = new_id
            self.update_status("Course saved.")
        else:
            self.notes_manager.delete_course(self.current_course_id)
            self.update_status("Course deleted (no valid items).")

    def save_and_close(self):
        self.save_course()
        self.accept()

    def delete_current_course(self):
        if self.current_course_id is not None:
            reply = QtWidgets.QMessageBox.question(
                self,
                "Confirm Deletion",
                f"هل تريد حقا حذف درس :  {self.course_input.text()} ؟",
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                QtWidgets.QMessageBox.No
            )
            if reply == QtWidgets.QMessageBox.Yes:
                self.notes_manager.delete_course(self.current_course_id)
                self.update_status("Current course deleted.")
                self.load_new_course()  # Load a new course after deletion
            else:
                self.update_status("Course deletion canceled.")
        else:
            self.update_status("No current course to delete.")

    
    def move_item_up(self):
        current_row = self.list_view.currentIndex().row()
        if current_row > 0:
            self._swap_items(current_row, current_row - 1)
            self.list_view.setCurrentIndex(self.model.index(current_row - 1, 0))

    def move_item_down(self):
        current_row = self.list_view.currentIndex().row()
        if current_row < self.model.rowCount() - 1:
            self._swap_items(current_row, current_row + 1)
            self.list_view.setCurrentIndex(self.model.index(current_row + 1, 0))

    def _swap_items(self, row1, row2):
        # Handle downward movement adjustment
        if row2 > row1:
            row2 -= 1
        
        # Swap rows using model methods
        item1 = self.model.takeRow(row1)
        item2 = self.model.takeRow(row2)
        self.model.insertRow(row2, item1)
        self.model.insertRow(row1, item2)

    def print_course(self):
        items = []
        for row in range(self.model.rowCount()):
            item = self.model.item(row)
            data = item.data(QtCore.Qt.UserRole)
            if data:
                items.append(data)
        
        output = []
        search_engine = self.parent().search_engine
        
        for item in items:
            if item['type'] == 'ayah':
                verses = search_engine.search_by_surah_ayah(
                    item['surah'], item['start'], item.get('end', item['start'])
                )
                output.extend([v['text_uthmani'] for v in verses])
                output.extend(["========================================================================",])
            elif item['type'] == 'search':
                results = search_engine.search_verses(item['query'])
                output.extend(["========================================================================",])
                output.extend([f"بحث عن : {item['query']}",])
                output.extend(["========================================================================",])
                output.extend([v['text_uthmani'] for v in results])
        title = self.course_input.text()
        last_dir = self.app_settings.get_last_directory()
        file_path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Save Course Text", 
            f"{last_dir}/{title}.txt",
            "Text Files (*.txt)"
        )


        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write('\n'.join(output))
                self.parent().showMessage(f"Course saved to {file_path}", 5000)
            except Exception as e:
                self.parent().showMessage(f"Error saving file: {str(e)}", 5000, bg="red")

