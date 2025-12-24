
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


class WordItemDelegate(QtWidgets.QStyledItemDelegate):
    """Custom delegate for word items"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
    
    def paint(self, painter, option, index):
        painter.save()
        
        # Get word data
        word_data = index.data(QtCore.Qt.UserRole)
        if not word_data:
            return super().paint(painter, option, index)
        
        # Set up colors based on selection
        is_dark = self.parent.is_dark_theme if hasattr(self.parent, 'is_dark_theme') else False
        
        # Background
        if option.state & QtWidgets.QStyle.State_Selected:
            if is_dark:
                painter.fillRect(option.rect, QtGui.QColor('#2A5C82'))
            else:
                painter.fillRect(option.rect, option.palette.highlight())
        else:
            # Alternate row colors
            if index.row() % 2 == 0:
                if is_dark:
                    painter.fillRect(option.rect, QtGui.QColor('#252525'))
                else:
                    painter.fillRect(option.rect, QtGui.QColor('#F8F8F8'))
        
        # Text color
        if option.state & QtWidgets.QStyle.State_Selected:
            text_color = option.palette.highlightedText().color()
        else:
            text_color = option.palette.text().color()
        
        painter.setPen(text_color)
        
        # Draw word with proper Arabic alignment
        text_rect = QtCore.QRect(option.rect.left() + 10, option.rect.top(), 
                               option.rect.width() - 20, option.rect.height())
        
        font = painter.font()
        font.setPointSize(12)
        font.setFamily('Amiri')
        font.setBold(True)
        painter.setFont(font)
        
        # Draw Arabic word (right-aligned)
        painter.drawText(text_rect, QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter, word_data['word'])
        
        painter.restore()
    
    def sizeHint(self, option, index):
        sh = super().sizeHint(option, index)
        sh.setHeight(40)  # Slightly larger for better readability
        return sh


class WordDictionaryDialog(QtWidgets.QDialog):
    """Non-modal dialog for managing Quran words and their definitions"""
    
    word_selected = QtCore.pyqtSignal(str, str)  # word, definition
    
    def __init__(self, db, search_engine=None, parent=None):
        super().__init__(parent)
        self.db = db
        self.search_engine = search_engine
        self.main_window = parent
        self.current_page = 1
        self.page_size = 50
        self.total_words = 0
        self.current_word_id = None
        self.edit_mode = False
        self.filter_letter = ""
        self.search_term = ""
        self.unsaved_changes = False
        self.original_definition = ""  # Store original definition for cancel
        
        self.is_dark_theme = False
        if self.main_window and hasattr(self.main_window, 'theme_action'):
            self.is_dark_theme = self.main_window.theme_action.isChecked()
            self.main_window.theme_action.toggled.connect(self.handle_theme_change)
        
        self.init_ui()
        self.load_words()
        
        # Set as non-modal dialog
        self.setWindowModality(QtCore.Qt.NonModal)
        
        # Set RTL layout direction for the entire dialog
        self.setLayoutDirection(QtCore.Qt.RightToLeft)
    
    def handle_theme_change(self, dark):
        """Handle theme changes from main window"""
        self.is_dark_theme = dark
        self.apply_theme_styles()
    
    def init_ui(self):
        self.setWindowTitle("قاموس كلمات القرآن")
        self.resize(1000, 600)
        
        # Main layout
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(5)
        
        # Header with title and search
        header_layout = QtWidgets.QHBoxLayout()
        
        # Title
        title_label = QtWidgets.QLabel("قاموس كلمات القرآن")
        title_label.setStyleSheet("""
            QLabel {
                font-family: 'Amiri';
                font-size: 18pt;
                font-weight: bold;
                color: #2E7D32;
                padding: 5px;
                text-align: right;
            }
        """)
        title_label.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        title_label.setMaximumHeight(50)
        # Search bar
        search_layout = QtWidgets.QHBoxLayout()
        
        self.search_input = QtWidgets.QLineEdit()
        self.search_input.setPlaceholderText("ابحث عن كلمة أو تعريف...")
        self.search_input.setMinimumWidth(250)
        self.search_input.setMaximumHeight(50)
        self.search_input.textChanged.connect(self.on_search_changed)
        self.search_input.setAlignment(QtCore.Qt.AlignRight)
        
        search_layout.addWidget(QtWidgets.QLabel("بحث:"))
        search_layout.addWidget(self.search_input)
        search_layout.addStretch()
        
        header_layout.addLayout(search_layout)
        header_layout.addStretch()
        header_layout.addWidget(title_label)
        
        main_layout.addLayout(header_layout)
        
        # Create splitter for left/right panels
        splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        
        # Right panel - Definition (75% width) - Now on the right side in RTL
        right_widget = QtWidgets.QWidget()
        right_layout = QtWidgets.QVBoxLayout(right_widget)
        right_layout.setContentsMargins(5, 5, 5, 5)
        
        # Definition header with word and timestamps
        definition_header = QtWidgets.QHBoxLayout()
        
        self.word_label = QtWidgets.QLabel("")
        self.word_label.setStyleSheet("""
            QLabel {
                font-family: 'Amiri';
                font-size: 16pt;
                font-weight: bold;
                color: #1565C0;
                text-align: right;
            }
        """)
        self.word_label.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        
        self.timestamp_label = QtWidgets.QLabel("")
        self.timestamp_label.setStyleSheet("""
            QLabel {
                font-family: 'Segoe UI';
                font-size: 9pt;
                color: #666666;
                text-align: right;
            }
        """)
        self.timestamp_label.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        
        definition_header.addWidget(self.word_label)
        definition_header.addStretch()
        definition_header.addWidget(self.timestamp_label)

        right_layout.addLayout(definition_header)
        
        # Definition text area
        self.definition_edit = QtWidgets.QTextEdit()
        self.definition_edit.setReadOnly(True)
        self.definition_edit.setPlaceholderText("اختر كلمة لعرض تعريفها...")
        self.definition_edit.textChanged.connect(self.on_definition_changed)
        self.definition_edit.setLayoutDirection(QtCore.Qt.LeftToRight)
        self.definition_edit.setAlignment(QtCore.Qt.AlignRight)

        self.highlighter = DefinitionHighlighter(self.definition_edit.document(), self.is_dark_theme)

        right_layout.addWidget(self.definition_edit)
        
        # Definition action buttons - Right aligned
        definition_buttons = QtWidgets.QHBoxLayout()
        
        self.copy_button = QtWidgets.QPushButton("نسخ")
        self.copy_button.clicked.connect(self.copy_definition)
        self.copy_button.setEnabled(False)
        self.copy_button.setIcon(self.style().standardIcon(QtWidgets.QStyle.SP_FileDialogDetailedView))
        
        self.close_button = QtWidgets.QPushButton("إغلاق")
        self.close_button.setIcon(self.style().standardIcon(QtWidgets.QStyle.SP_DialogCloseButton))
        self.close_button.setToolTip("إغلاق النافذة")
        self.close_button.clicked.connect(self.close)
        self.close_button.setFixedSize(80, 30)
        
        self.cancel_button = QtWidgets.QPushButton("إلغاء")
        self.cancel_button.clicked.connect(self.cancel_edit)
        self.cancel_button.hide()
        self.cancel_button.setIcon(self.style().standardIcon(QtWidgets.QStyle.SP_DialogCancelButton))
        
        self.save_button = QtWidgets.QPushButton("حفظ")
        self.save_button.clicked.connect(self.save_word)
        self.save_button.hide()
        self.save_button.setIcon(self.style().standardIcon(QtWidgets.QStyle.SP_DialogSaveButton))
        
        self.edit_button = QtWidgets.QPushButton("تعديل التعريف")
        self.edit_button.clicked.connect(self.toggle_edit_mode)
        self.edit_button.setEnabled(False)
        self.edit_button.setIcon(self.style().standardIcon(QtWidgets.QStyle.SP_FileIcon))
        
        definition_buttons.addWidget(self.copy_button)
        definition_buttons.addWidget(self.close_button)
        definition_buttons.addWidget(self.cancel_button)
        definition_buttons.addWidget(self.save_button)
        definition_buttons.addWidget(self.edit_button)
        definition_buttons.addStretch()
        
        right_layout.addLayout(definition_buttons)
        
        # Left panel - Word list and controls (25% width) - Now on the left side in RTL
        left_widget = QtWidgets.QWidget()
        left_layout = QtWidgets.QVBoxLayout(left_widget)
        left_layout.setContentsMargins(5, 5, 5, 5)

        # Quick filter buttons (Arabic alphabet)
        filter_container = QtWidgets.QWidget()
        filter_layout = QtWidgets.QVBoxLayout(filter_container)
        filter_layout.setContentsMargins(0, 0, 0, 0)
        filter_layout.setSpacing(0)

        # Alphabet filter label
        filter_label = QtWidgets.QLabel("تصفية سريعة:")
        filter_label.setStyleSheet("""
            font-weight: bold;
            margin: 0px;
            padding: 2px;
            text-align: right;
        """)
        filter_label.setFixedHeight(22)
        #filter_label.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        filter_layout.addWidget(filter_label)

        # Create scroll area for alphabet buttons
        alphabet_scroll = QtWidgets.QScrollArea()
        alphabet_scroll.setLayoutDirection(QtCore.Qt.RightToLeft)
        alphabet_scroll.setMaximumHeight(120)
        alphabet_scroll.setWidgetResizable(True)
        alphabet_scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        alphabet_scroll.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)

        # Arabic alphabet (corrected order)
        arabic_letters = "أبتثجحخدذرزسشصضطظعغفقكلمنهويءآىئ"

        alphabet_widget = QtWidgets.QWidget()
        alphabet_widget.setLayoutDirection(QtCore.Qt.RightToLeft)

        alphabet_grid = QtWidgets.QGridLayout(alphabet_widget)
        alphabet_grid.setSpacing(4)
        alphabet_grid.setAlignment(QtCore.Qt.AlignTop | QtCore.Qt.AlignRight)

        row, col = 0, 0
        max_cols = 8

        self.alphabet_buttons = []

        # All button
        self.all_button = QtWidgets.QPushButton("الكل")
        self.all_button.setFixedSize(50, 35)
        self.all_button.clicked.connect(lambda: self.filter_by_letter(""))
        alphabet_grid.addWidget(self.all_button, row, col)
        self.alphabet_buttons.append(self.all_button)
        col += 1

        for letter in arabic_letters:
            btn = QtWidgets.QPushButton(letter)
            btn.setFixedSize(35, 35)
            btn.setToolTip(f"كلمات تبدأ بـ '{letter}'")
            btn.clicked.connect(lambda checked, l=letter: self.filter_by_letter(l))
            alphabet_grid.addWidget(btn, row, col)
            self.alphabet_buttons.append(btn)

            col += 1
            if col >= max_cols:
                col = 0
                row += 1


        alphabet_scroll.setWidget(alphabet_widget)
        filter_layout.addWidget(alphabet_scroll)

        left_layout.addWidget(filter_container)
        
        # Word list with search count
        list_header = QtWidgets.QHBoxLayout()
        self.list_count_label = QtWidgets.QLabel("0 كلمة")
        self.list_count_label.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        list_header.addStretch()
        list_header.addWidget(self.list_count_label)
        left_layout.addLayout(list_header)
        
        # Word list
        self.word_list = QtWidgets.QListWidget()
        self.word_list.setItemDelegate(WordItemDelegate(self))
        self.word_list.itemClicked.connect(self.on_word_selected)
        self.word_list.setAlternatingRowColors(True)
        self.word_list.setLayoutDirection(QtCore.Qt.RightToLeft)
        left_layout.addWidget(self.word_list)
        
        # Word action buttons - Right aligned
        word_buttons = QtWidgets.QHBoxLayout()
        
        self.delete_button = QtWidgets.QPushButton("حذف")
        self.delete_button.clicked.connect(self.delete_word)
        self.delete_button.setEnabled(False)
        self.delete_button.setIcon(self.style().standardIcon(QtWidgets.QStyle.SP_TrashIcon))
        
        self.add_button = QtWidgets.QPushButton("إضافة كلمة")
        self.add_button.clicked.connect(self.add_new_word)
        self.add_button.setIcon(self.style().standardIcon(QtWidgets.QStyle.SP_FileDialogNewFolder))
        
        word_buttons.addWidget(self.delete_button)
        word_buttons.addStretch()
        word_buttons.addWidget(self.add_button)
        
        left_layout.addLayout(word_buttons)
        
        # Pagination controls - Right aligned
        pagination_layout = QtWidgets.QHBoxLayout()
        
        self.next_button = QtWidgets.QPushButton("التالي ▶")
        self.next_button.clicked.connect(self.next_page)
        
        self.page_label = QtWidgets.QLabel("")
        self.page_label.setAlignment(QtCore.Qt.AlignCenter)
        
        self.prev_button = QtWidgets.QPushButton("◀ السابق")
        self.prev_button.clicked.connect(self.prev_page)
        self.prev_button.setEnabled(False)
        
        pagination_layout.addWidget(self.next_button)
        pagination_layout.addWidget(self.page_label)
        pagination_layout.addWidget(self.prev_button)
        
        left_layout.addLayout(pagination_layout)
        
        # Import/Export buttons - Right aligned
        io_layout = QtWidgets.QHBoxLayout()
        
        self.export_button = QtWidgets.QPushButton("تصدير CSV")
        self.export_button.clicked.connect(self.export_words)
        self.export_button.setIcon(self.style().standardIcon(QtWidgets.QStyle.SP_ArrowUp))
        
        self.import_button = QtWidgets.QPushButton("استيراد CSV")
        self.import_button.clicked.connect(self.import_words)
        self.import_button.setIcon(self.style().standardIcon(QtWidgets.QStyle.SP_ArrowDown))
        
        io_layout.addWidget(self.export_button)
        io_layout.addWidget(self.import_button)
        
        left_layout.addLayout(io_layout)
        
        # Add widgets to splitter 
        splitter.addWidget(left_widget)  
        splitter.addWidget(right_widget)  
        splitter.setSizes([250, 700])  # 74%/26% split
        
        main_layout.addWidget(splitter)
        
        # Status bar
        self.status_bar = QtWidgets.QStatusBar()
        self.status_bar.setMaximumHeight(20)
        self.status_bar.setLayoutDirection(QtCore.Qt.RightToLeft)
        main_layout.addWidget(self.status_bar)
        
        # Apply initial theme
        self.apply_theme_styles()
        
        # Set focus to search input
        self.search_input.setFocus()
    
    def apply_theme_styles(self):
        """Apply theme-specific styling"""
        base_style = """
            QLabel {
                text-align: right;
            }
            QLineEdit, QTextEdit {
                text-align: right;
            }
            QPushButton {
                text-align: right;
            }
            QListWidget {
                text-align: right;
            }
        """
        
        if self.is_dark_theme:
            self.setStyleSheet(base_style + """
                QDialog {
                    background-color: #2D2D2D;
                }
                QLabel {
                    color: #E0E0E0;
                }
                QLineEdit, QTextEdit {
                    background-color: #3D3D3D;
                    color: #FFFFFF;
                    border: 1px solid #555555;
                    border-radius: 3px;
                    padding: 5px;
                }
                QListWidget {
                    background-color: #252525;
                    color: #FFFFFF;
                    border: 1px solid #555555;
                    border-radius: 3px;
                    alternate-background-color: #2A2A2A;
                }
                QListWidget::item:selected {
                    background-color: #2A5C82;
                    color: white;
                }
                QPushButton {
                    background-color: #4A4A4A;
                    color: #FFFFFF;
                    border: 1px solid #5A5A5A;
                    padding: 5px 10px;
                    border-radius: 3px;
                }
                QPushButton:hover {
                    background-color: #5A5A5A;
                }
                QPushButton:pressed {
                    background-color: #3A3A3A;
                }
                QPushButton:disabled {
                    background-color: #353535;
                    color: #777777;
                }
                QSplitter::handle {
                    background-color: #555555;
                }
                QScrollArea {
                    border: none;
                    background-color: transparent;
                }
                QStatusBar {
                    color: #E0E0E0;
                }
            """)
            
            self.definition_edit.setStyleSheet("""
                QTextEdit {
                    font-family: 'Amiri';
                    font-size: 14pt;
                    background-color: #252525;
                    color: #FFFFFF;
                    border: 1px solid #555555;
                    border-radius: 5px;
                    padding: 10px;
                    text-align: right;
                }
                QTextEdit:read-only {
                    background-color: #2A2A2A;
                }
            """)
        else:
            self.setStyleSheet(base_style + """
                QDialog {
                    background-color: #F5F5F5;
                }
                QLineEdit, QTextEdit {
                    border: 1px solid #CCCCCC;
                    border-radius: 3px;
                    padding: 5px;
                }
                QListWidget {
                    border: 1px solid #CCCCCC;
                    border-radius: 3px;
                    alternate-background-color: #F8F8F8;
                }
                QListWidget::item:selected {
                    background-color: #E3F2FD;
                    color: black;
                }
                QPushButton {
                    background-color: #F0F0F0;
                    border: 1px solid #CCCCCC;
                    padding: 5px 10px;
                    border-radius: 3px;
                }
                QPushButton:hover {
                    background-color: #E0E0E0;
                }
                QPushButton:pressed {
                    background-color: #D0D0D0;
                }
                QPushButton:disabled {
                    background-color: #F5F5F5;
                    color: #AAAAAA;
                }
                QSplitter::handle {
                    background-color: #DDDDDD;
                }
            """)
            
            self.definition_edit.setStyleSheet("""
                QTextEdit {
                    font-family: 'Amiri';
                    font-size: 14pt;
                    background-color: white;
                    border: 1px solid #CCCCCC;
                    border-radius: 5px;
                    padding: 10px;
                    text-align: right;
                }
                QTextEdit:read-only {
                    background-color: #F9F9F9;
                }
            """)
    
    def set_edit_mode(self, editing):
        """Enable/disable UI elements during editing to prevent data loss"""
        self.edit_mode = editing
        
        # List of widgets to disable during editing
        widgets_to_disable = [
            # Word list and selection
            self.word_list,
            
            # Filter controls
            self.all_button,
            *self.alphabet_buttons,
            
            # Search
            self.search_input,
            
            # Word actions
            self.add_button,
            self.delete_button,
            self.copy_button,
            
            # Pagination
            self.prev_button,
            self.next_button,
            
            # Import/Export
            self.import_button,
            self.export_button,
            
            # Edit button (when in edit mode)
            self.edit_button
        ]
        
        for widget in widgets_to_disable:
            widget.setEnabled(not editing)
        
        # Enable only these in edit mode
        self.save_button.setEnabled(editing)
        self.cancel_button.setEnabled(editing)
        self.close_button.setEnabled(not editing)  # Keep close enabled for safety
        
        # Show/hide editing buttons
        if editing:
            self.edit_button.hide()
            self.save_button.show()
            self.cancel_button.show()
        else:
            self.edit_button.show()
            self.save_button.hide()
            self.cancel_button.hide()
    
    def load_words(self):
        """Load words for current page"""
        self.word_list.clear()
        
        # Get words based on current filters
        if self.filter_letter:
            words = self.db.get_words_starting_with(
                self.filter_letter, 
                self.current_page, 
                self.page_size
            )
            self.total_words = self.db.get_total_words_starting_with(self.filter_letter)
        elif self.search_term:
            words = self.db.get_all_words(
                self.current_page, 
                self.page_size, 
                self.search_term
            )
            self.total_words = self.db.get_total_word_count(self.search_term)
        else:
            words = self.db.get_all_words(self.current_page, self.page_size)
            self.total_words = self.db.get_total_word_count()
        
        # Add words to list
        for word_data in words:
            item = QtWidgets.QListWidgetItem(word_data['word'])
            item.setData(QtCore.Qt.UserRole, word_data)
            item.setTextAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
            self.word_list.addItem(item)
        
        # Update list count
        self.list_count_label.setText(f"{len(words)} كلمة (من أصل {self.total_words})")
        
        # Update pagination
        total_pages = max(1, (self.total_words + self.page_size - 1) // self.page_size)
        self.page_label.setText(f"صفحة {self.current_page} من {total_pages}")
        self.prev_button.setEnabled(self.current_page > 1 and not self.edit_mode)
        self.next_button.setEnabled(self.current_page < total_pages and not self.edit_mode)
        
        # Update status
        if self.filter_letter:
            self.status_bar.showMessage(f"عرض الكلمات التي تبدأ بـ '{self.filter_letter}' - {self.total_words} كلمة", 3000)
        elif self.search_term:
            self.status_bar.showMessage(f"نتائج البحث عن '{self.search_term}' - {self.total_words} كلمة", 3000)
        else:
            self.status_bar.showMessage(f"إجمالي الكلمات: {self.total_words}", 3000)
    
    def on_word_selected(self, item):
        """Handle word selection"""
        # Block selection changes during editing
        if self.edit_mode:
            self.status_bar.showMessage("قم بحفظ التعديلات أولاً قبل اختيار كلمة أخرى", 3000)
            return
            
        word_data = item.data(QtCore.Qt.UserRole)
        self.current_word_id = word_data['id']
        
        # Update definition area
        self.word_label.setText(f"{word_data['word']}")
        
        # Format timestamp
        try:
            created = datetime.strptime(word_data['created'], "%Y-%m-%d %H:%M:%S")
            modified = datetime.strptime(word_data['modified'], "%Y-%m-%d %H:%M:%S")
            
            if created == modified:
                time_str = f"أضيفت: {created.strftime('%Y-%m-%d %H:%M')}"
            else:
                time_str = f"أنشئت: {created.strftime('%Y-%m-%d')} | عدلت: {modified.strftime('%Y-%m-%d')}"
        except:
            time_str = ""
        
        self.timestamp_label.setText(time_str)
        self.definition_edit.setPlainText(word_data['definition'])
        
        # Store original definition for possible cancel
        self.original_definition = word_data['definition']
        
        # Enable buttons (except in edit mode)
        if not self.edit_mode:
            self.edit_button.setEnabled(True)
            self.delete_button.setEnabled(True)
            self.copy_button.setEnabled(True)
    
    def on_definition_changed(self):
        """Handle definition text changes"""
        if self.edit_mode:
            current_text = self.definition_edit.toPlainText()
            if current_text != self.original_definition:
                self.unsaved_changes = True
                # Highlight unsaved changes
                if self.is_dark_theme:
                    self.definition_edit.setStyleSheet("""
                        QTextEdit {
                            font-family: 'Amiri';
                            font-size: 14pt;
                            background-color: #3A2A00;
                            color: #FFFFFF;
                            border: 2px solid #FFA000;
                            border-radius: 5px;
                            padding: 10px;
                            text-align: right;
                        }
                    """)
                else:
                    self.definition_edit.setStyleSheet("""
                        QTextEdit {
                            font-family: 'Amiri';
                            font-size: 14pt;
                            background-color: #FFF8E1;
                            border: 2px solid #FFA000;
                            border-radius: 5px;
                            padding: 10px;
                            text-align: right;
                        }
                    """)
            else:
                self.unsaved_changes = False
                # Restore edit mode styling
                if self.is_dark_theme:
                    self.definition_edit.setStyleSheet("""
                        QTextEdit {
                            font-family: 'Amiri';
                            font-size: 14pt;
                            background-color: #3A2A00;
                            color: #FFFFFF;
                            border: 2px solid #FFA000;
                            border-radius: 5px;
                            padding: 10px;
                            text-align: right;
                        }
                    """)
                else:
                    self.definition_edit.setStyleSheet("""
                        QTextEdit {
                            font-family: 'Amiri';
                            font-size: 14pt;
                            background-color: #FFF8E1;
                            border: 2px solid #FFA000;
                            border-radius: 5px;
                            padding: 10px;
                            text-align: right;
                        }
                    """)
    
    def toggle_edit_mode(self):
        """Toggle edit mode for definition"""
        if not self.current_word_id:
            return
        
        if self.edit_mode:
            # Already in edit mode - save changes
            self.save_word()
        else:
            # Enter edit mode
            self.original_definition = self.definition_edit.toPlainText()
            self.unsaved_changes = False
            self.definition_edit.setReadOnly(False)
            self.set_edit_mode(True)
            self.definition_edit.setFocus()
            
            # Highlight edit mode
            if self.is_dark_theme:
                self.definition_edit.setStyleSheet("""
                    QTextEdit {
                        font-family: 'Amiri';
                        font-size: 14pt;
                        background-color: #3A2A00;
                        color: #FFFFFF;
                        border: 2px solid #FFA000;
                        border-radius: 5px;
                        padding: 10px;
                        text-align: right;
                    }
                """)
            else:
                self.definition_edit.setStyleSheet("""
                    QTextEdit {
                        font-family: 'Amiri';
                        font-size: 14pt;
                        background-color: #FFF8E1;
                        border: 2px solid #FFA000;
                        border-radius: 5px;
                        padding: 10px;
                        text-align: right;
                    }
                """)
            
            self.status_bar.showMessage("وضع التعديل مفعل - يمكنك تعديل التعريف الآن", 3000)
    
    def save_word(self):
        """Save word definition"""
        if not self.current_word_id:
            return
        
        new_definition = self.definition_edit.toPlainText().strip()
        if not new_definition:
            QtWidgets.QMessageBox.warning(self, "تحذير", "لا يمكن حفظ تعريف فارغ")
            return
        
        # Update in database
        self.db.update_word(self.current_word_id, new_definition)
        
        # Update current item in list
        current_item = self.word_list.currentItem()
        if current_item:
            word_data = current_item.data(QtCore.Qt.UserRole)
            word_data['definition'] = new_definition
            word_data['modified'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            current_item.setData(QtCore.Qt.UserRole, word_data)
        
        # Exit edit mode
        self.definition_edit.setReadOnly(True)
        self.set_edit_mode(False)
        self.unsaved_changes = False
        
        # Update timestamp
        try:
            modified = datetime.now().strftime("%Y-%m-%d %H:%M")
            self.timestamp_label.setText(f"أنشئت: {word_data['created'].split()[0]} | عدلت: {modified}")
        except:
            pass
        
        # Restore normal styling
        self.apply_theme_styles()
        
        self.status_bar.showMessage("تم حفظ التعريف بنجاح", 3000)
    
    def cancel_edit(self):
        """Cancel editing and revert to original"""
        if not self.current_word_id:
            return
        
        # Confirm if there are unsaved changes
        if self.unsaved_changes:
            reply = QtWidgets.QMessageBox.question(
                self,
                "تعديلات غير محفوظة",
                "لديك تعديلات غير محفوظة. هل تريد بالتأكيد التخلي عن هذه التغييرات؟",
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                QtWidgets.QMessageBox.No
            )
            
            if reply == QtWidgets.QMessageBox.No:
                return
        
        # Revert to original definition
        self.definition_edit.setPlainText(self.original_definition)
        
        # Exit edit mode
        self.definition_edit.setReadOnly(True)
        self.set_edit_mode(False)
        self.unsaved_changes = False
        
        # Restore normal styling
        self.apply_theme_styles()
        
        self.status_bar.showMessage("تم إلغاء التعديل", 3000)
    
    def add_new_word(self):
        """Add a new word to dictionary"""
        # Don't allow adding new words during editing
        if self.edit_mode:
            self.status_bar.showMessage("قم بحفظ التعديلات الحالية أولاً قبل إضافة كلمة جديدة", 3000)
            return
            
        # Get word from user
        word, ok = QtWidgets.QInputDialog.getText(
            self,
            "إضافة كلمة جديدة",
            "أدخل الكلمة الجديدة:",
            QtWidgets.QLineEdit.Normal,
            ""
        )
        
        if not ok or not word.strip():
            return
        
        word = word.strip()
        
        # Check if word already exists
        existing = self.db.get_word_by_name(word)
        if existing:
            QtWidgets.QMessageBox.information(
                self,
                "معلومات",
                f"الكلمة '{word}' موجودة بالفعل في القاموس"
            )
            return
        
        # Get definition
        definition, ok = QtWidgets.QInputDialog.getMultiLineText(
            self,
            "تعريف الكلمة",
            f"أدخل تعريف الكلمة '{word}':",
            ""
        )
        
        if not ok or not definition.strip():
            return
        
        definition = definition.strip()
        
        # Add to database
        word_id = self.db.add_word(word, definition)
        if not word_id:
            QtWidgets.QMessageBox.warning(
                self,
                "خطأ",
                "فشل إضافة الكلمة - قد تكون موجودة بالفعل"
            )
            return
        
        # Clear filters and reload
        self.search_term = ""
        self.filter_letter = ""
        self.search_input.clear()
        self.current_page = 1
        self.load_words()
        
        # Find and select the new word
        for i in range(self.word_list.count()):
            item = self.word_list.item(i)
            if item.text() == word:
                self.word_list.setCurrentItem(item)
                self.word_list.scrollToItem(item)
                self.on_word_selected(item)
                break
        
        self.status_bar.showMessage(f"تمت إضافة الكلمة '{word}' بنجاح", 3000)
    
    def delete_word(self):
        """Delete selected word"""
        # Don't allow deletion during editing
        if self.edit_mode:
            self.status_bar.showMessage("قم بحفظ التعديلات الحالية أولاً قبل حذف كلمة", 3000)
            return
            
        if not self.current_word_id:
            return
        
        current_item = self.word_list.currentItem()
        if not current_item:
            return
        
        word_name = current_item.text()
        
        # Confirm deletion
        reply = QtWidgets.QMessageBox.question(
            self,
            "تأكيد الحذف",
            f"هل أنت متأكد من حذف الكلمة '{word_name}'؟\n\nهذا الإجراء لا يمكن التراجع عنه.",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.No
        )
        
        if reply == QtWidgets.QMessageBox.No:
            return
        
        # Delete from database
        success = self.db.delete_word(self.current_word_id)
        
        if not success:
            QtWidgets.QMessageBox.warning(self, "خطأ", "فشل حذف الكلمة")
            return
        
        # Clear definition area
        self.word_label.setText("")
        self.timestamp_label.setText("")
        self.definition_edit.clear()
        self.current_word_id = None
        
        # Disable buttons
        self.edit_button.setEnabled(False)
        self.delete_button.setEnabled(False)
        self.copy_button.setEnabled(False)
        
        # Reload words
        self.load_words()
        
        self.status_bar.showMessage(f"تم حذف الكلمة '{word_name}'", 3000)
    
    def filter_by_letter(self, letter):
        """Filter words by starting letter"""
        # Don't allow filtering during editing
        if self.edit_mode:
            self.status_bar.showMessage("قم بحفظ التعديلات الحالية أولاً قبل التصفية", 3000)
            return
            
        self.filter_letter = letter
        self.search_term = ""
        self.search_input.clear()
        self.current_page = 1
        self.load_words()
    
    def on_search_changed(self, text):
        """Handle search text changes with debouncing"""
        # Don't allow searching during editing
        if self.edit_mode:
            self.status_bar.showMessage("قم بحفظ التعديلات الحالية أولاً قبل البحث", 3000)
            return
            
        self.search_term = text.strip()
        self.filter_letter = ""
        self.current_page = 1
        
        # Debounce search to avoid excessive database queries
        if hasattr(self, '_search_timer'):
            self._search_timer.stop()
        
        self._search_timer = QtCore.QTimer()
        self._search_timer.setSingleShot(True)
        self._search_timer.timeout.connect(self.load_words)
        self._search_timer.start(300)  # 300ms delay
    
    def prev_page(self):
        """Go to previous page"""
        # Don't allow pagination during editing
        if self.edit_mode:
            self.status_bar.showMessage("قم بحفظ التعديلات الحالية أولاً قبل التنقل بين الصفحات", 3000)
            return
            
        if self.current_page > 1:
            self.current_page -= 1
            self.load_words()
    
    def next_page(self):
        """Go to next page"""
        # Don't allow pagination during editing
        if self.edit_mode:
            self.status_bar.showMessage("قم بحفظ التعديلات الحالية أولاً قبل التنقل بين الصفحات", 3000)
            return
            
        total_pages = max(1, (self.total_words + self.page_size - 1) // self.page_size)
        if self.current_page < total_pages:
            self.current_page += 1
            self.load_words()
    
    def copy_definition(self):
        """Copy current definition to clipboard"""
        # Don't allow copying during editing
        if self.edit_mode:
            self.status_bar.showMessage("قم بحفظ التعديلات الحالية أولاً قبل النسخ", 3000)
            return
            
        if not self.definition_edit.toPlainText():
            return
        
        clipboard = QtWidgets.QApplication.clipboard()
        current_item = self.word_list.currentItem()
        word_name = current_item.text() if current_item else ""
        
        text_to_copy = f"{word_name}:\n{self.definition_edit.toPlainText()}"
        clipboard.setText(text_to_copy)
        
        self.status_bar.showMessage("تم نسخ التعريف إلى الحافظة", 2000)
    
    def import_words(self):
        """Import words from CSV file"""
        # Don't allow import during editing
        if self.edit_mode:
            self.status_bar.showMessage("قم بحفظ التعديلات الحالية أولاً قبل الاستيراد", 3000)
            return
            
        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "استيراد كلمات من ملف CSV",
            "",
            "CSV Files (*.csv);;All Files (*)"
        )
        
        if not file_path:
            return
        
        try:
            imported, errors = self.db.import_words_from_csv(file_path)
            
            msg = QtWidgets.QMessageBox()
            msg.setIcon(QtWidgets.QMessageBox.Information)
            msg.setWindowTitle("نتيجة الاستيراد")
            msg.setText(f"تم استيراد {imported} كلمة بنجاح")
            if errors > 0:
                msg.setInformativeText(f"عدد الأخطاء: {errors}")
            msg.exec_()
            
            # Reload words
            self.load_words()
            
        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self,
                "خطأ في الاستيراد",
                f"فشل استيراد الملف:\n{str(e)}"
            )
    
    def export_words(self):
        """Export words to CSV file"""
        # Don't allow export during editing
        if self.edit_mode:
            self.status_bar.showMessage("قم بحفظ التعديلات الحالية أولاً قبل التصدير", 3000)
            return
            
        if self.total_words == 0:
            QtWidgets.QMessageBox.information(
                self,
                "معلومات",
                "لا توجد كلمات لتصديرها"
            )
            return
        
        # Suggest filename with timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        suggested_name = f"قاموس_كلمات_القرآن_{timestamp}.csv"
        
        file_path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "تصدير الكلمات إلى ملف CSV",
            suggested_name,
            "CSV Files (*.csv);;All Files (*)"
        )
        
        if not file_path:
            return
        
        try:
            self.db.export_words_to_csv(file_path)
            
            QtWidgets.QMessageBox.information(
                self,
                "نجاح",
                f"تم تصدير {self.total_words} كلمة إلى:\n{file_path}"
            )
            
        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self,
                "خطأ في التصدير",
                f"فشل تصدير الملف:\n{str(e)}"
            )
    
    def keyPressEvent(self, event):
        """Handle keyboard shortcuts"""
        # Escape: Cancel edit or close dialog
        if event.key() == QtCore.Qt.Key_Escape:
            if self.edit_mode:
                self.cancel_edit()
            else:
                self.close()
            return
        
        # Ctrl+F: Focus search (only if not editing)
        if event.key() == QtCore.Qt.Key_F and (event.modifiers() & QtCore.Qt.ControlModifier):
            if not self.edit_mode:
                self.search_input.setFocus()
                self.search_input.selectAll()
            return
        
        # Ctrl+N: Add new word (only if not editing)
        if event.key() == QtCore.Qt.Key_N and (event.modifiers() & QtCore.Qt.ControlModifier):
            if not self.edit_mode:
                self.add_new_word()
            return
        
        # Delete: Delete word (only if not editing)
        if event.key() == QtCore.Qt.Key_Delete and self.current_word_id and not self.edit_mode:
            self.delete_word()
            return
        
        # F2: Edit word (only if not already editing)
        if event.key() == QtCore.Qt.Key_F2 and self.current_word_id and not self.edit_mode:
            self.toggle_edit_mode()
            return
        
        # Ctrl+S: Save word (only in edit mode)
        if event.key() == QtCore.Qt.Key_S and (event.modifiers() & QtCore.Qt.ControlModifier):
            if self.edit_mode:
                self.save_word()
            return
        
        # Ctrl+C: Copy definition (only if not editing)
        if event.key() == QtCore.Qt.Key_C and (event.modifiers() & QtCore.Qt.ControlModifier):
            if self.current_word_id and not self.edit_mode:
                self.copy_definition()
            return
        
        # Arrow keys for navigation (only if not editing)
        if not self.edit_mode:
            if event.key() == QtCore.Qt.Key_Up:
                current_row = self.word_list.currentRow()
                if current_row > 0:
                    self.word_list.setCurrentRow(current_row - 1)
                return
            
            if event.key() == QtCore.Qt.Key_Down:
                current_row = self.word_list.currentRow()
                if current_row < self.word_list.count() - 1:
                    self.word_list.setCurrentRow(current_row + 1)
                return
        
        super().keyPressEvent(event)
    
    def closeEvent(self, event):
        """Handle dialog closing"""
        if self.edit_mode and self.unsaved_changes:
            reply = QtWidgets.QMessageBox.question(
                self,
                "تعديل غير محفوظ",
                "لديك تعديلات غير محفوظة. هل تريد حفظها قبل المغادرة؟",
                QtWidgets.QMessageBox.Save | 
                QtWidgets.QMessageBox.Discard |
                QtWidgets.QMessageBox.Cancel,
                QtWidgets.QMessageBox.Save  # Default to save
            )
            
            if reply == QtWidgets.QMessageBox.Cancel:
                event.ignore()
                return
            elif reply == QtWidgets.QMessageBox.Save:
                self.save_word()
                # Give time for save to complete
                QtCore.QCoreApplication.processEvents()
        
        # Also check if in edit mode without unsaved changes
        elif self.edit_mode:
            reply = QtWidgets.QMessageBox.question(
                self,
                "خروج من وضع التعديل",
                "أنت في وضع التعديل. هل تريد الخروج دون حفظ؟",
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                QtWidgets.QMessageBox.No
            )
            
            if reply == QtWidgets.QMessageBox.No:
                event.ignore()
                return
        
        event.accept()