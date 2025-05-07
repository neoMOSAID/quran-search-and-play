
import json

from PyQt5 import QtCore, QtWidgets, QtGui
from utils.settings import AppSettings


class CourseItemDelegate(QtWidgets.QStyledItemDelegate):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent

    def paint(self, painter, option, index):
        item = index.data(QtCore.Qt.UserRole)
        #item_type = item.get('data',{}).get('type','ayah')
        if not isinstance(item, dict):
            return super().paint(painter, option, index)
        
        painter.save()

        # Set background color
        # bg_color = {
        #     'note': QtGui.QColor('#E8F5E9'),
        #     'ayah': QtGui.QColor('#E3F2FD'),
        #     'search': QtGui.QColor('#FFF8E1')
        # }.get(item_type, QtCore.Qt.white)
        # painter.fillRect(option.rect, bg_color)

        # Draw type icon
        icon_rect = QtCore.QRect(option.rect.left() + 5, option.rect.top() + 5, 32, 32)
        icons = {
            'note': QtWidgets.QStyle.SP_FileDialogListView,
            'ayah': QtWidgets.QStyle.SP_DialogSaveButton,
            'search': QtWidgets.QStyle.SP_FileDialogContentsView
        }
        self.parent.style().drawControl(
            QtWidgets.QStyle.CE_ItemViewItem,
            option,
            painter,
            None
        )

        # Draw text content
        text_rect = QtCore.QRect(option.rect.left() + 40, option.rect.top() + 5, 
                               option.rect.width() - 45, option.rect.height() )
        painter.setPen(QtCore.Qt.black)
        painter.drawText(text_rect, QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter | QtCore.Qt.TextWordWrap,
                     self._get_preview_text(item))

        painter.restore()

    def _get_preview_text(self, item):
        data = item.get('data') or item.get('user_data')
        item_type = data.get('type','ayah')
        if item_type == 'note':
            return f"...{data['content'][:30]}"
        elif item_type == 'ayah':
            surah = data.get('surah') 
            start = data.get('start') 
            end = data.get('end') 
            if surah and start:
                chapter = self.parent.search_engine.get_chapter_name(surah)
                if start == end:
                    tt = f"الآية {start}"
                else:
                    tt = f"الآيات {start} - {end}"
                return f"سورة {chapter}  {tt}"
        elif item_type == 'search':
            return f"بحث: {data['query']}"
        return ''

    def createEditor(self, parent, option, index):
        item = index.data(QtCore.Qt.UserRole)
        if item.get('type') == 'note':
            editor = QtWidgets.QTextEdit(parent)
            return editor
        return super().createEditor(parent, option, index)


    def setEditorData(self, editor, index):
        item = index.data(QtCore.Qt.UserRole)
        if item.get('type') == 'note':
            editor.setText(item.get('data', {}).get('content', ''))

    def setModelData(self, editor, model, index):
        item = index.data(QtCore.Qt.UserRole)
        if item.get('type') == 'note':
            new_data = {
                **item,
                'data': {
                    **item.get('data', {}),
                    'content': editor.toPlainText()
                }
            }
            model.setData(index, new_data, QtCore.Qt.UserRole)

    def editorEvent(self, event, model, option, index):
        # Disable direct in-place editing
        return False



# Add this custom layout class at the top of your file
class FlowLayout(QtWidgets.QLayout):
    def __init__(self, parent=None, margin=0, spacing=-1):
        super().__init__(parent)
        self._items = []
        self.setContentsMargins(margin, margin, margin, margin)
        self.setSpacing(spacing)

    def addItem(self, item):
        self._items.append(item)

    def count(self):
        return len(self._items)

    def itemAt(self, index):
        if 0 <= index < len(self._items):
            return self._items[index]
        return None

    def takeAt(self, index):
        if 0 <= index < len(self._items):
            return self._items.pop(index)
        return None

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self._doLayout(QtCore.QRect(0, 0, width, 0), True)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._doLayout(rect, False)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        size = QtCore.QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        margin = self.contentsMargins().left()
        return size + QtCore.QSize(2 * margin, 2 * margin)

    def _doLayout(self, rect, testOnly):
        x = rect.x()
        y = rect.y()
        line_height = 0
        spacing = self.spacing()
        
        for item in self._items:
            wid = item.widget()
            space_x = spacing + wid.style().layoutSpacing(
                QtWidgets.QSizePolicy.PushButton,
                QtWidgets.QSizePolicy.PushButton,
                QtCore.Qt.Horizontal
            )
            space_y = spacing + wid.style().layoutSpacing(
                QtWidgets.QSizePolicy.PushButton,
                QtWidgets.QSizePolicy.PushButton,
                QtCore.Qt.Vertical
            )
            
            next_x = x + item.sizeHint().width() + space_x
            if next_x - space_x > rect.right() and line_height > 0:
                x = rect.x()
                y = y + line_height + space_y
                next_x = x + item.sizeHint().width() + space_x
                line_height = 0

            if not testOnly:
                item.setGeometry(QtCore.QRect(
                    QtCore.QPoint(x, y),
                    item.sizeHint()
                ))

            x = next_x
            line_height = max(line_height, item.sizeHint().height())

        return y + line_height - rect.y()



class CourseManagerDialog(QtWidgets.QDialog):
    course_modified = QtCore.pyqtSignal()
    play_requested = QtCore.pyqtSignal(int, int, int)  
    search_requested = QtCore.pyqtSignal(str)

    def __init__(self, db, search_engine, parent=None):
        super().__init__(parent)
        self.db = db
        self.search_engine = search_engine
        self.app_settings = AppSettings() 
        self.current_course = None
        self.preview_was_visible = False
        self.init_ui()
        self.load_initial_courses() 
        self.list_view.setFocus() 

    def init_ui(self):
        self.setWindowTitle("دروس القرآن")
        self.resize(800, 600)
        layout = QtWidgets.QVBoxLayout()

        # Header
        self.title_edit = QtWidgets.QLineEdit()
        self.title_edit.setPlaceholderText("Course Title")
        self.prev_btn = QtWidgets.QPushButton("←")
        self.next_btn = QtWidgets.QPushButton("→")
        self.prev_btn.clicked.connect(self.load_previous_course)
        self.next_btn.clicked.connect(self.load_next_course)
        
        # 
        nav_layout = QtWidgets.QHBoxLayout()
        nav_layout.addWidget(self.prev_btn)
        nav_layout.addWidget(self.title_edit)
        nav_layout.addWidget(self.next_btn)

        self.prev_btn.setFixedSize(25, 25)
        self.next_btn.setFixedSize(25, 25)

        # nav_layout.setStretch(0, 1)
        # nav_layout.setStretch(1, 8)
        # nav_layout.setStretch(2, 1)
        layout.addLayout(nav_layout)

        # List View
        self.list_view = QtWidgets.QListView()
        self.model = QtGui.QStandardItemModel()
        self.list_view.setModel(self.model)
        self.delegate = CourseItemDelegate(parent=self)
        self.list_view.setItemDelegate(self.delegate)
        self.list_view.setSelectionMode(QtWidgets.QListView.SingleSelection)
        self.list_view.setDragDropMode(QtWidgets.QListView.InternalMove)
        self.list_view.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.list_view.setAcceptDrops(True)
        self.list_view.setDropIndicatorShown(True)
        self.list_view.setLayoutDirection(QtCore.Qt.RightToLeft)
        self.list_view.setStyleSheet("""
            QListView {
                font-family: 'Amiri';
                font-size: 14pt;
                padding-right: 10px;
                text-align: right;
            }
        """)

        self.preview_edit = QtWidgets.QTextEdit()
        self.preview_edit.setReadOnly(True)

        self.preview_edit.setStyleSheet("""
            QTextEdit {
                font-family: 'Amiri';
                font-size: 14pt;
                padding: 10px;
            }
        """)

        splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)

        splitter.addWidget(self.list_view)
        splitter.addWidget(self.preview_edit)
        splitter.setSizes([int(self.width()*0.3), int(self.width()*0.7)])
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)

        self.list_view.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding,
            QtWidgets.QSizePolicy.Expanding
        )

        layout.addWidget(splitter)

        # Control Buttons
        self.add_note_btn = QtWidgets.QPushButton("Add Note")
        self.add_note_btn.clicked.connect(self.add_note)
        self.remove_btn = QtWidgets.QPushButton("Remove")
        self.remove_btn.clicked.connect(self.remove_item)
        self.move_up_btn = QtWidgets.QPushButton("Move Up")
        self.move_up_btn.clicked.connect(lambda: self.move_item(-1))
        self.move_down_btn = QtWidgets.QPushButton("Move Down")
        self.move_down_btn.clicked.connect(lambda: self.move_item(1))
        self.play_checkbox = QtWidgets.QCheckBox("Auto-Play")
        self.play_checkbox.setChecked(False)
        self.preview_check = QtWidgets.QCheckBox("Preview")
        self.preview_check.setChecked(False)

        button_container = QtWidgets.QWidget()
        btn_layout = FlowLayout(button_container, margin=2, spacing=4)  

        button_container.setStyleSheet("""
            QPushButton {
                padding: 2px 5px;
                margin: 1px;
                font-size: 12px;
                min-height: 22px;
            }
            QCheckBox {
                spacing: 4px;
                font-size: 12px;
            }
        """)

        btn_layout.addWidget(self.add_note_btn)
        btn_layout.addWidget(self.remove_btn)
        btn_layout.addWidget(self.move_up_btn)
        btn_layout.addWidget(self.move_down_btn)
        btn_layout.addWidget(self.play_checkbox)
        btn_layout.addWidget(self.preview_check)
        

        button_container.setMaximumHeight(60) 
        button_container.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding,
            QtWidgets.QSizePolicy.Fixed
        )

        layout.addWidget(button_container)

        # Dialog Buttons
        dialog_btn = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Save | QtWidgets.QDialogButtonBox.Close)

        self.print_btn = QtWidgets.QPushButton("Print")
        self.print_btn.clicked.connect(self.print_course)

        dialog_btn.addButton(self.print_btn, QtWidgets.QDialogButtonBox.ActionRole)

        # Compact styling
        dialog_btn.setStyleSheet("""
            QPushButton {
                min-width: 70px;
                max-width: 90px;
                padding: 2px 5px;
                margin: 1px;
            }
            QDialogButtonBox {
                spacing: 4px;
            }
        """)

        dialog_btn.setCenterButtons(True)
        dialog_btn.accepted.connect(self.save_course)
        dialog_btn.rejected.connect(self.reject)

        # Create container for centering
        # Create compact container
        btn_container = QtWidgets.QWidget()
        btn_container.setFixedHeight(32)  # Set fixed height
        btn_container_layout = QtWidgets.QHBoxLayout(btn_container)
        btn_container_layout.setContentsMargins(0, 0, 0, 0)  # Remove margins
        btn_container_layout.setSpacing(4)
        btn_container_layout.addWidget(dialog_btn)
        btn_container_layout.setAlignment(QtCore.Qt.AlignCenter)

        layout.addWidget(btn_container) 

        # connections
        self.list_view.installEventFilter(self)
        self.list_view.doubleClicked.connect(self.handle_enter_key)
        self.list_view.selectionModel().currentChanged.connect(self.handle_selection_changed)
        self.preview_edit.textChanged.connect(self.handle_text_edit)
        self.preview_check.toggled.connect(self.on_preview_toggled)

        self.setLayout(layout)


    def load_initial_courses(self):
        """Load first course or create new one"""
        if self.db.has_any_courses():
            courses = self.db.get_all_courses()
            if courses:
                self.load_course(courses[0][0])
        else:
            course_id = self.db.create_new_course()
            self.current_course = self.db.get_course(course_id)
        self.update_navigation_buttons()

    def load_course(self, course_id):
        """Load a course by ID with proper item deserialization"""
        if not course_id:
            return
        self.current_course = self.db.get_course(course_id)
        self.title_edit.setText(self.current_course['title'])
        self.model.clear()
        
        for item in self.current_course['items']:
            # Handle legacy string format if needed
            if isinstance(item, str):
                try:
                    item = json.loads(item)
                except json.JSONDecodeError:
                    continue
                    
            list_item = QtGui.QStandardItem(item.get('text', ''))
            list_item.setData(item, QtCore.Qt.UserRole)
            self.model.appendRow(list_item)
        
        self.update_navigation_buttons()
        self.list_view.setFocus()    

    def _add_item_to_model(self, item):
        list_item = QtGui.QStandardItem()
        list_item.setData(item, QtCore.Qt.UserRole)
        list_item.setEditable(False)
        self.model.appendRow(list_item)

    def add_note(self):
        new_note = {
            'type': 'note',
            'user_data': {
                'type': 'note',
                'content': 'New note - click to edit',
                'timestamp': QtCore.QDateTime.currentDateTime().toString()
            }
        }
        item = QtGui.QStandardItem("New Note")
        item.setData(new_note, QtCore.Qt.UserRole)
        item.setEditable(False)  # Let delegate handle editing
        self.model.appendRow(item)
        
        # Select and scroll to new item
        index = self.model.index(self.model.rowCount()-1, 0)
        self.list_view.setCurrentIndex(index)
        self.list_view.scrollTo(index)

    def add_ayah_range(self, surah, start, end):
        ayah_item = {
            'type': 'ayah',
            'data': {
                'surah': surah,
                'start': start,
                'end': end
            },
            'timestamp': QtCore.QDateTime.currentDateTime().toString()
        }
        self._add_item_to_model(ayah_item)

    def add_search(self, query):
        search_item = {
            'type': 'search',
            'data': {'query': query},
            'timestamp': QtCore.QDateTime.currentDateTime().toString()
        }
        self._add_item_to_model(search_item)

    def remove_item(self):
        index = self.list_view.currentIndex()
        if index.isValid():
            self.model.removeRow(index.row())

    def move_item(self, direction):
        row = self.list_view.currentIndex().row()
        if 0 <= row + direction < self.model.rowCount():
            item = self.model.takeRow(row)
            self.model.insertRow(row + direction, item)
            self.list_view.setCurrentIndex(self.model.index(row + direction, 0))

    def save_course(self):
        items = []
        for row in range(self.model.rowCount()):
            item = self.model.item(row).data(QtCore.Qt.UserRole)
            items.append(item)
        
        course_title = self.title_edit.text()
        
        if self.current_course:
            course_id = self.current_course['id']
        else:
            course_id = None
            
        new_id = self.db.save_course(course_id, course_title, items)
        self.current_course = self.db.get_course(new_id)
        self.course_modified.emit()

    def load_previous_course(self):
        if not self.current_course:
            return
            
        prev_info = self.db.get_previous_course(self.current_course['id'])
        if prev_info:
            prev_id, _ = prev_info
            self.load_course(prev_id)
            self.update_navigation_buttons()

    def load_next_course(self):
        if not self.current_course:
            return
            
        next_info = self.db.get_next_course(self.current_course['id'])
        if next_info:
            next_id, _ = next_info
            self.load_course(next_id)
            self.update_navigation_buttons()

    def update_navigation_buttons(self):
        """Properly update button states"""
        if self.current_course:
            has_prev = self.db.has_previous_course(self.current_course['id'])
            has_next = self.db.has_next_course(self.current_course['id'])
            self.prev_btn.setEnabled(has_prev)
            self.next_btn.setEnabled(has_next)
        else:
            self.prev_btn.setEnabled(False)
            self.next_btn.setEnabled(False)    

    def on_preview_toggled(self, checked):
        """Handle preview checkbox changes"""
        if checked:
            self.preview_edit.show()
            self.resize(800, 600) 
        else:
            # Only hide if not showing a note
            current_index = self.list_view.currentIndex()
            if current_index.isValid():
                item = self.model.itemFromIndex(current_index)
                data = item.data(QtCore.Qt.UserRole)
                if data.get('type') != 'note':
                    self.preview_edit.hide()
                    self.resize(250, 350) 

    def handle_enter_key(self):
        index = self.list_view.currentIndex()
        if index.isValid():
            item = self.model.itemFromIndex(index).data(QtCore.Qt.UserRole)
            data = item.get('data') or item.get('user_data')
            if data:
                if data['type'] == 'ayah':
                    # Load full ayah range in main window
                    surah = data['surah']
                    start = data['start']
                    end = data.get('end', start)
                    
                    # Set search method and query
                    self.parent().search_method_combo.setCurrentText("Surah FirstAyah LastAyah")
                    self.parent().search_input.setText(f"{surah} {start} {end}")
                    self.parent().search()
                    
                    # Conditionally play audio
                    if self.play_checkbox.isChecked():
                        self.play_requested.emit(surah, start, end) 

                elif data['type'] == 'search':
                    idx = self.parent().search_method_combo.findText("Text", QtCore.Qt.MatchFixedString)
                    if idx >= 0:
                        self.parent().search_method_combo.setCurrentIndex(idx)
                    self.search_requested.emit(data['query'])
                
                elif data['type'] == 'note':
                    return

    def handle_selection_changed(self, current, previous):
        item = self.model.itemFromIndex(current)
        if not item:
            return

        # Store previous visibility state
        self.preview_was_visible = self.preview_edit.isVisible()
           
        data = item.data(QtCore.Qt.UserRole)
        item_type = data.get('data') or data.get('user_data')
        item_type = item_type.get('type','ayah')
        self.current_item = data        
        # Set preview content based on item type
        if item_type == 'note':
            if not self.preview_edit.isVisible():
                self.preview_edit.show()
            self.preview_edit.setPlainText(data.get('user_data', {}).get('content', ''))
            self.preview_edit.setReadOnly(False)
            return
        else:
            if self.preview_check.isChecked():
                self.preview_edit.show()
            else:
                self.preview_edit.hide()
        if item_type == 'ayah':
            self.show_ayah_preview(data)
            self.preview_edit.setReadOnly(True)
        elif item_type == 'search':
            query = data.get('data') or data.get('user_data')
            query = query.get('query', '')
            self.show_search_results(query)
            self.preview_edit.setReadOnly(True)

    def show_ayah_preview(self, data):
        inner_data = data.get('data', {})
        user_data = data.get('user_data', {})

        surah = inner_data.get('surah') or user_data.get('surah')
        start = inner_data.get('start') or user_data.get('start')
        end = inner_data.get('end') or user_data.get('end')
        if surah and start:
            verses = self.search_engine.search_by_surah_ayah(surah, start, end)
        
            preview_text = "\n".join(
                [f"{v['text_uthmani']} ({self.search_engine.get_chapter_name(surah)} {v['ayah']})" 
                for v in verses]
            )
            self.preview_edit.setPlainText(preview_text)

    def handle_text_edit(self):
        index = self.list_view.currentIndex()
        if not index.isValid():
            return

        item = self.model.itemFromIndex(index)
        note_data = item.data(QtCore.Qt.UserRole)
        
        if note_data.get('type') == 'note':
            new_content = self.preview_edit.toPlainText()
            note_data['user_data']['content'] = new_content
            item.setData(note_data, QtCore.Qt.UserRole)
            
            # Update display text
            preview = new_content.split('\n')[0][:30] + ('...' if len(new_content) > 30 else '')
            item.setText(f"Note: {preview}")

    def show_search_results(self, query):
        """Show actual search results in preview"""
        import re
        results, _ = self.search_engine.search_verses(query)
        output = []
        
        for verse in results:
            text = re.sub(r'<[^>]+>', '', verse['text_uthmani'])
            output.append(
                f"{text} ({verse['chapter']} {verse['ayah']})"
            )
        
        self.preview_edit.setPlainText("\n".join(output))

    def eventFilter(self, source, event):
        if event.type() == QtCore.QEvent.KeyPress:
            # Handle Enter key
            if event.key() in (QtCore.Qt.Key_Return, QtCore.Qt.Key_Enter):
                self.handle_enter_key()
                return True
                
            # Handle F2 editing
            if event.key() == QtCore.Qt.Key_F2:
                self.start_editing()
                return True
                
            # Handle navigation
            if event.key() == QtCore.Qt.Key_Left:
                self.load_previous_course()
                return True
            if event.key() == QtCore.Qt.Key_Right:
                self.load_next_course()
                return True
                
            # Handle item movement
            if event.modifiers() & QtCore.Qt.ControlModifier:
                if event.key() == QtCore.Qt.Key_Up:
                    self.move_item_up()
                    return True
                if event.key() == QtCore.Qt.Key_Down:
                    self.move_item_down()
                    return True
                    
        return super().eventFilter(source, event)

    def print_course(self):
        import re

        def strip_html_tags(text):
            clean = re.compile('<.*?>')
            return re.sub(clean, '', text)

        items = []
        for row in range(self.model.rowCount()):
            item = self.model.item(row)
            data = item.data(QtCore.Qt.UserRole)
            if data:
                items.append(data)
        
        output = []
        title = self.title_edit.text()
        search_engine = self.parent().search_engine
        output.extend(["",])
        output.extend(["========================================================================",])
        output.extend([f"درس: {title}",])
        output.extend(["========================================================================",])

        for item in items:
            item = item['user_data']
            if item['type'] == 'note':
                output.extend([item['content']])
            elif item['type'] == 'ayah':
                surah = item['surah']
                start = item['start']
                end = item.get('end', start)
                verses = search_engine.search_by_surah_ayah(surah, start, end)
                
                # Collect all verse texts
                verse_texts = [strip_html_tags(v['text_uthmani']) for v in verses]
                
                # Add reference to last verse
                if verse_texts:
                    chapter_name = search_engine.get_chapter_name(surah)
                    range_info = f"آية {start}" if start == end else f"الآيات {start}-{end}"
                    verse_texts[-1] += f" ({chapter_name} {range_info})"
                
                output.extend(["========================================================================",])
                output.extend(verse_texts)
                
            elif item['type'] == 'search':
                results = search_engine.search_verses(item['query'])
                output.extend(["========================================================================",])
                output.extend([f"بحث عن : {item['query']}",])
                output.extend(["========================================================================",])
                for v in results:
                    chapter_name = search_engine.get_chapter_name(v['surah'])
                    ayah_text = strip_html_tags(v['text_uthmani'])
                    output.append(f"{ayah_text} ({chapter_name} آية {v['ayah']})")
        
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
       