
import re
import json
import logging 
from datetime import datetime
from pathlib import Path
from PyQt5.QtWidgets import QFileDialog, QMessageBox
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QSettings
from PyQt5.QtGui import QKeySequence
from PyQt5.QtWidgets import QApplication, QMainWindow, QShortcut

from PyQt5 import QtWidgets, QtCore, QtGui
from models.quran_model import QuranListModel
from models.database import DbManager
from models.search_engine import QuranSearch, QuranWordCache
from controllers.search_worker import SearchWorker
from controllers.audio_controller import AudioController
from utils.settings import AppSettings
from utils.helpers import resource_path
from views.widgets.search_input import SearchLineEdit
from views.detail_view import DetailView
from views.delegates import QuranDelegate
from views.dialogs.compact_help import CompactHelpDialog
from views.dialogs.select_course import CourseSelectionDialog
from views.dialogs.course_manager import CourseManagerDialog
from views.dialogs.bookmarks import BookmarkDialog
from views.dialogs.notes_manager import NotesManagerDialog
from views.dialogs.notes_dialog import NoteDialog
from views.dialogs.data_transfer import DataTransferDialog
from views.dialogs.help_dialog import HelpDialog
from views.dialogs.pinned_dialog import PinnedVersesDialog
from views.dialogs.word_dictionary import WordDictionaryDialog


from PyQt5.QtWidgets import QInputDialog
# =============================================================================
# Main application window
# =============================================================================
class QuranBrowser(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        icon_path = resource_path("icon.png")
        self.setWindowIcon(QtGui.QIcon(icon_path))
        self.search_engine = QuranSearch()
        self.course_dialog = None
        self.bookmark_dialog = None
        self.notes_dialog = None
        self.pinned_dialog = None
        self.compact_help_dialog = None
        self.current_detail_result = None
        self.word_dictionary_dialog = None
        self.resizing = False
        self.current_view = None  # Will track {'type': 'surah'/'search', 'surah': x, 'method': y, 'query': z}

        self._status_msg = ""
        self.temporary_message_active = False
        self.message_timer = QtCore.QTimer()
        self.message_timer.timeout.connect(self.revert_status_message)



        self.highlight_action = None
        self.highlight_color = "#FFD700"  # Gold color for highlighting
        self.highlight_words = ["الله"]  # Default word
        self.results_count_int = 0
        self.total_occurrences = 0
        self.pending_scroll = None  
        self.scroll_retries = 0
        self.MAX_SCROLL_RETRIES = 5

        self.audio_controller = AudioController(self)

        self.db = DbManager()

        self.pinned_verses = self.db.get_active_pinned_verses()

        self.settings = AppSettings()
        self.theme_action = None
        self.init_ui()
        self.setup_connections()
        self.setup_menu()
        self.setup_shortcuts()
        self.load_settings()
        self.trigger_initial_search()

        self.model.loading_started.connect(self.handle_loading_started)
        self.model.loading_progress.connect(self.handle_loading_progress)
        self.model.loading_complete.connect(self.handle_loading_complete)
        
        self.original_style = self.result_count.styleSheet()


    @property
    def search_input(self):
        return self.search_input_v if self.is_vertical_layout else self.search_input_h
    
    @property
    def version_combo(self):
        return self.version_combo_v if self.is_vertical_layout else self.version_combo_h
    
    @property
    def search_method_combo(self):
        return self.search_method_combo_v if self.is_vertical_layout else self.search_method_combo_h
    
    @property
    def surah_combo(self):
        return self.surah_combo_v if self.is_vertical_layout else self.surah_combo_h
    
    @property
    def clear_button(self):
        return self.clear_button_v if self.is_vertical_layout else self.clear_button_h

    def __del__(self):
        try:
            self.model.loading_complete.disconnect(self.handle_pending_scroll)
        except:
            pass

    def init_ui(self):
        # Create search bar widgets for horizontal layout
        self.search_input_h = SearchLineEdit()
        self.version_combo_h = QtWidgets.QComboBox()
        self.version_combo_h.addItems(["Show Uthmani", "Show Simplified"])
        self.search_method_combo_h = QtWidgets.QComboBox()
        self.search_method_combo_h.addItems(["Text", "Surah", "Surah FirstAyah LastAyah"])
        self.surah_combo_h = QtWidgets.QComboBox()
        self.surah_combo_h.addItems(self.search_engine.get_chapters_names())
        self.clear_button_h = QtWidgets.QPushButton("Clear")
        
        # Create search bar widgets for vertical layout
        self.search_input_v = SearchLineEdit()
        self.version_combo_v = QtWidgets.QComboBox()
        self.version_combo_v.addItems(["Show Uthmani", "Show Simplified"])
        self.search_method_combo_v = QtWidgets.QComboBox()
        self.search_method_combo_v.addItems(["Text", "Surah", "Surah FirstAyah LastAyah"])
        self.surah_combo_v = QtWidgets.QComboBox()
        self.surah_combo_v.addItems(self.search_engine.get_chapters_names())
        self.clear_button_v = QtWidgets.QPushButton("Clear")

        # Set size policies for horizontal layout widgets
        for widget in [self.search_input_h, self.version_combo_h, self.search_method_combo_h, 
                      self.surah_combo_h, self.clear_button_h]:
            widget.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Fixed)
            widget.setMaximumHeight(30)  # Compact height for horizontal layout

        # Set size policies for vertical layout widgets
        for widget in [self.version_combo_v, self.search_method_combo_v, self.surah_combo_v, self.clear_button_v]:
            widget.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Fixed)
            widget.setMaximumHeight(30)  # Compact height for combo boxes in vertical layout
            
        # Give the search input more height in vertical layout
        self.search_input_v.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        self.search_input_v.setMinimumHeight(40)  # More height for search input in vertical layout

        # Create a container widget for the responsive search bar
        self.search_bar_container = QtWidgets.QWidget()
        self.search_bar_layout = QtWidgets.QVBoxLayout(self.search_bar_container)
        self.search_bar_layout.setContentsMargins(5, 2, 5, 2)  # Reduced vertical margins
        self.search_bar_layout.setSpacing(2)  # Reduced spacing
        # Set size policy for the container
        self.search_bar_container.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed) 
        #self.search_bar_container.setMinimumHeight(40)
        
        # Create stacked widget to hold both layouts
        self.stacked_widget = QtWidgets.QStackedWidget()
        self.search_bar_layout.addWidget(self.stacked_widget)
        
        # Create horizontal layout widget
        self.horizontal_widget = QtWidgets.QWidget()
        self.horizontal_layout = QtWidgets.QHBoxLayout(self.horizontal_widget)
        self.horizontal_layout.setContentsMargins(0, 0, 0, 0)  # No margins
        self.horizontal_layout.setSpacing(2)  # Reduced spacing
        self.horizontal_widget.setMinimumHeight(40)
        
        # Add widgets to horizontal layout with stretch factors
        self.horizontal_layout.addWidget(QtWidgets.QLabel("Surah:"), 0)
        self.horizontal_layout.addWidget(self.surah_combo_h, 1)
        self.horizontal_layout.addWidget(QtWidgets.QLabel("Version:"), 0)
        self.horizontal_layout.addWidget(self.version_combo_h, 1)
        self.horizontal_layout.addWidget(QtWidgets.QLabel("Method:"), 0)
        self.horizontal_layout.addWidget(self.search_method_combo_h, 1)
        self.horizontal_layout.addWidget(self.search_input_h, 3)  # More stretch for search input
        self.horizontal_layout.addWidget(self.clear_button_h, 0)
        
        # Create vertical layout widget
        self.vertical_widget = QtWidgets.QWidget()
        self.vertical_layout = QtWidgets.QVBoxLayout(self.vertical_widget)
        self.vertical_layout.setContentsMargins(0, 0, 0, 0)  # No margins
        self.vertical_layout.setSpacing(2)  # Reduced spacing
        self.vertical_widget.setMinimumHeight(80)
        
        # First row for combo boxes
        self.combo_row = QtWidgets.QHBoxLayout()
        self.combo_row.setContentsMargins(0, 0, 0, 0)  # No margins
        self.combo_row.setSpacing(5)  # Reduced spacing
        
        # Add widgets to combo row with stretch factors
        self.combo_row.addWidget(QtWidgets.QLabel("Surah:"), 0)
        self.combo_row.addWidget(self.surah_combo_v, 1)
        self.combo_row.addWidget(QtWidgets.QLabel("Version:"), 0)
        self.combo_row.addWidget(self.version_combo_v, 1)
        self.combo_row.addWidget(QtWidgets.QLabel("Method:"), 0)
        self.combo_row.addWidget(self.search_method_combo_v, 1)
        
        # Second row for search input and clear button
        self.input_row = QtWidgets.QHBoxLayout()
        self.input_row.setContentsMargins(0, 0, 0, 0)  # No margins
        self.input_row.setSpacing(5)  # Reduced spacing
        
        # Add widgets to input row with stretch factors
        self.input_row.addWidget(self.search_input_v, 1)
        self.input_row.addWidget(self.clear_button_v, 0)
        
        # Add rows to vertical layout
        self.vertical_layout.addLayout(self.combo_row)
        self.vertical_layout.addLayout(self.input_row)
        
        # Add both layouts to the stacked widget
        self.stacked_widget.addWidget(self.horizontal_widget)
        self.stacked_widget.addWidget(self.vertical_widget)
        
        # Start with horizontal layout
        self.stacked_widget.setCurrentIndex(0)
        self.stacked_widget.setMaximumHeight(40)
        self.is_vertical_layout = False
        
        # Connect signals for both sets of widgets
        self.setup_widget_connections()       
        
        # Use QVBoxLayout to stack search bar and results view
        central = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(central)
        layout.setContentsMargins(5, 2, 5, 2)  # Reduced vertical margins
        layout.setSpacing(2)  # Reduced spacing
        layout.addWidget(self.search_bar_container)  # Responsive search bar at the top

        # Create the results and detail views in a QSplitter.
        self.splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        self.results_view = QtWidgets.QListView()
        self.model = QuranListModel()
        self.model.loading_complete.connect(self.handle_pending_scroll, QtCore.Qt.UniqueConnection)
        self.results_view.setModel(self.model)
        self.delegate = None 
        self.results_view.setUniformItemSizes(False)
        self.results_view.activated.connect(self.show_detail_view)
        self.results_view.setWordWrap(True)
        self.results_view.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.results_view.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)  


        self.detail_view = DetailView()
        self.splitter.addWidget(self.results_view)
        self.splitter.addWidget(self.detail_view)

        # Set stretch factors to maximize results view space.
        self.splitter.setStretchFactor(0, 4)
        self.splitter.setStretchFactor(1, 1)

        # Initially hide the detail view.
        self.detail_view.hide()

        # Add the splitter to the main layout.
        layout.addWidget(self.splitter)

        # Status bar with result count and shortcuts.
        self.status_bar = QtWidgets.QStatusBar()
        self.setStatusBar(self.status_bar)
        
        # Create container widget
        status_container = QtWidgets.QWidget()
        status_layout = QtWidgets.QHBoxLayout(status_container)
        status_layout.setContentsMargins(0, 0, 0, 0)
        status_layout.setSpacing(10)

        # Left section (fixed width)
        self.center_label = QtWidgets.QLabel()
        self.center_label.setFixedWidth(250)
        self.center_label.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
        self.center_label.setTextFormat(QtCore.Qt.RichText)
        self.center_label.setTextInteractionFlags(QtCore.Qt.TextBrowserInteraction)
        self.center_label.setOpenExternalLinks(True)
        status_layout.addWidget(self.center_label)
        self.center_label.setText("© 2025 MOSAID, <a href='https://mosaid.xyz/quran-search'>https://mosaid.xyz</a>")

        # Center section (fixed width)
        self.result_count = QtWidgets.QLabel()
        self.result_count.setAlignment(QtCore.Qt.AlignCenter)
        self.result_count.setFixedWidth(400)
        status_layout.addWidget(self.result_count)

        # Right section (fixed width)
        self.shortcuts_label = QtWidgets.QLabel()
        self.shortcuts_label.setFixedWidth(250)
        self.shortcuts_label.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        status_layout.addWidget(self.shortcuts_label)
        self.shortcuts_label.setText("Help: Ctrl+H")

        # Add container to status bar
        self.status_bar.addPermanentWidget(status_container, 1)
        
        # Set the central widget.
        self.setCentralWidget(central)
        # self.setWindowTitle("Quran Search")
        # self.resize(1200, 500)

    def setup_widget_connections(self):
        """Connect signals for both sets of widgets to keep them in sync"""
        # Connect version combo boxes
        self.version_combo_h.currentIndexChanged.connect(
            lambda index: self.version_combo_v.setCurrentIndex(index) if self.version_combo_v.currentIndex() != index else None
        )
        self.version_combo_v.currentIndexChanged.connect(
            lambda index: self.version_combo_h.setCurrentIndex(index) if self.version_combo_h.currentIndex() != index else None
        )
        
        # Connect search method combo boxes
        self.search_method_combo_h.currentIndexChanged.connect(
            lambda index: self.search_method_combo_v.setCurrentIndex(index) if self.search_method_combo_v.currentIndex() != index else None
        )
        self.search_method_combo_v.currentIndexChanged.connect(
            lambda index: self.search_method_combo_h.setCurrentIndex(index) if self.search_method_combo_h.currentIndex() != index else None
        )
        
        # Connect surah combo boxes
        self.surah_combo_h.currentIndexChanged.connect(
            lambda index: self.surah_combo_v.setCurrentIndex(index) if self.surah_combo_v.currentIndex() != index else None
        )
        self.surah_combo_v.currentIndexChanged.connect(
            lambda index: self.surah_combo_h.setCurrentIndex(index) if self.surah_combo_h.currentIndex() != index else None
        )
        
        # Connect search inputs
        self.search_input_h.textChanged.connect(
            lambda text: self.search_input_v.setText(text) if self.search_input_v.text() != text else None
        )
        self.search_input_v.textChanged.connect(
            lambda text: self.search_input_h.setText(text) if self.search_input_h.text() != text else None
        )
        
        # Connect return pressed signals
        self.search_input_h.returnPressed.connect(self.search)
        self.search_input_v.returnPressed.connect(self.search)
        
        # Connect clear buttons
        self.clear_button_h.clicked.connect(self.clear_search)
        self.clear_button_v.clicked.connect(self.clear_search)
        
        # Connect version change signals
        self.version_combo_h.currentIndexChanged.connect(self.handle_version_change)
        self.version_combo_v.currentIndexChanged.connect(self.handle_version_change)
        
        # Connect surah selection signals
        self.surah_combo_h.currentIndexChanged.connect(self.handle_surah_selection)
        self.surah_combo_v.currentIndexChanged.connect(self.handle_surah_selection)
        
        # Connect search method signals
        self.search_method_combo_h.currentIndexChanged.connect(self.search)
        self.search_method_combo_v.currentIndexChanged.connect(self.search)

    def resizeEvent(self, event):
        # Prevent recursive resize events
        if self.resizing:
            return
            
        self.resizing = True
        
        try:
            # Call parent resize event first
            super().resizeEvent(event)
            
            # Switch layout based on window width
            width = self.width()
            threshold = 800  # Width threshold for switching layouts
            
            if width < threshold and not self.is_vertical_layout:
                # Switch to vertical layout
                self.stacked_widget.setCurrentIndex(1)
                self.is_vertical_layout = True
                self.stacked_widget.setMaximumHeight(80)
                # Allow more height for vertical layout
                self.search_bar_container.setMaximumHeight(100)
                # Force a refresh after a short delay
                QtCore.QTimer.singleShot(10, self.update_after_resize)
            elif width >= threshold and self.is_vertical_layout:
                # Switch to horizontal layout
                self.stacked_widget.setCurrentIndex(0)
                self.is_vertical_layout = False
                # Compact height for horizontal layout
                self.search_bar_container.setMaximumHeight(40)
                # Force a refresh after a short delay
                QtCore.QTimer.singleShot(10, self.update_after_resize)
        finally:
            # Always reset the flag, even if an exception occurs
            QtCore.QTimer.singleShot(50, self.reset_resizing_flag)
                
    def update_after_resize(self):
        """Update the layout after a resize operation"""
        self.search_bar_container.updateGeometry()
        self.update()
        
    def reset_resizing_flag(self):
        """Reset the resizing flag after a delay"""
        self.resizing = False

    def setup_connections(self):
        self.search_input.returnPressed.connect(self.search)
        self.version_combo.currentIndexChanged.connect(self.handle_version_change)
        self.search_method_combo.currentIndexChanged.connect(self.search)
        self.surah_combo.currentIndexChanged.connect(self.handle_surah_selection)
        self.clear_button.clicked.connect(self.clear_search)
        self.detail_view.backRequested.connect(self.show_results_view)
        self.results_view.doubleClicked.connect(self.show_detail_view)

    @property
    def status_msg(self):
        return self._status_msg

    @status_msg.setter
    def status_msg(self, value):
        self._status_msg = value
        self.updatePermanentStatus()

    def updatePermanentStatus(self):
        if not self.temporary_message_active:
            # Combine results count and status message
            base = f"{self.results_count_int} نتائج"
            if self.status_msg:
                self.result_count.setText(f"{base}، {self.status_msg}")
            elif self.total_occurrences:
                self.result_count.setText(f"{base}،  تكررت {self.total_occurrences} مرة")
            else:
                self.result_count.setText(base)
            self.result_count.setStyleSheet("")

    def setup_shortcuts(self):
        QtWidgets.QShortcut(QtGui.QKeySequence("Space"), self, activated=self.handle_space)
        QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+Space"), self, activated=self.read_current_verse)
        QtWidgets.QShortcut(QtGui.QKeySequence("Escape"), self, activated=self.toggle_version)
        QtWidgets.QShortcut(QtGui.QKeySequence("Backspace"), self, activated=self.handle_backspace)
        QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+F"), self, activated=self.input_focus)
        QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+Shift+F"), self, activated=self.handle_ctrlsf)
        QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+1"), self, activated=self.load_first_surah)
        #QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+D"), self, activated=self.toggle_theme)
        QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+Shift+L"), self, 
                            activated=self.configure_highlight_words)
        QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+P"), self, activated=self.handle_ctrlp)
        QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+O"), self, activated=self.pin_current_verse)
        #QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+R"), self, activated=self.handle_ctrlr)
        QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+R"), self, activated=self.handle_repeat_all_results)
        QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+Shift+R"), self, 
                            activated=lambda: self.handle_repeat_all_results(limited=True))
        QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+S"), self, activated=self.handle_ctrls)
        QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+W"), self, activated=self.handle_ctrlw)
        QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+Shift+W"), self, activated=self.handle_ctrlsw)
        QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+A"), self.results_view, activated=self.audio_controller.play_current_surah)
        QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+M"), self, activated=self.backto_current_surah)
        #QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+Shift+H"), self, activated=self.show_help_dialog)
        QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+H"), self, activated=self.show_compact_help)
        QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+J"), self, activated=self.handle_ctrlj)
        QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+K"), self, 
                            activated=self.audio_controller.load_surah_from_current_playback)
        QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+N"), self, activated=self.focus_note_editor)
        #QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+Shift+N"), self, activated=self.show_notes_manager)
        #QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+E"), self, activated=self.show_data_transfer)
        #QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+I"), self, activated=self.show_data_transfer)
        QtWidgets.QShortcut(QtGui.QKeySequence("Delete"), self, activated=self.delete_note)
        QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+Shift+P"), self, activated=self.audio_controller.play_all_results)
        QtWidgets.QShortcut(QtGui.QKeySequence("Left"), self, activated=self.navigate_surah_left)
        QtWidgets.QShortcut(QtGui.QKeySequence("Right"), self, activated=self.navigate_surah_right)
        #QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+Shift+T"), self, activated=self.show_course_manager)
        QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+T"), self, activated=self.add_ayah_to_course)
        QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+Y"), self, activated=self.add_search_to_course)
        #QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+Shift+B"), self, activated=self.show_bookmarks)
        QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+B"), self, activated=self.bookmark_current_ayah)
        QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+="), self, activated=self.increase_font_size)  # Ctrl++
        QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl++"), self, activated=self.increase_font_size) 
        QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+-"), self, activated=self.decrease_font_size)
        QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+MouseWheelUp"), self, activated=self.increase_font_size)
        QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+MouseWheelDown"), self, activated=self.decrease_font_size)
        QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+Shift+C"), self, activated=self.copy_all_results)
        QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+C"), self, activated=self.copy_selected_results)
        #QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+Shift+D"), self, activated=self.show_word_dictionary)


    def show_word_dictionary(self):
        """Show word dictionary dialog (non-modal)"""
        if not self.word_dictionary_dialog:
            self.word_dictionary_dialog = WordDictionaryDialog(
                self.db, 
                self.search_engine, 
                self
            )
            self.word_dictionary_dialog.word_selected.connect(self.handle_word_selected)
        
        # Show and raise the dialog
        self.word_dictionary_dialog.show()
        self.word_dictionary_dialog.raise_()
        self.word_dictionary_dialog.activateWindow()
    
    def handle_word_selected(self, word, definition):
        """Handle when a word is selected in dictionary"""
        # You can implement functionality here, like:
        # - Auto-filling search with the word
        # - Showing the word in context
        # - Copying to notes, etc.
        
        # For example, set search input to the word
        if self.search_input:
            self.search_input.setText(word)
            # Optionally trigger search
            # self.search()

    def increase_font_size(self):
        new_size = self.delegate.base_font_size + 1
        if new_size <= 48:
            self.delegate.update_font_size(new_size)
            self.results_view.reset()
            self.showMessage(f"Font size: {self.delegate.base_font_size}",2000)

    def decrease_font_size(self):
        new_size = self.delegate.base_font_size - 1
        if new_size >= 10:
            self.delegate.update_font_size(new_size)
            self.results_view.reset()
            self.showMessage(f"Font size: {self.delegate.base_font_size}",2000)


    def copy_selected_results(self):
        """Copy selected results to clipboard with verse references, grouping consecutive verses"""
        selected = self.results_view.selectionModel().selectedIndexes()
        
        if not selected:
            self.showMessage("No verses selected", 3000, bg="red")
            return
            
        version = self.get_current_version()
        text_list = []
        
        # Sort selected verses by surah and ayah
        verses = []
        for index in selected:
            result = self.model.data(index, QtCore.Qt.UserRole)
            if result:
                try:
                    surah = int(result.get('surah', 0))
                    ayah = int(result.get('ayah', 0))
                    # Remove span tags
                    raw_text = result.get(f'text_{version}', '')
                    clean_text = re.sub(r'<span[^>]*>|</span>', '', raw_text)
                    
                    verses.append({
                        'surah': surah,
                        'ayah': ayah,
                        'text': clean_text,
                        'chapter': self.search_engine.get_chapter_name(surah)
                    })
                except (ValueError, TypeError):
                    continue
        
        # Sort by surah then ayah
        verses.sort(key=lambda x: (x['surah'], x['ayah']))
        
        # Group consecutive verses from same surah
        grouped_verses = []
        current_group = []
        
        for verse in verses:
            if not current_group:
                current_group.append(verse)
            else:
                last_verse = current_group[-1]
                # Check if same surah and consecutive ayah
                if (verse['surah'] == last_verse['surah'] and 
                    verse['ayah'] == last_verse['ayah'] + 1):
                    current_group.append(verse)
                else:
                    grouped_verses.append(current_group)
                    current_group = [verse]
        
        if current_group:
            grouped_verses.append(current_group)
        
        # Format the output
        for group in grouped_verses:
            if len(group) == 1:
                # Single verse
                verse = group[0]
                text_list.append(f"﴿{verse['text']}﴾ ({verse['chapter']} {verse['ayah']})")
            else:
                # Group of consecutive verses
                texts = [f"{v['text']} ({v['ayah']})• " for v in group]
                combined_text = " ".join(texts)
                
                first_ayah = group[0]['ayah']
                last_ayah = group[-1]['ayah']
                chapter = group[0]['chapter']
                
                if first_ayah == last_ayah:
                    ref = f"{chapter} {first_ayah}"
                else:
                    ref = f"{chapter} الآيات {first_ayah}-{last_ayah}"
                
                text_list.append(f"﴿{combined_text}﴾ ({ref})")

        full_text = "\n".join(text_list)
        clipboard = QtWidgets.QApplication.clipboard()
        clipboard.setText(full_text)
        self.showMessage(f"Copied {len(selected)} selected verses", 3000)


    def copy_all_results(self):
        """Copy all search results to clipboard with verse references, grouping consecutive verses"""
        if not self.model.results:
            self.showMessage("No results to copy", 3000, bg="red")
            return
            
        version = self.get_current_version()
        text_list = []
        
        # Filter out pinned verses from the actual results for grouping
        actual_results = [result for result in self.model.results if not result.get('is_pinned', False)]
        
        if not actual_results:
            self.showMessage("No search results to copy", 3000, bg="red")
            return
        
        # Sort results by surah and ayah
        verses = []
        for result in actual_results:
            try:
                surah = int(result.get('surah', 0))
                ayah = int(result.get('ayah', 0))
                # Remove span tags
                raw_text = result.get(f'text_{version}', '')
                clean_text = re.sub(r'<span[^>]*>|</span>', '', raw_text)
                
                verses.append({
                    'surah': surah,
                    'ayah': ayah,
                    'text': clean_text,
                    'chapter': self.search_engine.get_chapter_name(surah)
                })
            except (ValueError, TypeError):
                continue
        
        # Sort by surah then ayah
        verses.sort(key=lambda x: (x['surah'], x['ayah']))
        
        # Group consecutive verses from same surah
        grouped_verses = []
        current_group = []
        
        for verse in verses:
            if not current_group:
                current_group.append(verse)
            else:
                last_verse = current_group[-1]
                # Check if same surah and consecutive ayah
                if (verse['surah'] == last_verse['surah'] and 
                    verse['ayah'] == last_verse['ayah'] + 1):
                    current_group.append(verse)
                else:
                    grouped_verses.append(current_group)
                    current_group = [verse]
        
        if current_group:
            grouped_verses.append(current_group)
        
        # Format the output
        for group in grouped_verses:
            if len(group) == 1:
                # Single verse
                verse = group[0]
                text_list.append(f"﴿{verse['text']}﴾ ({verse['chapter']} {verse['ayah']})")
            else:
                # Group of consecutive verses
                texts = [f"{v['text']} ({v['ayah']})• " for v in group]
                combined_text = " ".join(texts)
                
                first_ayah = group[0]['ayah']
                last_ayah = group[-1]['ayah']
                chapter = group[0]['chapter']
                
                if first_ayah == last_ayah:
                    ref = f"{chapter} {first_ayah}"
                else:
                    ref = f"{chapter} الآيات {first_ayah}-{last_ayah}"
                
                text_list.append(f"﴿{combined_text}﴾ ({ref})")

        full_text = "\n".join(text_list)
        clipboard = QtWidgets.QApplication.clipboard()
        clipboard.setText(full_text)
        self.showMessage("Copied all results to clipboard", 3000)


    # def copy_all_results(self):
    #     """Copy all search results to clipboard with verse references (without span tags)"""
    #     if not self.model.results:
    #         self.showMessage("No results to copy", 3000, bg="red")
    #         return
            
    #     version = self.get_current_version()
    #     text_list = []
        
    #     for result in self.model.results:
    #         # Remove span tags using regular expression
    #         raw_text = result.get(f'text_{version}', '')
    #         clean_text = re.sub(r'<span[^>]*>|</span>', '', raw_text)
            
    #         surah_num = result.get('surah', '')
    #         ayah = result.get('ayah', '')
    #         chapter = self.search_engine.get_chapter_name(surah_num)
    #         text_list.append(f"{clean_text} ({chapter} {ayah})")
        
    #     full_text = "\n".join(text_list)
    #     clipboard = QtWidgets.QApplication.clipboard()
    #     clipboard.setText(full_text)
    #     self.showMessage("Copied all results to clipboard", 3000)

    def focus_note_editor(self):
        # If not in detail view, show it first
        if not self.detail_view.isVisible():
            index = self.results_view.currentIndex()
            if index.isValid():
                self.show_detail_view(index)
            else:
                self.showMessage("No verse selected", 3000, bg="red")
                return
        
        # Enable editing and focus on the note editor
        self.detail_view.notes_widget.enable_editing()
        

    def show_notes_manager(self):
        if not self.notes_dialog:
            self.notes_dialog = NotesManagerDialog(self.db, self.search_engine, self)
            self.notes_dialog.show_ayah_requested.connect(self.load_and_show_ayah)
        self.notes_dialog.show()

    def load_and_show_ayah(self, surah, ayah):
        self.load_surah_from_current_ayah(surah, ayah)
        self.show_results_view()

    def show_compact_help(self):
        if not self.compact_help_dialog:
            self.compact_help_dialog = CompactHelpDialog(self)
        self.compact_help_dialog.show()

    def delete_note(self):
        # Only delete note if we're in the detail view
        if self.detail_view.isVisible():
            self.detail_view.notes_widget.delete_note()
        else:
            # If not in detail view, show a message
            self.showMessage("الرجاء فتح عرض التفاصيل أولاً", 5000, bg="red")

            
    def handle_loading_started(self, total_results):
        self.showMessage(f"Loading {total_results} results...", 0)  # 0 = indefinite

    def handle_loading_progress(self, loaded, total, remaining):
        self.showMessage(
            f"Loaded {loaded} of {total} results ({remaining} remaining)", 
            2500,  # Brief message
            bg="#2196F3"  # Blue background for progress
        )

    def handle_loading_complete(self, total):
        self.showMessage(f"All {total} results loaded!", 3000, bg="#4CAF50")

    def showMessage(self, message, timeout=3000, bg="#4CAF50"):
        """Temporarily override the left status label"""
        # Cancel any pending reverts
        self.message_timer.stop()
        
        if timeout == 0:
            self.temporary_message_active = True
            self.result_count.setText(message)
            self.result_count.setStyleSheet(f"background: {bg}; color: white;")
            return

        # Store current permanent text if not already in override
        if not self.temporary_message_active:
            self.original_style = self.result_count.styleSheet()
            
        self.temporary_message_active = True
        self.result_count.setText(message)
        self.result_count.setStyleSheet(f"background: {bg}; color: black;")  # Visual distinction
        
        if timeout > 0:
            self.message_timer.start(timeout)

    def revert_status_message(self):
        """Revert to permanent status message"""
        self.message_timer.stop()
        self.temporary_message_active = False
        self.status_msg = ""
        self.result_count.setStyleSheet(self.original_style)

    # def show_ayah_selector(self):
    #     if not self.ayah_selector:
    #         self.ayah_selector = AyahSelectorDialog(self.db, self)
    #         self.ayah_selector.play_requested.connect(self.audio_controller.play_ayah_range)
    #         self.ayah_selector.search_requested.connect(self.handle_course_search)
    #     self.ayah_selector.show()

    def show_course_manager(self):
        if not hasattr(self, 'course_dialog') or not self.course_dialog:
            self.course_dialog = CourseManagerDialog(self.db, self.search_engine, self)    
            self.course_dialog.play_requested.connect(self.audio_controller.play_current)
            self.course_dialog.search_requested.connect(self.handle_course_search)
        self.course_dialog.show()

    def handle_course_search(self, query):
        self.search_input.setText(query)
        self.search()

    def pin_current_verse(self):
        index = self.results_view.currentIndex()
        if not index.isValid():
            return
            
        result = self.model.data(index, QtCore.Qt.UserRole)
        if not result:
            return
            
        try:
            surah = int(result['surah'])
            ayah = int(result['ayah'])
        except (ValueError, TypeError):
            return
            

        # Get active group
        active_group = next(
            (g for g in self.db.get_pinned_groups() if g['active']), 
            None
        )
        
        if not active_group:
            self.showMessage("No active group", 2000)
            return

        # Check if already pinned
        key = (surah, ayah)
        found = False
        for i, verse in enumerate(self.pinned_verses):
            if (verse['surah'], verse['ayah']) == key:
                # Unpin
                if self.db.remove_pinned_verse(surah, ayah):
                    del self.pinned_verses[i]
                    self.showMessage("تم إزالة التثبيت", 2000)
                    found = True
                break
                
        if not found:
            # Pin
            if self.db.add_pinned_verse(surah, ayah, active_group['id']):
                # Add minimal data to pinned verses
                self.pinned_verses.append({
                    'surah': surah,
                    'ayah': ayah,
                    'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                })
                self.showMessage("تم تثبيت الآية", 2000)
        
        # Refresh current view
        self.refresh_current_view()

    def refresh_current_view(self):
        """Refresh the current view to update pinned verses"""
        if self.current_view is None:
            return
            
        if self.current_view['type'] == 'surah':
            self.handle_surah_selection(self.current_view['surah'] - 1)
        elif self.current_view['type'] == 'search':
            self.search_method_combo.setCurrentText(self.current_view['method'])
            self.search_input.setText(self.current_view['query'])
            self.search()

                
    def show_pinned_dialog(self):
        if not self.pinned_dialog:
            self.pinned_dialog = PinnedVersesDialog(self.db, self.search_engine, self)
            self.pinned_dialog.verseSelected.connect(self.load_and_show_ayah)
            # Connect the active group changed signal
            self.pinned_dialog.activeGroupChanged.connect(self.handle_active_group_changed)
        self.pinned_dialog.show()

    def handle_active_group_changed(self):
        """Refresh pinned verses when active group changes"""
        self.pinned_verses = self.db.get_active_pinned_verses()
        self.refresh_current_view()
        self.showMessage("تم تحديث المجموعة النشطة", 2000)


    def setup_menu(self):
        menu = self.menuBar().addMenu("&Menu")
        
        # Dark Mode (Ctrl+D)
        self.theme_action = QtWidgets.QAction("Dark Mode", self, checkable=True)
        self.theme_action.setShortcut(QtGui.QKeySequence("Ctrl+D"))
        self.theme_action.toggled.connect(self.update_theme_style)
        menu.addAction(self.theme_action)
        
        # Highlighting (Ctrl+Shift+L)
        self.highlight_action = QtWidgets.QAction("Word Highlighting", self, checkable=True)
        #self.highlight_action.setShortcut(QtGui.QKeySequence("Ctrl+Shift+L"))
        self.highlight_action.toggled.connect(self.toggle_highlighting)
        menu.addAction(self.highlight_action)

        # Audio Directory (Ctrl+Shift+A)
        audio_dir_action = QtWidgets.QAction("Set Audio Directory", self)
        audio_dir_action.setShortcut(QtGui.QKeySequence("Ctrl+Shift+A"))
        audio_dir_action.triggered.connect(self.audio_controller.choose_audio_directory)
        menu.addAction(audio_dir_action)

        # Bookmarks (Ctrl+Shift+B)
        bookmark_action = QtWidgets.QAction("Bookmark Manager", self)
        bookmark_action.setShortcut(QtGui.QKeySequence("Ctrl+Shift+B"))
        bookmark_action.triggered.connect(self.show_bookmarks)
        menu.addAction(bookmark_action)

        # Notes Manager (Ctrl+Shift+N)
        notes_action = QtWidgets.QAction("Notes Manager", self)
        notes_action.setShortcut(QtGui.QKeySequence("Ctrl+Shift+N"))
        notes_action.triggered.connect(self.show_notes_manager)
        menu.addAction(notes_action)

        # Course Manager (Ctrl+Shift+T)
        course_action = QtWidgets.QAction("Course Manager", self)
        course_action.setShortcut(QtGui.QKeySequence("Ctrl+Shift+T"))
        course_action.triggered.connect(self.show_course_manager)
        menu.addAction(course_action)

        pinned_action = QtWidgets.QAction("Pinned Verses", self)
        pinned_action.setShortcut(QtGui.QKeySequence("Ctrl+Shift+O"))
        pinned_action.triggered.connect(self.show_pinned_dialog)
        menu.addAction(pinned_action)

        # Add Word Dictionary menu item
        dict_action = QtWidgets.QAction("قاموس الكلمات", self)
        dict_action.setShortcut(QtGui.QKeySequence("Ctrl+Shift+D"))
        dict_action.triggered.connect(self.show_word_dictionary)
        menu.addAction(dict_action)

        # Data Transfer (Ctrl+Shift+E)
        data_transfer_action = QtWidgets.QAction("Data Transfer", self)
        data_transfer_action.setShortcut(QtGui.QKeySequence("Ctrl+Shift+E"))
        data_transfer_action.triggered.connect(self.show_data_transfer)
        menu.addAction(data_transfer_action)

        # Help (Ctrl+Shift+H)
        help_action = QtWidgets.QAction("Help", self)
        help_action.setShortcut(QtGui.QKeySequence("Ctrl+Shift+H"))
        help_action.triggered.connect(self.show_help_dialog)
        menu.addAction(help_action)

        # About (Ctrl+I)
        about_action = QtWidgets.QAction("About", self)
        about_action.setShortcut(QtGui.QKeySequence("Ctrl+I"))
        about_action.triggered.connect(self.about_dialog)
        menu.addAction(about_action)

        # Exit (Ctrl+Q)
        exit_action = QtWidgets.QAction("Exit", self)
        exit_action.setShortcut(QtGui.QKeySequence("Ctrl+Q"))
        exit_action.triggered.connect(self.close)
        menu.addAction(exit_action)
 
        # Load highlight settings
        self.load_highlight_settings()

        # Initialize delegate now that theme_action exists
        self.delegate = QuranDelegate(parent=self.results_view, 
                                    is_dark=self.theme_action.isChecked())
        self.results_view.setItemDelegate(self.delegate)


    def load_highlight_settings(self):
        enabled = self.settings.value("highlightEnabled", False, type=bool)
        words = self.settings.value("highlightWords", "الله", type=str)
        self.highlight_words = [w.strip() for w in words.split(",")]
        self.highlight_action.setChecked(enabled)

    def toggle_highlighting(self, enabled):
        if enabled and not self.highlight_words:
            self.configure_highlight_words()
        self.settings.set("highlightEnabled", enabled)
        
        self.settings.set("highlightEnabled", enabled)
        self.model.updateResults(self.model.results)  # Refresh view

    def configure_highlight_words(self):
        words, ok = QtWidgets.QInputDialog.getText(
            self,
            "Highlight Words",
            "Enter comma-separated words to highlight:",
            text=",".join(self.highlight_words)
        )
        if ok and words:
            self.highlight_words = [w.strip() for w in words.split(",") if w.strip()]
            self.settings.set("highlightWords", ",".join(self.highlight_words))
            self.search()  # Refresh results with new words

    def export_notes(self):
        """Handles exporting notes to a CSV file with suggested filename."""
        # Generate default filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        default_name = f"quran_notes_{timestamp}.csv"

        # Get default documents directory
        docs_dir = QtCore.QStandardPaths.writableLocation(QtCore.QStandardPaths.DocumentsLocation)

        file_path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Export Notes",
            os.path.join(docs_dir, default_name),  # Suggested path/name
            "CSV Files (*.csv)",
            options=QtWidgets.QFileDialog.DontConfirmOverwrite
        )

        if file_path:
            # Ensure .csv extension
            if not file_path.lower().endswith('.csv'):
                file_path += '.csv'

            try:
                self.db.export_to_csv(file_path)
                self.showMessage(f"Notes exported to {file_path}", 5000)
            except Exception as e:
                self.showMessage(f"Export failed: {str(e)}", 5000, bg="red")

    def import_notes(self):
        """Handles importing notes from a CSV file."""
        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Import Notes", "", "CSV Files (*.csv)")
        if file_path:
            try:
                imported, duplicates, errors = self.db.import_from_csv(file_path)
                msg = f"Imported {imported} notes. Skipped {duplicates} duplicates. {errors} errors."
                self.showMessage(msg, 7000)

                # Refresh notes display if detail view is visible
                if self.detail_view.isVisible():
                    self.detail_view.notes_widget.load_notes()
            except ValueError as e:
                self.showMessage(str(e), 7000, bg="red")
            except Exception as e:
                self.showMessage(f"Import failed: {str(e)}", 7000, bg="red")
        if self.detail_view.isVisible():
            self.detail_view.notes_widget.load_notes()

    def show_data_transfer(self):
        dialog = DataTransferDialog(self)
        dialog.coursesChanged.connect(self.refresh_courses)
        dialog.notesChanged.connect(self.refresh_notes)
        dialog.bookmarksChanged.connect(self.refresh_bookmarks)
        dialog.pinnedChanged.connect(self.refresh_pinned)
        dialog.exec_()
    
    def refresh_courses(self):
        if hasattr(self, 'course_dialog') and self.course_dialog:
            self.course_dialog.refresh_course()
            
    def refresh_notes(self):
        # Refresh detail view notes
        if self.detail_view.isVisible():
            self.detail_view.notes_widget.load_notes()
        # Refresh notes manager if open
        if hasattr(self, 'notes_dialog') and self.notes_dialog:
            self.notes_dialog.load_notes()
            
    def refresh_bookmarks(self):
        if hasattr(self, 'bookmark_dialog') and self.bookmark_dialog:
            self.bookmark_dialog.load_bookmarks()
            
    def refresh_pinned(self):
        # Refresh main window pinned verses
        self.pinned_verses = self.db.get_active_pinned_verses()
        # Refresh current view to show new pins
        self.refresh_current_view()
        # Refresh pinned dialog if open
        if hasattr(self, 'pinned_dialog') and self.pinned_dialog:
            self.pinned_dialog.load_groups()

    def load_settings(self):
        geometry = self.settings.value("geometry")
        if geometry:
            self.restoreGeometry(geometry)
        window_state = self.settings.value("windowState")
        if window_state:
            self.restoreState(window_state)
        dark_mode = self.settings.value("darkMode", False, type=bool)
        self.theme_action.setChecked(dark_mode)
        version_index = self.settings.value("versionIndex", 0, type=int)
        self.version_combo.setCurrentIndex(version_index)
        surah_index = self.settings.value("surahIndex", 0, type=int)
        self.surah_combo.setCurrentIndex(surah_index)
        self.pinned_verses = self.db.get_active_pinned_verses()


    def closeEvent(self, event):
        self.settings.set("geometry", self.saveGeometry())
        self.settings.set("windowState", self.saveState())
        self.settings.set("darkMode", self.theme_action.isChecked())
        self.settings.set("versionIndex", self.version_combo.currentIndex())
        self.settings.set("surahIndex", self.surah_combo.currentIndex())
        event.accept()

    def trigger_initial_search(self):
        QtCore.QTimer.singleShot(100, lambda: self.handle_surah_selection(self.surah_combo.currentIndex()))

    def handle_version_change(self):
        # This will be called by both version combo boxes
        version = self.get_current_version()
        self.delegate.update_version(version)
        self.results_view.viewport().update()
        if self.detail_view.isVisible() and self.current_detail_result:
            is_dark_theme = self.theme_action.isChecked()
            self.detail_view.display_ayah(self.current_detail_result, self.search_engine, version, is_dark_theme)

    def get_current_version(self):
        # Use the appropriate combo based on current layout
        if self.is_vertical_layout:
            return "uthmani" if "Uthmani" in self.version_combo_v.currentText() else "simplified"
        else:
            return "uthmani" if "Uthmani" in self.version_combo_h.currentText() else "simplified"

    def load_first_surah(self):
        """Directly load the first surah (Al-Fatiha)"""
        self.surah_combo.setCurrentIndex(0)  # First item in the combo box
        self.handle_surah_selection(0)  # Load the first surah

    def handle_surah_selection(self, index):
        # This will be called by both surah combo boxes
        if index < 0:
            # Use the appropriate combo based on current layout
            if self.is_vertical_layout:
                index = self.surah_combo_v.currentIndex()
            else:
                index = self.surah_combo_h.currentIndex()
        
        surah = index + 1
        self.current_view = {'type': 'surah', 'surah': surah}
        try:
            is_dark_theme = self.theme_action.isChecked()
            results = self.search_engine.search_by_surah(surah, is_dark_theme, self.highlight_words)
            for result in results:
                if self.db.has_note(result['surah'], result['ayah']):
                    bullet = "<span style='font-size:32px;'>•</span> "
                    result['text_simplified'] = bullet + result['text_simplified']
                    result['text_uthmani'] = bullet + result['text_uthmani']
            self.update_results(results, f"Surah {surah} (Automatic Selection)")
            # Scroll to the top after loading new surah
            self.results_view.scrollToTop()
        except Exception as e:
            logging.exception("Error during surah selection")
            self.showMessage("Error loading surah", 3000, bg="red")
        self.show_results_view()

    def load_surah_from_current_ayah(self, surah=None, selected_ayah=None):
        """
        Load the full surah for a given surah and ayah.
        If surah and selected_ayah are not provided, use the currently selected verse.
        This does not affect playback. (Use Ctrl+A to play the surah.)
        """
        # If no parameters provided, use the current selection.
        if surah is None or selected_ayah is None:
            index = self.results_view.currentIndex()
            if not index.isValid():
                self.showMessage("No verse selected", 2000, bg="red")
                return

            result = self.model.data(index, QtCore.Qt.UserRole)
            try:
                surah = int(result.get('surah'))
                selected_ayah = int(result.get('ayah'))
            except Exception as e:
                self.showMessage("Invalid surah/ayah information", 3000, bg="red")
                return

        # Load the full surah using your search engine.
        try:
            is_dark_theme = self.theme_action.isChecked()
            results = self.search_engine.search_by_surah(surah, is_dark_theme, self.highlight_words)
            for result in results:
                if self.db.has_note(result['surah'], result['ayah']):
                    bullet = "<span style='font-size:32px;'>•</span> "
                    result['text_simplified'] = bullet + result['text_simplified']
                    result['text_uthmani'] = bullet + result['text_uthmani']
            
            # Clear current view to ensure proper scroll behavior
            self.current_view = {'type': 'surah', 'surah': surah}
            
            self.update_results(results, f"Surah {surah} (Automatic Selection)")
            self.pending_scroll = (surah, selected_ayah)
            self.scroll_retries = 0
            try:
                self.model.loading_complete.disconnect(self.handle_pending_scroll)
            except TypeError:
                pass  # No connection existed
            
            # Create fresh connection
            self.model.loading_complete.connect(
                self.handle_pending_scroll, 
                QtCore.Qt.UniqueConnection
            )
        except Exception as e:
            logging.exception("Error loading surah")
            self.showMessage("Error loading surah", 3000, bg="red")
            return

        # Show the results view.
        self.show_results_view()


    def navigate_surah_left(self):
        current_index = self.surah_combo.currentIndex()
        if current_index > 0:
            self.surah_combo.setCurrentIndex(current_index - 1)
            self.handle_surah_selection(self.surah_combo.currentIndex())

    def navigate_surah_right(self):
        current_index = self.surah_combo.currentIndex()
        if current_index < self.surah_combo.count() - 1:
            self.surah_combo.setCurrentIndex(current_index + 1)
            self.handle_surah_selection(self.surah_combo.currentIndex())

    def backto_current_surah(self):
        current_index = self.surah_combo.currentIndex()
        self.handle_surah_selection(current_index)

    # def focus_notes(self):
    #     if self.detail_view.isVisible():
    #         self.detail_view.notes_widget.editor.setFocus()

    def search(self):
        # Use the appropriate input based on current layout
        if self.is_vertical_layout:
            query = self.search_input_v.text().strip()
        else:
            query = self.search_input_h.text().strip()
            
        method = self.get_current_search_method()
        if not query and method == "Text":
            self.showMessage("Please enter a search query", 3000, bg="red")
            return
        
        # Update history for both inputs
        self.search_input_h.update_history(query)
        self.search_input_v.update_history(query)
        
        self.showMessage("Searching...", 2000)

        if (method == "Surah" and query.isdigit()) or method == "Surah FirstAyah LastAyah":
            try:
                if method == "Surah":
                    surah_num = int(query)
                else:
                    parts = [int(p) for p in query.split()]
                    surah_num = parts[0] if parts else None
                if surah_num is not None:
                    self.current_surah = surah_num
                    self.surah_combo.setCurrentIndex(surah_num - 1)  # Adjust for 0-based index
            except ValueError:
                # Conversion failed; do nothing.
                pass

        # Start the search in a background thread.
        is_dark = self.theme_action.isChecked()
        self.search_worker = SearchWorker(
            search_engine=self.search_engine,
            method=method,
            query=query,
            is_dark_theme=is_dark,  
            parent=self
        )
        self.search_worker.results_ready.connect(self.handle_search_results)
        self.search_worker.error_occurred.connect(lambda error: self.showMessage(f"Search error: {error}", 3000, bg="red"))
        self.search_worker.start()

    def get_current_search_method(self):
        # Use the appropriate combo based on current layout
        if self.is_vertical_layout:
            return self.search_method_combo_v.currentText()
        else:
            return self.search_method_combo_h.currentText()

    def handle_search_results(self,method, results,total_occurrences):
        self.current_view = {'type': 'search', 'method': method, 'query': self.search_input.text()}
        self.update_results(results)
        self.total_occurrences = total_occurrences
        self.total_occurrences = total_occurrences
        if method == "Text":
            self.status_msg = f" مرات {total_occurrences} تكرار"
        else:
            self.status_msg = ""  # Clear occurrences for non-text searches
        
        if results:
            # Select and scroll to first result
            first_index = self.model.index(0)
            self.results_view.setCurrentIndex(first_index)
            self.results_view.scrollTo(first_index, 
                QtWidgets.QAbstractItemView.PositionAtTop)
            self.results_view.setFocus()
        # Connect to the properly defined signal
        self.model.loading_complete.connect(self.finalize_results)

    def finalize_results(self):
        self.results_count_int = len(self.model.results) - len(self.pinned_verses)
        self.model.loading_complete.disconnect()  # Clean up connection

    def update_results(self, results, query=None):
        pinned_verses_ordered = self.db.get_active_pinned_verses_ordered()
        pinned_full = []
        for pin in pinned_verses_ordered:
            try:
                verse_uthmani = self.search_engine.get_verse(pin['surah'], pin['ayah'], 'uthmani')
                verse_simplified = self.search_engine.get_verse(pin['surah'], pin['ayah'], 'simplified')
                pinned_full.append({
                    'surah': pin['surah'],
                    'ayah': pin['ayah'],
                    'text_uthmani': verse_uthmani,
                    'text_simplified': verse_simplified,
                    'chapter': self.search_engine.get_chapter_name(pin['surah']),
                    'is_pinned': True  # Add pin flag
                })
            except Exception as e:
                print(f"Error loading pinned verse: {e}")

        # Combine pinned verses with current results
        combined_results = list(pinned_full) + list(results)
            
        # Update model with combined results
        self.model.updateResults(combined_results)
        self.results_count_int = len(combined_results) - len(self.pinned_verses)
        
        # Set status message
        if query and "Surah" in query:
            self.status_msg = ""
        self.updatePermanentStatus()
        
        if results:
            self.results_view.setFocus()
        
        # Force immediate scroll check
        QtCore.QTimer.singleShot(500, self.handle_pending_scroll)        


    def show_detail_view(self, index):
        if isinstance(index, QtCore.QModelIndex):
            result = self.model.data(index, QtCore.Qt.UserRole)
        else:
            result = None
        if result:
            self.current_detail_result = result
            version = self.get_current_version()
            is_dark_theme = self.theme_action.isChecked()
            self.update_theme_style(is_dark_theme)
            self.detail_view.display_ayah(result, self.search_engine, version,is_dark_theme)
            self.detail_view.show()
            self.results_view.hide()

    def input_focus(self):
        self.search_input.setFocus()
        self.search_input.selectAll()

    def handle_backspace(self):
        # Switch to results view if in detail view
        if self.detail_view.isVisible() and not self.detail_view.notes_widget.edit_checkbox.isChecked():
            self.show_results_view()
        
        # Get current selection
        index = self.results_view.currentIndex()
        if not index.isValid():
            return

        result = self.model.data(index, QtCore.Qt.UserRole)
        if not result:
            return

        try:
            surah = int(result.get('surah'))
            ayah = int(result.get('ayah'))
        except (ValueError, TypeError):
            return

        # Direct scroll without loading logic
        QtCore.QTimer.singleShot(50, lambda: self._scroll_to_ayah_immediate(surah, ayah))

    def _scroll_to_ayah_immediate(self, surah, ayah):
        # Search through all loaded items
        for row in range(self.model.rowCount()):
            index = self.model.index(row, 0)
            result = self.model.data(index, QtCore.Qt.UserRole)
            if result and result['surah'] == surah and result['ayah'] == ayah:
                self.results_view.setCurrentIndex(index)
                self.results_view.scrollTo(index, 
                    QtWidgets.QAbstractItemView.PositionAtCenter)
                break


    def show_results_view(self):
        self.detail_view.hide()
        self.results_view.show()
        self.results_view.setFocus()

    def read_current_verse(self):
        """Read the currently selected verse, stopping any ongoing playback first"""
        # Stop any current playback
        self.audio_controller.stop_playback()
        
        # Get the current selection
        index = self.results_view.currentIndex()
        if not index.isValid():
            self.showMessage("No verse selected", 2000, bg="red")
            return
            
        result = self.model.data(index, QtCore.Qt.UserRole)
        if not result:
            self.showMessage("No verse data available", 2000, bg="red")
            return
            
        try:
            surah = int(result.get('surah'))
            ayah = int(result.get('ayah'))
        except (ValueError, TypeError):
            self.showMessage("Invalid verse data", 2000, bg="red")
            return
        
        # Play the selected verse
        self.audio_controller.play_current(surah, ayah, count=1)
        self.showMessage(f"Playing Surah {surah}, Ayah {ayah}", 2000)
        
    def handle_space(self):
        status = self.audio_controller.handle_space()
        
        if status == "paused":
            self.showMessage("Playback paused", 2000)
            self.status_msg = "Paused"
        elif status == "resumed":
            self.showMessage("Playback resumed", 2000)
            self.status_msg = "Resumed"
        elif status == "new_playback":
            self.playing_context = 0
            self.playing_range = 0
            self.status_msg = ""
            self.audio_controller.play_current()

            
        # Force UI update
        #self.updatePermanentStatus()

    def handle_ctrlp(self):
        self.playing_context = 1
        self.status_msg = "إستماع الى الأية وخمسة بعدها"
        self.audio_controller.play_current(count=6)

    def handle_ctrlr(self):
        method = self.search_method_combo.currentText()
        if not method == "Surah FirstAyah LastAyah":
            self.showMessage("Please select a range to repeat using 'Surah FirstAyah LastAyah' search method", 10000, bg="red")
            return
        self.playing_range = 1
        self.playing_range_max = self.results_count_int
        self.audio_controller.play_current(count=self.playing_range_max)

    def handle_repeat_all_results(self, limited=False):
        """Handle repeating with optional limit"""
        if limited:
            # Get repeat count from user
            count, ok = QtWidgets.QInputDialog.getInt(
                self, 
                "Repeat Settings",
                "Number of repeats:",
                value=2, min=1, max=100, step=1
            )
            
            if not ok or count < 1:
                self.showMessage("Invalid repeat count", 2000, bg="red")
                return
                
            self.audio_controller.max_repeats = count
            self.audio_controller.repeat_count = 0
            self.showMessage(f"Repeating {self.audio_controller.max_repeats} times", 3000)
        else:
            # Original infinite repeat behavior
            self.audio_controller.max_repeats = 0  
            self.audio_controller.repeat_count = 0
            self.showMessage("Repeating all results continuously", 3000)
        
        # Common playback start logic
        self.audio_controller.repeat_all = True
        self.audio_controller.play_all_results()

    def handle_ctrlsf(self):
        """Handle Ctrl+shift+f: Set search method to text and focus search input"""
        try:
            # Set search method to "text"
            index = self.search_method_combo.findText("text", QtCore.Qt.MatchFixedString)
            if index >= 0:
                self.search_method_combo.setCurrentIndex(index)

            # Focus and select all text in search input
            self.search_input.setFocus()
            self.search_input.selectAll()

            # Optional: Trigger search if needed
            # self.search()

        except Exception as e:
            logging.error(f"Error in handle_ctrlsf: {str(e)}")
            self.showMessage("Error changing search mode", 3000, bg="red")

    def handle_ctrlw(self):
        """Handle Ctrl+Z: Set search method to Surah and focus search input"""
        try:
            # Set search method to "Surah"
            index = self.search_method_combo.findText("Surah", QtCore.Qt.MatchFixedString)
            if index >= 0:
                self.search_method_combo.setCurrentIndex(index)

            # Focus and select all text in search input
            self.search_input.setFocus()
            self.search_input.selectAll()

            # Optional: Trigger search if needed
            # self.search()

        except Exception as e:
            logging.error(f"Error in handle_ctrlw: {str(e)}")
            self.showMessage("Error changing search mode", 3000, bg="red")
    
    def handle_ctrlsw(self):
        """Handle Ctrl+shift+w: Set search method to Surah and focus search input"""
        try:
            # Set search method to "Surah"
            index = self.search_method_combo.findText("Surah FirstAyah LastAyah", QtCore.Qt.MatchFixedString)
            if index >= 0:
                self.search_method_combo.setCurrentIndex(index)

            # Focus and select all text in search input
            self.search_input.setFocus()
            self.search_input.selectAll()

            # Optional: Trigger search if needed
            # self.search()

        except Exception as e:
            logging.error(f"Error in handle_ctrlsw: {str(e)}")
            self.showMessage("Error changing search mode", 3000, bg="red")

    def handle_ctrls(self):
        if self.detail_view.isVisible():
            notes_widget = self.detail_view.notes_widget
            # Check if notes editor has focus
            if notes_widget.editor.hasFocus():
                notes_widget.save_note()
                return
        # Fallback to audio stop
        self.status_msg = ""
        self.audio_controller.stop_playback()



    def handle_pending_scroll(self):
        if not self.pending_scroll:
            return
            
        surah, ayah = self.pending_scroll
        found = self._scroll_to_ayah(surah, ayah)
        
        if not found and self.scroll_retries < self.MAX_SCROLL_RETRIES:
            self.scroll_retries += 1
            # Load more results and try again
            self.model.load_remaining_results()
            QtCore.QTimer.singleShot(100, self.handle_pending_scroll)
        else:
            self.pending_scroll = None
            self.scroll_retries = 0
            try:
                self.model.loading_complete.disconnect(self.handle_pending_scroll)
            except TypeError:
                pass 

    def _scroll_to_ayah(self, surah, ayah):
        """Enhanced scroll function with progressive loading"""
        self.results_view.selectionModel().clearSelection()
        
        # First try non-pinned items (actual results) when in surah view
        for row in range(self.model.rowCount()):
            index = self.model.index(row, 0)
            result = self.model.data(index, QtCore.Qt.UserRole)
            
            # Skip pinned verses when in surah view
            if self.current_view and self.current_view['type'] == 'surah' and result.get('is_pinned', False):
                continue
                
            if (result['surah'] == surah and 
                result['ayah'] == ayah):
                self.results_view.setCurrentIndex(index)
                self.results_view.scrollTo(index, 
                    QtWidgets.QAbstractItemView.PositionAtCenter)
                return True
                
        # If not found and not in surah view, check pinned verses
        if not (self.current_view and self.current_view['type'] == 'surah'):
            for row in range(self.model.rowCount()):
                index = self.model.index(row, 0)
                result = self.model.data(index, QtCore.Qt.UserRole)
                if (result['surah'] == surah and 
                    result['ayah'] == ayah):
                    self.results_view.setCurrentIndex(index)
                    self.results_view.scrollTo(index, 
                        QtWidgets.QAbstractItemView.PositionAtCenter)
                    return True
                    
        # If still not found, check if more results need loading
        if self.model._displayed_results < len(self.model.results):
            self.model.load_remaining_results()
            
        return False

    def _add_search_to_course(self, course_id, query):
        """Add a search query to a course"""
        courses = self.db.get_all_courses()
        course = next((c for c in courses if c[0] == course_id), None)
        if not course:
            return

        _, title, items = course
        updated_items = items.copy()
        
        # Create search item
        search_item = {
            "text": f"Search: {query}",
            "user_data": {
                "type": "search",
                "query": query
            }
        }
        
        # Check if this search already exists in the course
        for item in updated_items:
            if (item.get('user_data', {}).get('type') == 'search' and 
                item.get('user_data', {}).get('query') == query):
                self.showMessage("This search already exists in the course", 3000)
                return
                
        updated_items.append(search_item)
        
        # Save the course
        self.db.save_course(course_id, title, updated_items)
        self.showMessage(f"Added search to course: {title}", 3000)
        
        # Refresh course manager if open
        if hasattr(self, 'course_dialog') and self.course_dialog:
            self.course_dialog.refresh_course()
            
    def add_search_to_course(self):
        """Add current search query to course if method is Text and has results"""
        # Check if search method is "Text"
        if self.search_method_combo.currentText() != "Text":
            self.showMessage("Only text searches can be added to courses", 3000, bg="red")
            return
            
        # Check if there are results
        if not self.model.results or len(self.model.results) == 0:
            self.showMessage("No search results to add to course", 3000, bg="red")
            return
            
        # Get the search query
        query = self.search_input.text().strip()
        if not query:
            self.showMessage("No search query to add", 3000, bg="red")
            return
            
        # Check for unsaved changes in course dialog
        if hasattr(self, 'course_dialog') and self.course_dialog and self.course_dialog.unsaved_changes:
            reply = QtWidgets.QMessageBox.question(
                self,
                'Unsaved Changes',
                'You have unsaved changes in the course manager. Save changes first?',
                QtWidgets.QMessageBox.Save | 
                QtWidgets.QMessageBox.Discard |
                QtWidgets.QMessageBox.Cancel
            )
            
            if reply == QtWidgets.QMessageBox.Cancel:
                return
            elif reply == QtWidgets.QMessageBox.Save:
                self.course_dialog.save_course()
                
        # Show course selection dialog
        dialog = CourseSelectionDialog(self.db, self)
        if dialog.exec_() == QtWidgets.QDialog.Accepted:
            course_id = dialog.get_selected_course()
            if course_id:
                self._add_search_to_course(course_id, query)
                # Refresh course manager if open
                if hasattr(self, 'course_dialog') and self.course_dialog:
                    self.course_dialog.load_course(course_id)

    def add_ayah_to_course(self):
        # Only check for unsaved changes if course dialog exists
        if hasattr(self, 'course_dialog') and self.course_dialog and self.course_dialog.unsaved_changes:
            reply = QtWidgets.QMessageBox.question(
                self,
                'Unsaved Changes',
                'You have unsaved changes in the course manager. Save changes first?',
                QtWidgets.QMessageBox.Save | 
                QtWidgets.QMessageBox.Discard |
                QtWidgets.QMessageBox.Cancel
            )
            
            if reply == QtWidgets.QMessageBox.Cancel:
                return
            elif reply == QtWidgets.QMessageBox.Save:
                self.course_dialog.save_course()
                
        selected = self.results_view.selectionModel().selectedIndexes()
        if not selected:
            self.showMessage("No verses selected", 3000, bg="red")
            return

        ayahs = []
        for index in selected:
            result = self.model.data(index, QtCore.Qt.UserRole)
            if not result:
                continue
            try:
                surah = int(result.get('surah'))
                ayah = int(result.get('ayah'))
                ayahs.append((surah, ayah))
            except (KeyError, ValueError, TypeError):
                continue

        if not ayahs:
            self.showMessage("No valid verses selected", 3000, bg="red")
            return

        dialog = CourseSelectionDialog(self.db, self)
        if dialog.exec_() == QtWidgets.QDialog.Accepted:
            course_id = dialog.get_selected_course()
            if course_id:
                self._add_to_course(course_id, ayahs)
                # Only show course manager if it exists
                if hasattr(self, 'course_dialog') and self.course_dialog:
                    self.course_dialog.load_course(course_id)

    def _add_to_course(self, course_id, ayahs):
        # Group ayahs by surah and find consecutive clusters
        surah_groups = {}
        for surah, ayah in ayahs:
            if surah not in surah_groups:
                surah_groups[surah] = []
            surah_groups[surah].append(ayah)

        # Process each surah group
        entries = []
        for surah, ayahs in surah_groups.items():
            # Sort and find consecutive clusters
            sorted_ayahs = sorted(ayahs)
            clusters = []
            current_start = sorted_ayahs[0]
            current_end = sorted_ayahs[0]

            for ayah in sorted_ayahs[1:]:
                if ayah == current_end + 1:
                    current_end = ayah
                else:
                    clusters.append((current_start, current_end))
                    current_start = current_end = ayah
            clusters.append((current_start, current_end))

            # Create entries for clusters
            for start, end in clusters:
                entries.append({
                    "surah": surah,
                    "start": start,
                    "end": end
                })

        # Add entries to course
        courses = self.db.get_all_courses()
        course = next((c for c in courses if c[0] == course_id), None)
        if not course:
            return

        _, title, items = course
        updated_items = items.copy()

        for entry in entries:
            surah = entry["surah"]
            start = entry["start"]
            end = entry["end"]
            
            new_entry = {
                "text": f"Surah {surah}: Ayah {start}-{end}" if start != end else f"Surah {surah}: Ayah {start}",
                "user_data": {
                    "type": "ayah",
                    "surah": surah,
                    "start": start,
                    "end": end
                }
            }
            updated_items.append(new_entry)  

        self.db.save_course(course_id, title, updated_items)
        self.showMessage(f"Added {len(entries)} entries to course: {title}", 3000)
        if hasattr(self, 'course_dialog') and self.course_dialog:
            self.course_dialog.refresh_course()

    def bookmark_current_ayah(self):
        index = self.results_view.currentIndex()
        if index.isValid():
            result = self.model.data(index, QtCore.Qt.UserRole)
            if result:
                self.db.add_bookmark(result['surah'], result['ayah'])
                self.showMessage("تم حفظ الآية في المرجعية", 2000)
                if hasattr(self, 'bookmark_dialog'):
                    if self.bookmark_dialog:
                        self.bookmark_dialog.load_bookmarks()

    def show_bookmarks(self):
        if not hasattr(self, 'bookmark_dialog') or not self.bookmark_dialog:
            self.bookmark_dialog = BookmarkDialog(self)
            self.bookmark_dialog.list_view.doubleClicked.connect(self.load_and_close_dialog)
        
        self.bookmark_dialog.load_bookmarks()
        self.bookmark_dialog.show()
        self.bookmark_dialog.raise_()
        self.bookmark_dialog.activateWindow()

    def load_and_close_dialog(self):
        self.load_selected_bookmark()
        self.bookmark_dialog.hide()

    def load_selected_bookmark(self):
        index = self.bookmark_dialog.list_view.currentIndex()
        if index.isValid():
            bookmark = self.bookmark_dialog.model.data(index, QtCore.Qt.UserRole)
            self.load_surah_from_current_ayah(
                surah=bookmark['surah'],
                selected_ayah=bookmark['ayah']
            )

    def handle_ctrlj(self):
        index = self.results_view.currentIndex()
        if not index.isValid():
            self.showMessage("No verse selected", 2000,bg="red")
            return

        result = self.model.data(index, QtCore.Qt.UserRole)
        try:
            surah = int(result.get('surah'))
            selected_ayah = int(result.get('ayah'))
        except Exception as e:
            self.showMessage("Invalid surah/ayah information", 3000, bg="red")
            return
        self.load_surah_from_current_ayah(
            surah=surah,
            selected_ayah=selected_ayah
        )

    def toggle_version(self):
        current = self.version_combo.currentIndex()
        new_index = 0 if current else 1
        self.version_combo.setCurrentIndex(new_index)
        self.handle_version_change()

    def toggle_theme(self):
        """
        Toggle between dark and light themes.
        This method inverts the current theme by toggling the theme_action's checked state,
        then updates the UI style by calling update_theme_style.
        """
        # Invert the current theme state.
        dark = not self.theme_action.isChecked()
        # Update the theme action's checked state.
        self.theme_action.setChecked(dark)
        # Apply the new theme.
        self.update_theme_style(dark)
        # if self.results_view.isVisible():
        #     self.results_view.viewport().update()


    def update_theme_style(self, dark):
        splitter_handle = """
        QSplitter::handle {{
            background: {background};
            border: 1px solid {border_color};
            margin: 2px;
        }}
        QSplitter::handle:hover {{
            background: {hover_color};
        }}
        """

        if dark:
            style = f"""
            QWidget {{
                background: #333333;
                color: #FFFFFF;
            }}
            {splitter_handle.format(
                background="#555555",
                border_color="#444444",
                hover_color="#666666"
            )}
            QListView {{
                background: #1e1e1e;
            }}
            QLineEdit {{
                background: #222222;
            }}
            """
        else:
            style = f"""
            {splitter_handle.format(
                background="#cccccc",
                border_color="#aaaaaa",
                hover_color="#999999"
            )}
            """
        
        self.setStyleSheet(style)
        self.delegate.update_theme(dark)
        self.settings.set("darkMode", dark)

    def clear_search(self):
        # Clear both search inputs
        self.search_input_h.clear()
        self.search_input_v.clear()
        self.model.updateResults([])
        self.result_count.clear()
        
        # Reset both surah combo boxes
        self.surah_combo_h.setCurrentIndex(0)
        self.surah_combo_v.setCurrentIndex(0)
        
        self.current_view = None

    def about_dialog(self):
        QtWidgets.QMessageBox.about(
            self,
            "About Quran Search",
            """<b>Quran Search</b> v1.0<br><br>
            Developed by MOSAID<br>
            © 2025 All rights reserved<br><br>
            Quran text from Tanzil.net<br>
            GPL v3 Licensed<br><br>
            <a href="https://mosaid.xyz/quran-search">https://mosaid.xyz</a>"""
        )


    # Then modify your show_help_dialog method:
    def show_help_dialog(self):
        if not hasattr(self, '_help_dialog'):
            self._help_dialog = HelpDialog(self)
            
        if self._help_dialog.isVisible():
            self._help_dialog.hide()
        else:
            self._help_dialog.show()
            self._help_dialog.raise_()
            self._help_dialog.activateWindow()
