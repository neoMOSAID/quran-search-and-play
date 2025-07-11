
import json
import os
import glob
from datetime import datetime

from PyQt5 import QtCore, QtWidgets, QtGui
from utils.settings import AppSettings
from views.dialogs.select_course import CourseSelectionDialog

class CourseItemDelegate(QtWidgets.QStyledItemDelegate):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent

    def paint(self, painter, option, index):
        item = index.data(QtCore.Qt.UserRole)
        #item_type = item.get('data',{}).get('type','ayah')
        if not isinstance(item, dict):
            return super().paint(painter, option, index)
        
        main_window = self.parent.main_window  # Dialog -> MainWindow
        is_dark = False
        if main_window and hasattr(main_window, 'theme_action'):
            is_dark = main_window.theme_action.isChecked()

        # # Set colors based on theme
        # if (item.get('user_data') or {}).get('type') == 'note':
        #     bg_color = QtGui.QColor('#3A4A3A') if is_dark else QtGui.QColor('#E8F5E9')
        #     text_color = QtCore.Qt.white if is_dark else QtCore.Qt.black
        # else:
        #     bg_color = QtGui.QColor('#2D2D2D') if is_dark else QtGui.QColor('#FFFFFF')
        #     text_color = QtCore.Qt.white if is_dark else QtCore.Qt.black

        # Use system palette colors
        palette = self.parent.palette()
        bg_color = palette.color(QtGui.QPalette.Base)
        text_color = palette.color(QtGui.QPalette.Text)
        
        # Override for notes
        if (item.get('user_data') or {}).get('type') == 'note':
            bg_color = QtGui.QColor('#3A4A3A') if is_dark else QtGui.QColor('#E8F5E9')
            text_color = QtGui.QColor('#FFFFFF') if is_dark else QtGui.QColor('#000000')

        painter.save()
        painter.fillRect(option.rect, bg_color)
        painter.setPen(text_color)
        
        item_type = item.get('user_data', {}).get('type') or item.get('data', {}).get('type')
        
        # Set background color for notes
        if item_type == 'note':
            if is_dark:
                painter.fillRect(option.rect, QtGui.QColor('#2a2a2a'))
            else:
                painter.fillRect(option.rect, QtGui.QColor('#C8E6C9'))

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
                               option.rect.width() - 45, option.rect.height()  )
        painter.setPen(QtCore.Qt.black)
        painter.drawText(text_rect, QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter | QtCore.Qt.TextWordWrap,
                     self._get_preview_text(item))

        painter.restore()

    # def sizeHint(self, option, index):
    #     # Get base size from superclass
    #     sh = super().sizeHint(option, index)
        
    #     # Add extra height based on font metrics
    #     font = self.parent.list_view.font()
    #     fm = QtGui.QFontMetrics(font)
    #     sh.setHeight(fm.height() * 2 )  # 2 lines + padding
    #     return sh

    def _get_preview_text(self, item):
        data = item.get('data') or item.get('user_data')
        item_type = data.get('type','ayah')
        if item_type == 'note':
            content = data.get('content','')
            first_line = content.split('\n')[0].strip()
            return f"...{first_line[:30]}"
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
        self.main_window = parent
        self.search_engine = search_engine
        self.app_settings = AppSettings() 
        self.current_course = None
        self.loading = False
        self.preview_was_visible = False
        self.unsaved_changes = False
        self.original_title = ""
        self.auto_save_timer = QtCore.QTimer()
        self.auto_save_timer.timeout.connect(self.auto_save_note)
        self.recovery_dir = "note_recovery"
        os.makedirs(self.recovery_dir, exist_ok=True)
        self.edit_mode = False
        
        # Add model change listeners
        self.model = QtGui.QStandardItemModel()
        self.model.dataChanged.connect(self.handle_model_changed)
        self.model.rowsInserted.connect(self.handle_model_changed)
        self.model.rowsRemoved.connect(self.handle_model_changed)
        
        if self.main_window and hasattr(self.main_window, 'theme_action'):
            self.main_window.theme_action.toggled.connect(self.handle_theme_change)
        
        self.init_ui()
        self.load_initial_courses() 
        self.list_view.setFocus()

    def auto_save_note(self):
        """Auto-save note content to dedicated recovery file"""
        if not hasattr(self, 'current_editing_index') or not self.current_editing_index:
            return
            
        if not hasattr(self, 'current_recovery_file'):
            # Generate unique filename based on note ID and timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            note_id = hash(self.current_editing_index)  # Simple ID based on index
            self.current_recovery_file = os.path.join(
                self.recovery_dir, 
                f"note_recovery_{note_id}_{timestamp}.txt"
            )
        
        content = self.preview_edit.toPlainText()
        try:
            with open(self.current_recovery_file, "w", encoding="utf-8") as f:
                f.write(f"# Auto-saved at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(content)
            
            # Show status message with full path
            self.status_bar.showMessage(
                f"Auto-saved to: {os.path.abspath(self.current_recovery_file)}", 
                30000
            )
        except Exception as e:
            logging.error(f"Error saving recovery file: {str(e)}")
            self.status_bar.showMessage(
                f"Error saving recovery: {str(e)}", 
                50000
            )

    # def log_edit_session(self):
    #     """Log edit session start to recovery file"""
    #     timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    #     try:
    #         with open(self.recovery_file, "w", encoding="utf-8") as f:
    #             f.write(f"# Edit session started at {timestamp}\n")
    #             f.write(self.original_note_content)
    #     except Exception as e:
    #         logging.error(f"Error creating recovery file: {str(e)}")

    def clear_recovery_file(self):
        """Clear the recovery file"""
        try:
            if os.path.exists(self.recovery_file):
                os.remove(self.recovery_file)
        except Exception as e:
            logging.error(f"Error removing recovery file: {str(e)}")

    # def save_current_note(self):
    #     """Save current note and exit edit mode"""
    #     if not self.current_editing_index.isValid():
    #         return
            
    #     item = self.model.itemFromIndex(self.current_editing_index)
    #     data = item.data(QtCore.Qt.UserRole)
    #     new_content = self.preview_edit.toPlainText()
        
    #     # Update data
    #     data['user_data']['content'] = new_content
    #     item.setData(data, QtCore.Qt.UserRole)
        
    #     # Update display
    #     preview = new_content.split('\n')[0][:30] + ('...' if len(new_content) > 30 else '')
    #     item.setText(f"Note: {preview}")
        
    #     # Exit edit mode
    #     self.end_editing()
        
    #     # Clear recovery file
    #     self.clear_recovery_file()


    def cancel_editing(self):
        """Cancel editing and revert to original content"""
        if not hasattr(self, 'current_editing_index') or not self.current_editing_index:
            return
            
        item = self.model.itemFromIndex(self.current_editing_index)
        data = item.data(QtCore.Qt.UserRole)
        
        # Revert to original content
        data['user_data']['content'] = self.original_note_content
        item.setData(data, QtCore.Qt.UserRole)
        self.preview_edit.setPlainText(self.original_note_content)
        
        # Update display text
        preview = self.original_note_content.split('\n')[0][:30] + ('...' if len(self.original_note_content) > 30 else '')
        item.setText(f"Note: {preview}")
        
        # Exit edit mode
        self.end_editing()
        
        # Show status message
        self.status_bar.showMessage("Editing canceled", 30000)
        # Clear recovery file
        #self.clear_recovery_file()

    def end_editing(self):
        """Exit edit mode"""
        self.preview_edit.setReadOnly(True)
        self.set_edit_mode(False)
        self.auto_save_timer.stop()
        if hasattr(self, 'current_editing_index'):
            self.current_editing_index = None
        self.list_view.setFocus()

    # def revert_to_version(self):
    #     """Revert to previous version"""
    #     if not self.edit_mode or len(self.note_versions) < 2:
    #         return
            
    #     # Get the previous version
    #     prev_version = self.note_versions[self.current_version - 1]
        
    #     # Update the editor and model
    #     self.preview_edit.setPlainText(prev_version)
    #     self.status_bar.showMessage(f"Reverted to previous version", 3000)
        
    #     # Update the current version pointer
    #     self.current_version -= 1
    #     if self.current_version < 0:
    #         self.current_version = 0
            
    #     # Update the model
    #     item = self.model.itemFromIndex(self.current_editing_index)
    #     data = item.data(QtCore.Qt.UserRole)
    #     data['user_data']['content'] = prev_version
    #     item.setData(data, QtCore.Qt.UserRole)
        
    #     # Update display text
    #     preview = prev_version.split('\n')[0][:30] + ('...' if len(prev_version) > 30 else '')
    #     item.setText(f"Note: {preview}")
    #     self.mark_unsaved()

    # def show_version_history(self):
    #     """Show dialog with all saved versions"""
    #     if not self.edit_mode or len(self.note_versions) < 2:
    #         return
            
    #     dialog = QtWidgets.QDialog(self)
    #     dialog.setWindowTitle("Note Version History")
    #     layout = QtWidgets.QVBoxLayout()
        
    #     list_widget = QtWidgets.QListWidget()
    #     for i, version in enumerate(reversed(self.note_versions)):
    #         preview = version.split('\n')[0][:50] + ('...' if len(version) > 50 else '')
    #         item = QtWidgets.QListWidgetItem(f"Version {len(self.note_versions)-i}: {preview}")
    #         item.setData(QtCore.Qt.UserRole, version)
    #         list_widget.addItem(item)
        
    #     button_box = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
    #     button_box.accepted.connect(dialog.accept)
    #     button_box.rejected.connect(dialog.reject)
        
    #     layout.addWidget(QtWidgets.QLabel("Select a version to restore:"))
    #     layout.addWidget(list_widget)
    #     layout.addWidget(button_box)
    #     dialog.setLayout(layout)
        
    #     if dialog.exec_() == QtWidgets.QDialog.Accepted:
    #         selected = list_widget.currentItem()
    #         if selected:
    #             version_content = selected.data(QtCore.Qt.UserRole)
    #             self.preview_edit.setPlainText(version_content)
                
    #             # Update model
    #             item = self.model.itemFromIndex(self.current_editing_index)
    #             data = item.data(QtCore.Qt.UserRole)
    #             data['user_data']['content'] = version_content
    #             item.setData(data, QtCore.Qt.UserRole)
                
    #             # Update display text
    #             preview = version_content.split('\n')[0][:30] + ('...' if len(version_content) > 30 else '')
    #             item.setText(f"Note: {preview}")
    #             self.mark_unsaved()

    def handle_model_changed(self, *args):
        """Only mark changes if not loading"""
        #print(f"Model changed signal received with args: {args}")
        if not self.loading and not self.unsaved_changes:
            self.mark_unsaved()

    def handle_theme_change(self, dark):
        # Refresh list view styling
        self.list_view.style().unpolish(self.list_view)
        self.list_view.style().polish(self.list_view)
        self.list_view.update()

    def init_ui(self):
        self.setWindowTitle("دروس القرآن")
        self.resize(800, 600)
        layout = QtWidgets.QVBoxLayout()

        # Header
        # Replace title_edit with a combo box
        self.course_combo = QtWidgets.QComboBox()
        self.course_combo.setEditable(True)  # Allow editing the title
        self.course_combo.setInsertPolicy(QtWidgets.QComboBox.NoInsert)  # Don't add new items on edit
        self.course_combo.setMinimumWidth(200)  # Make it wider
        
        # Create a custom delegate to handle double-click
        class ComboDelegate(QtWidgets.QStyledItemDelegate):
            def __init__(self, parent):
                super().__init__(parent)
                
            def editorEvent(self, event, model, option, index):
                # Open dropdown on double-click
                if event.type() == QtCore.QEvent.MouseButtonDblClick:
                    self.parent().showPopup()
                    return True
                return super().editorEvent(event, model, option, index)
        
        self.course_combo.setItemDelegate(ComboDelegate(self.course_combo))

        self.prev_btn = QtWidgets.QPushButton("←")
        self.next_btn = QtWidgets.QPushButton("→")
        self.prev_btn.clicked.connect(self.load_previous_course)
        self.next_btn.clicked.connect(self.load_next_course)
        
        nav_layout = QtWidgets.QHBoxLayout()
        nav_layout.addWidget(self.prev_btn)
        nav_layout.addWidget(self.course_combo)
        nav_layout.addWidget(self.next_btn)

        self.prev_btn.setFixedSize(25, 25)
        self.next_btn.setFixedSize(25, 25)

        layout.addLayout(nav_layout)

        # List View
        self.list_view = QtWidgets.QListView()
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
                alternate-background-color: #FFFFFF;
            }
            QListView::item {
                border-bottom: 1px solid #DDD;
                padding: 4px;
            }
            QListView::item:selected {
                background: #0078D4;
                color: white;
            }
        """)
        # Add dark mode variant
        if self.main_window and self.main_window.theme_action.isChecked():
            self.list_view.setStyleSheet("""
                QListView {
                    font-family: 'Amiri';
                    font-size: 14pt;
                    padding-right: 10px;
                    text-align: right;
                    color: #FFFFFF;
                }
                QListView::item {
                    border-bottom: 1px solid #DDD;
                    padding: 4px;
                    background: #ff0000;
                }
                QListView::item:selected {
                    background: #ff0000;
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

        self.splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        self.splitter.addWidget(self.list_view)
        self.splitter.addWidget(self.preview_edit)
        self.splitter.setSizes([int(self.width()*0.3), int(self.width()*0.7)])
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 3)

        layout.addWidget(self.splitter)

        # Control Buttons
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

        # Existing buttons
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

        # Note editing buttons
        self.edit_note_btn = QtWidgets.QPushButton("Edit Note")
        self.edit_note_btn.clicked.connect(self.start_editing)
        self.save_note_btn = QtWidgets.QPushButton("Save Note")
        self.save_note_btn.clicked.connect(self.save_note)
        self.cancel_note_btn = QtWidgets.QPushButton("Cancel")
        self.cancel_note_btn.clicked.connect(self.cancel_editing)
        
        # Add all buttons to layout
        btn_layout.addWidget(self.add_note_btn)
        btn_layout.addWidget(self.remove_btn)
        btn_layout.addWidget(self.move_up_btn)
        btn_layout.addWidget(self.move_down_btn)
        btn_layout.addWidget(self.edit_note_btn)
        btn_layout.addWidget(self.play_checkbox)
        btn_layout.addWidget(self.preview_check)
        btn_layout.addWidget(self.save_note_btn)
        btn_layout.addWidget(self.cancel_note_btn)

        # Initially hide save/cancel buttons
        self.save_note_btn.hide()
        self.cancel_note_btn.hide()

        button_container.setMaximumHeight(60) 
        button_container.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding,
            QtWidgets.QSizePolicy.Fixed
        )

        layout.addWidget(button_container)

        # Dialog Buttons
        self.dialog_btn = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Save | QtWidgets.QDialogButtonBox.Close)

        # Compact styling
        self.dialog_btn.setStyleSheet("""
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


        self.print_btn = QtWidgets.QPushButton("Print")
        self.print_btn.clicked.connect(self.print_course)

        self.open_btn = QtWidgets.QPushButton("Open")
        self.open_btn.clicked.connect(self.open_course_selection)

        self.dialog_btn.addButton(self.open_btn, QtWidgets.QDialogButtonBox.ActionRole)
        self.dialog_btn.addButton(self.print_btn, QtWidgets.QDialogButtonBox.ActionRole)

        # Button styling (unchanged)
        self.dialog_btn.accepted.connect(self.save_course)
        self.dialog_btn.rejected.connect(self.reject)

        # Create compact container
        btn_container = QtWidgets.QWidget()
        btn_container.setFixedHeight(32)  # Set fixed height
        btn_container_layout = QtWidgets.QHBoxLayout(btn_container)
        btn_container_layout.setContentsMargins(0, 0, 0, 0)  # Remove margins
        btn_container_layout.setSpacing(4)
        btn_container_layout.addWidget(self.dialog_btn)
        btn_container_layout.setAlignment(QtCore.Qt.AlignCenter)

        layout.addWidget(btn_container) 

        self.status_bar = QtWidgets.QStatusBar()
        self.status_bar.setSizeGripEnabled(False)
        self.status_bar.setMaximumHeight(20) 
        layout.addWidget(self.status_bar)

        # Connections
        self.list_view.installEventFilter(self)
        self.list_view.doubleClicked.connect(self.handle_enter_key)
        self.list_view.selectionModel().currentChanged.connect(self.handle_selection_changed)
        self.preview_edit.textChanged.connect(self.handle_text_edit)
        self.preview_check.toggled.connect(self.on_preview_toggled)
        self.preview_edit.installEventFilter(self)

        self.course_combo.currentIndexChanged.connect(self.handle_course_selection)
        self.course_combo.editTextChanged.connect(self.handle_title_changed)
        self.course_combo.installEventFilter(self)

        self.setLayout(layout)


    # def showEvent(self, event):
    #     """Check for recovery file on show"""
    #     super().showEvent(event)
    #     self.check_recovery_file()

    # def check_recovery_file(self):
    #     """Check for recovery file and prompt user"""
    #     if os.path.exists(self.recovery_file):
    #         reply = QtWidgets.QMessageBox.question(
    #             self,
    #             'Recover Note',
    #             'A recovered note edit session was found. Would you like to recover it?',
    #             QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
    #         )
            
    #         if reply == QtWidgets.QMessageBox.Yes:
    #             try:
    #                 with open(self.recovery_file, "r", encoding="utf-8") as f:
    #                     content = f.read()
    #                     # Skip header line
    #                     if content.startswith("#"):
    #                         content = "\n".join(content.split("\n")[1:])
    #                     self.recovered_content = content
                        
    #                     # Find the first note item
    #                     for row in range(self.model.rowCount()):
    #                         index = self.model.index(row, 0)
    #                         item = self.model.itemFromIndex(index)
    #                         data = item.data(QtCore.Qt.UserRole)
    #                         if data.get('type') == 'note':
    #                             self.list_view.setCurrentIndex(index)
    #                             self.start_editing()
    #                             self.preview_edit.setPlainText(content)
    #                             break
    #             except Exception as e:
    #                 logging.error(f"Error loading recovery file: {str(e)}")
            
    #         # Clear recovery file regardless of choice
    #         #self.clear_recovery_file()


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

    def open_course_selection(self):
        """Handle opening course selection dialog"""
        if self.unsaved_changes:
            reply = QtWidgets.QMessageBox.question(
                self,
                'Unsaved Changes',
                'Save changes before opening another course?',
                QtWidgets.QMessageBox.Save | 
                QtWidgets.QMessageBox.Discard |
                QtWidgets.QMessageBox.Cancel
            )
            
            if reply == QtWidgets.QMessageBox.Cancel:
                return
            elif reply == QtWidgets.QMessageBox.Save:
                self.save_course()
        
        dialog = CourseSelectionDialog(self.db, self)
        if dialog.exec_() == QtWidgets.QDialog.Accepted:
            course_id = dialog.get_selected_course()
            if course_id:
                self.load_course(course_id)

    def handle_course_selection(self, index):
        """Handle when a course is selected from the dropdown"""
        if index < 0 or self.loading:
            return
            
        course_id = self.course_combo.itemData(index)
        if course_id and course_id != getattr(self.current_course, 'id', None):
            # Check for unsaved changes before loading new course
            if not self.check_unsaved_changes():
                # User canceled, so reset to current course
                if self.current_course:
                    current_index = self.course_combo.findData(self.current_course['id'])
                    if current_index >= 0:
                        self.course_combo.setCurrentIndex(current_index)
                return
                
            self.load_course(course_id)

    def update_course_dropdown(self):
        """Populate the dropdown with all courses"""
        self.course_combo.blockSignals(True)
        self.course_combo.clear()
        
        courses = self.db.get_all_courses()
        for course in courses:
            course_id = course[0]
            title = course[1]
            self.course_combo.addItem(title, course_id)
            
        # Set current course
        if self.current_course:
            index = self.course_combo.findData(self.current_course['id'])
            if index >= 0:
                self.course_combo.setCurrentIndex(index)
                
        self.course_combo.blockSignals(False)

    def load_course(self, course_id):

        """Confirm before loading new course during editing"""
        if self.edit_mode:
            reply = QtWidgets.QMessageBox.question(
                self,
                'Unsaved Note',
                'You have unsaved changes to a note. Save before switching courses?',
                QtWidgets.QMessageBox.Save | 
                QtWidgets.QMessageBox.Discard |
                QtWidgets.QMessageBox.Cancel
            )
            
            if reply == QtWidgets.QMessageBox.Cancel:
                return
            elif reply == QtWidgets.QMessageBox.Save:
                self.end_editing(save=True)

        if not course_id:
            return
        
        self.loading = True  # Set loading flag
        self.current_course = self.db.get_course(course_id)
        if not self.current_course:
            self.loading = False
            return
        
        # print(f"Loading course ID: {course_id}")
        # print(f"Previous unsaved state: {self.unsaved_changes}")
        # print(f"Previous original title: {self.original_title}")

        try:
            self.unsaved_changes = False
            self.original_title = self.current_course['title']
            self.update_course_dropdown() 
            # print(f"Setting title to: {new_title}")
            # print(f"Model row count before clear: {self.model.rowCount()}")

            # Block signals while loading
            self.model.blockSignals(True)

            self.model.clear()
            
            # print(f"Model cleared, row count: {self.model.rowCount()}")

            for item in self.current_course['items']:
                list_item = QtGui.QStandardItem(item.get('text', ''))
                list_item.setData(item, QtCore.Qt.UserRole)
                self.model.appendRow(list_item)
                # print(f"Added item: {item.get('text', '')[:20]}...")
                
            # Force UI update
            self.list_view.viewport().update()
            QtCore.QCoreApplication.processEvents()  # Process pending events
            
            # print(f"Model row count after load: {self.model.rowCount()}")
            # print(f"Current course item count: {len(self.current_course['items'])}")
                        
            self.update_window_title()
 
        finally:
            # REMOVE signal unblocking
            # self.title_edit.blockSignals(False)  # REMOVE
            # self.model.blockSignals(False)  # REMOVE
            self.model.blockSignals(False)
            self.loading = False  # Clear loading flag
            QtCore.QTimer.singleShot(100, self.clear_initial_changes)


            # print(f"After load - unsaved_changes: {self.unsaved_changes}")
            # print(f"Title edit text: {self.title_edit.text()}")
            # print(f"Original title: {self.original_title}")
            # print(f"Title changed: {self.title_edit.text() != self.original_title}")
            # print(f"Model row count changed: {self.model.rowCount() != len(self.current_course['items'])}")
            # print("-" * 50)

    def clear_initial_changes(self):
        """Clear any false unsaved states caused by initial rendering"""
        if not self.loading and self.unsaved_changes:
            #print("Clearing false unsaved state after load")
            self.unsaved_changes = False
            self.update_window_title()

    def mark_unsaved(self):
        if not self.loading and not self.unsaved_changes:
            # Check if this is a real content change or just view update
            if self.is_real_content_change():
                self.unsaved_changes = True
                self.update_window_title()
                self.status_bar.showMessage("Content modified - save needed", 5000)
                
    def is_real_content_change(self):
        """Determine if the change is actual content or just view rendering"""
        # Check if title changed
        if self.course_combo.currentText() != self.original_title:
            return True
        
        # Check if item count changed
        if self.model.rowCount() != len(self.current_course.get('items', [])):
            return True
        
        # Check if any item content changed
        for row in range(self.model.rowCount()):
            item = self.model.item(row)
            data = item.data(QtCore.Qt.UserRole)
            original_item = self.current_course['items'][row] if row < len(self.current_course['items']) else None
            
            if not original_item:
                return True
                
            # Compare the actual content, ignoring display text
            if data.get('user_data', {}) != original_item.get('user_data', {}):
                return True
            if data.get('data', {}) != original_item.get('data', {}):
                return True
                
        return False

    # def load_course(self, course_id):
    #     """Load a course by ID with proper unsaved state handling"""
    #     if not course_id:
    #         return
        
    #     # Store previous title to compare later
    #     previous_title = self.title_edit.text()
        
    #     # Fetch course data
    #     self.current_course = self.db.get_course(course_id)
    #     if not self.current_course:
    #         return
        
    #     try:
    #         # Block signals while loading
    #         self.title_edit.blockSignals(True)
    #         self.model.blockSignals(True)
            
    #         # Set title first without triggering changes
    #         new_title = self.current_course['title']
    #         self.original_title = new_title
    #         self.title_edit.setText(new_title)
            
    #         # Clear and reload items
    #         self.model.clear()
    #         for item in self.current_course['items']:
    #             list_item = QtGui.QStandardItem(item.get('text', ''))
    #             list_item.setData(item, QtCore.Qt.UserRole)
    #             self.model.appendRow(list_item)
                
    #         # Reset state after load
    #         self.unsaved_changes = False
    #         self.update_window_title()
            
    #     finally:
    #         # Restore signal handling
    #         self.title_edit.blockSignals(False)
    #         self.model.blockSignals(False)
        
    #     self.update_navigation_buttons()
    #     self.list_view.setFocus()   

    def _add_item_to_model(self, item):
        list_item = QtGui.QStandardItem()
        list_item.setData(item, QtCore.Qt.UserRole)
        list_item.setEditable(False)
        self.model.appendRow(list_item)
        self.mark_unsaved()

    def add_note(self):
        current_index = self.list_view.currentIndex()
        current_row = current_index.row() if current_index.isValid() else -1

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
        item.setEditable(False)

        if current_row == -1:  # No selection, append to end
            self.model.appendRow(item)
            new_row = self.model.rowCount() - 1
        else:  # Insert below selection
            new_row = current_row + 1
            self.model.insertRow(new_row, item)

        index = self.model.index(new_row, 0)
        self.list_view.setCurrentIndex(index)
        self.list_view.scrollTo(index)
        self.mark_unsaved()

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
        self.mark_unsaved()

    def move_item(self, direction):
        row = self.list_view.currentIndex().row()
        if 0 <= row + direction < self.model.rowCount():
            item = self.model.takeRow(row)
            self.model.insertRow(row + direction, item)
            self.list_view.setCurrentIndex(self.model.index(row + direction, 0))
        self.mark_unsaved()

    def save_course(self):
        items = []
        for row in range(self.model.rowCount()):
            item = self.model.item(row).data(QtCore.Qt.UserRole)
            items.append(item)
        
        # Get title from combo box
        course_title = self.course_combo.currentText()
        
        if self.current_course:
            course_id = self.current_course['id']
        else:
            course_id = None
      
        new_id = self.db.save_course(course_id, course_title, items)
        self.current_course = self.db.get_course(new_id)
        self.course_modified.emit()
        self.unsaved_changes = False
        self.original_title = course_title  # Update original title
        self.update_window_title()
        self.update_course_dropdown()  # Refresh dropdown with new title

    def load_previous_course(self):
  
        if not self.current_course:
            return

        if not self.check_unsaved_changes():
            return

        prev_info = self.db.get_previous_course(self.current_course['id'])
        if prev_info:
            prev_id, _ = prev_info
            self.load_course(prev_id)
            self.update_navigation_buttons()

    def load_next_course(self):
        if not self.current_course:
            return

        if not self.check_unsaved_changes():
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
            #self.resize(800, 600) 
        else:
            # Only hide if not showing a note
            current_index = self.list_view.currentIndex()
            if current_index.isValid():
                item = self.model.itemFromIndex(current_index)
                data = item.data(QtCore.Qt.UserRole)
                if data.get('type') != 'note':
                    self.preview_edit.hide()
                    #self.resize(250, 350) 

    def handle_title_changed(self, text):
        #print(f"Title changed: '{self.original_title}' -> '{text}'")
        if not self.loading and text != self.original_title:
            self.mark_unsaved()

    def update_window_title(self):
        title = "Course Manager"
        current_title = self.course_combo.currentText()
        if current_title:
            title += f" - {current_title}"
        if self.unsaved_changes:
            title += " *"
            # Add status bar message explaining why
            if self.course_combo.currentText() != self.original_title:
                self.status_bar.showMessage("Title modified - save needed", 5000)
            elif self.model.rowCount() != len(self.current_course.get('items', [])):
                self.status_bar.showMessage("Items changed - save needed", 5000)
            else:
                self.status_bar.showMessage("Content modified - save needed", 5000)
        else:
            self.status_bar.clearMessage()
        self.setWindowTitle(title)


    # def mark_unsaved(self):
    #     if not self.unsaved_changes:
    #         self.unsaved_changes = True
    #         self.update_window_title()

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
                
                elif data.get('type') == 'note' and not self.edit_mode:
                    self.start_editing()
                    return

    def handle_selection_changed(self, current, previous):
        if hasattr(self, 'current_editing_index') and self.current_editing_index:
            # Block selection changes during editing
            self.list_view.selectionModel().select(
                self.current_editing_index, 
                QtCore.QItemSelectionModel.ClearAndSelect
            )
            return

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
            content = data.get('user_data', {}).get('content', '')
            first_line = content.split('\n')[0].strip() if content else ''
            preview = f"...{first_line[:30]}"
            #item.setText(preview)
            if not self.preview_edit.isVisible():
                self.preview_edit.show()
            self.preview_edit.setPlainText(content)
            self.preview_edit.setReadOnly(True)
            self.edit_note_btn.setEnabled(True)  # Enable edit button
            return
        else:
            self.edit_note_btn.setEnabled(False)  # Disable edit button for non-notes
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
            self.mark_unsaved() 


    def check_unsaved_changes(self):
        """Check if there are unsaved changes and prompt user"""
        if self.unsaved_changes:
            reply = QtWidgets.QMessageBox.question(
                self,
                'Unsaved Changes',
                'Save changes before switching courses?',
                QtWidgets.QMessageBox.Save | 
                QtWidgets.QMessageBox.Discard |
                QtWidgets.QMessageBox.Cancel
            )
            if reply == QtWidgets.QMessageBox.Save:
                self.save_course()
                return True
            elif reply == QtWidgets.QMessageBox.Discard:
                self.unsaved_changes = False
                self.update_window_title()
                return True
            else:
                return False
        return True

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

    def start_editing(self):
        """Enter note editing mode"""
        index = self.list_view.currentIndex()
        if not index.isValid():
            return
            
        item = self.model.itemFromIndex(index)
        data = item.data(QtCore.Qt.UserRole)
        if data.get('type') != 'note':
            return
            
        # Store original content
        self.original_note_content = data['user_data']['content']
        self.current_editing_index = index
        
        # Check for existing recovery files for this note
        note_id = hash(index)  # Simple ID based on index
        recovery_files = glob.glob(os.path.join(self.recovery_dir, f"*{note_id}*.txt"))
        
        if recovery_files:
            # Sort by modification time (newest first)
            recovery_files.sort(key=os.path.getmtime, reverse=True)
            newest_file = recovery_files[0]
            
            self.status_bar.showMessage(
                f"Found recovery file: {os.path.abspath(newest_file)}", 
                50000
            )
            
            reply = QtWidgets.QMessageBox.question(
                self,
                'Recovery File Found',
                f'A recovery file exists for this note:\n\n{os.path.abspath(newest_file)}\n\n'
                'It will be overwritten with your changes. Continue editing?',
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
            )
            
            if reply == QtWidgets.QMessageBox.No:
                return
        
        # Enable editing
        self.preview_edit.setReadOnly(False)
        self.preview_edit.setFocus()
        
        # Show status message
        self.status_bar.showMessage(
            f"Editing note - Auto-saves to: {self.recovery_dir}", 
            50000
        )
        
        # Disable all other controls
        self.set_edit_mode(True)
        
        # Start auto-save timer
        self.auto_save_timer.start(30000)  # Save every 30 seconds

    def set_edit_mode(self, editing):
        """Enable/disable UI elements during editing"""
        # Disable all controls except the current editing ones
        controls = [
            self.add_note_btn, self.remove_btn, self.move_up_btn, self.move_down_btn,
            self.play_checkbox, self.preview_check, self.course_combo, self.prev_btn, self.next_btn,
            self.print_btn, self.open_btn, self.edit_note_btn, self.dialog_btn
        ]
        
        for control in controls:
            control.setEnabled(not editing)
            
        # self.list_view.setEnabled(not editing)
        # self.splitter.setEnabled(not editing)
        
        # Show/hide editing buttons
        self.edit_note_btn.setVisible(not editing)
        self.save_note_btn.setVisible(editing)
        self.cancel_note_btn.setVisible(editing)

        self.edit_mode = editing

    def save_note(self):
        """Save current note and exit edit mode"""
        if not hasattr(self, 'current_editing_index') or not self.current_editing_index:
            return
            
        item = self.model.itemFromIndex(self.current_editing_index)
        data = item.data(QtCore.Qt.UserRole)
        new_content = self.preview_edit.toPlainText()
        
        # Update data
        data['user_data']['content'] = new_content
        item.setData(data, QtCore.Qt.UserRole)
        
        # Update display text
        preview = new_content.split('\n')[0][:30] + ('...' if len(new_content) > 30 else '')
        item.setText(f"Note: {preview}")
        
        # Exit edit mode
        self.end_editing()
        
        # Show status message
        self.status_bar.showMessage("Note saved", 30000)

    def closeEvent(self, event):
        """Handle window close event"""
        # If in edit mode, prompt to save
        if hasattr(self, 'current_editing_index') and self.current_editing_index:
            reply = QtWidgets.QMessageBox.question(
                self,
                'Unsaved Note',
                'You are currently editing a note. Save changes?',
                QtWidgets.QMessageBox.Save | 
                QtWidgets.QMessageBox.Discard |
                QtWidgets.QMessageBox.Cancel
            )
            
            if reply == QtWidgets.QMessageBox.Cancel:
                event.ignore()
                return
            elif reply == QtWidgets.QMessageBox.Save:
                self.save_note()
            else:
                self.cancel_editing()
        
        # Clear recovery file when closing
        #self.clear_recovery_file()
        event.accept()

    def showPopup(self):
        """Custom method to show dropdown"""
        self.course_combo.showPopup()

    def eventFilter(self, source, event):

        # Block all events during note editing
        if hasattr(self, 'current_editing_index') and self.current_editing_index:
            # Only allow events from the preview editor
            if source is not self.preview_edit:
                return True
                
            # Handle save with Ctrl+S
            if event.type() == QtCore.QEvent.KeyPress:
                if event.key() == QtCore.Qt.Key_S and (event.modifiers() & QtCore.Qt.ControlModifier):
                    self.save_note()
                    return True
                # Allow escape to cancel
                elif event.key() == QtCore.Qt.Key_Escape:
                    #self.cancel_editing()
                    return True
                    
            return super().eventFilter(source, event)


        # Handle Enter key in course combo
        if event.type() == QtCore.QEvent.KeyPress and source is self.course_combo:
            if event.key() in (QtCore.Qt.Key_Return, QtCore.Qt.Key_Enter):
                # Open dropdown on Enter
                self.course_combo.showPopup()
                return True

        # Existing code for Ctrl+S in preview_edit
        if event.type() == QtCore.QEvent.KeyPress and source is self.preview_edit:
            if event.key() == QtCore.Qt.Key_S and (event.modifiers() & QtCore.Qt.ControlModifier):
                self.save_course()
                if self.main_window:
                    self.main_window.showMessage("Course saved", 2000)
                return True  # Event handled
                    
        if event.type() == QtCore.QEvent.KeyPress:
            # Handle Enter key only in list view
            if event.key() in (QtCore.Qt.Key_Return, QtCore.Qt.Key_Enter):
                if source is self.list_view:  # Only handle Enter for list view
                    self.handle_enter_key()
                    return True
                else:
                    return False  # Let other widgets handle Enter normally

            # Handle F2 editing
            if event.key() == QtCore.Qt.Key_F2:
                self.start_editing()
                return True

            if event.key() == QtCore.Qt.Key_Delete:
                self.remove_item()
                return True
                    
            # Handle navigation
            if event.key() == QtCore.Qt.Key_Left and source is not self.preview_edit:
                if not self.check_unsaved_changes():
                    return True  # Block navigation if user cancels
                self.load_previous_course()
                return True
            if event.key() == QtCore.Qt.Key_Right and source is not self.preview_edit:
                if not self.check_unsaved_changes():
                    return True  # Block navigation if user cancels
                self.load_next_course()
                return True
                    
            # Handle item movement
            if event.modifiers() & QtCore.Qt.ControlModifier:
                if event.key() == QtCore.Qt.Key_Up:
                    self.move_item(-1)
                    return True
                if event.key() == QtCore.Qt.Key_Down:
                    self.move_item(1)
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
        title = self.course_combo.currentText()
        search_engine = self.parent().search_engine
        output.extend(["",])
        #output.extend(["========================================================================",])
        output.extend([f"درس: {title}",])
        output.extend(["========================================================================", ""])

        for i in range(len(items)):
            item_data = items[i]
            item = item_data.get('user_data', {})
            item_type = item.get('type', 'note')
            
            if item_type == 'note':
                content = item.get('content', '')
                lines = content.split('\n')
                if lines:
                    # Add bullet to first line
                    output.append(f"● {lines[0].strip()}")
                    # Add indented subsequent lines
                    for line in lines[1:]:
                        #if line.strip():  # Skip empty lines
                        output.append(f"  {line.strip()}")

            elif item_type == 'ayah':
                surah = item.get('surah')
                start = item.get('start')
                end = item.get('end', start)
                verses = search_engine.search_by_surah_ayah(surah, start, end)
                
                if verses:
                    chapter_name = search_engine.get_chapter_name(surah)
                    range_info = f"آية {start}" if start == end else f"الآيات {start}-{end}"
                    # Add star header
                    text = "★ "
                    # Add verses with individual ayah numbers
                    for v in verses:
                        v_text = strip_html_tags(v['text_uthmani'])
                        text += f"{v_text} •  "
                    text +=f" ({chapter_name} {range_info})"
                    output.append(text)
            elif item_type == 'search':
                query = item.get('query', '')
                results, _ = search_engine.search_verses(query)
                output.extend(["========================================================================",])
                output.extend([f"بحث عن : {query}",])
                output.extend(["========================================================================", ""])
                for v in results:
                    chapter_name = search_engine.get_chapter_name(v['surah'])
                    ayah_text = strip_html_tags(v['text_uthmani'])
                    output.append(f"{ayah_text} ({chapter_name} آية {v['ayah']})\n")
            
            # Add empty line after all item types except last
            if i != len(items) - 1:
                output.append('')

        last_dir = self.app_settings.get_last_directory()
        file_path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Save Course Text", 
            f"{last_dir}/{title}.txt",
            "Text Files (*.txt)"
        )
        output = [line.replace('(', ' ( ').replace(')', ' ) ') for line in output]
        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write('\n'.join(output))
                self.parent().showMessage(f"Course saved to {file_path}", 5000)
            except Exception as e:
                self.parent().showMessage(f"Error saving file: {str(e)}", 5000, bg="red")
                
       