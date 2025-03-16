
import re

from PyQt5 import QtWidgets, QtCore, QtGui
from models.quran_model import QuranListModel
from models.notes_manager import NotesManager
from models.search_engine import QuranSearch, QuranWordCache
from controllers.search_worker import SearchWorker
from controllers.audio_controller import AudioController
from utils.settings import AppSettings
from utils.helpers import resource_path
from views.widgets.search_input import SearchLineEdit
from views.detail_view import DetailView
from views.delegates import QuranDelegate
from views.dialogs.compact_help import CompactHelpDialog
from views.dialogs.course import CourseSelectionDialog
from views.dialogs.ayah_selector import AyahSelectorDialog
from views.dialogs.bookmarks import BookmarkDialog
from views.dialogs.notes_manager import NotesManagerDialog
from views.dialogs.data_transfer import DataTransferDialog
from views.dialogs.help_dialog import HelpDialog

#class QuranBrowser(QtWidgets.QMainWindow):
    # Keep core UI methods:
    # - __init__
    # - init_ui
    # - setup_connections
    # - setup_menu
    # - setup_shortcuts
    # - load_settings
    # - closeEvent
    
    # Move audio methods to AudioController:
    # DELETE: play_current, play_next_file, on_media_status_changed
    # DELETE: stop_playback, play_all_results
    
    # Keep search-related methods:
    # - search
    # - handle_search_results
    # - update_results
    
    # Keep UI handlers:
    # - handle_version_change
    # - handle_surah_selection
    # - show_detail_view
    # - show_results_view


# =============================================================================
# Main application window
# =============================================================================
class QuranBrowser(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        icon_path = resource_path("icon.png")
        self.setWindowIcon(QtGui.QIcon(icon_path))
        self.search_engine = QuranSearch()
        self.ayah_selector = None
        self.bookmark_dialog = None
        self.notes_dialog = None
        self.compact_help_dialog = None
        self.current_detail_result = None
        self._status_msg = ""
        self.temporary_message_active = False
        self.message_timer = QtCore.QTimer()
        self.message_timer.timeout.connect(self.revert_status_message)

        self.results_count_int = 0
        self.pending_scroll = None  
        self.scroll_retries = 0
        self.MAX_SCROLL_RETRIES = 5

        self.audio_controller = AudioController(self)

        self.notes_manager = NotesManager()

        self.settings = AppSettings()
        self.theme_action = None
        self.init_ui()
        self.setup_connections()
        self.setup_menu()
        self.setup_shortcuts()
        self.load_settings()
        self.trigger_initial_search()

    def __del__(self):
        try:
            self.model.loading_complete.disconnect(self.handle_pending_scroll)
        except:
            pass

    def init_ui(self):
        # Create search bar widgets.
        self.search_input = SearchLineEdit()
        self.version_combo = QtWidgets.QComboBox()
        self.version_combo.addItems(["Show Uthmani", "Show Simplified"])
        self.search_method_combo = QtWidgets.QComboBox()
        self.search_method_combo.addItems(["Text", "Surah", "Surah FirstAyah LastAyah"])
        self.surah_combo = QtWidgets.QComboBox()
        self.surah_combo.addItems(self.search_engine.get_chapters_names())
        self.clear_button = QtWidgets.QPushButton("Clear")

        # Build the search bar as a compact widget.
        search_bar = QtWidgets.QWidget()
        search_layout = QtWidgets.QHBoxLayout(search_bar)
        search_layout.setContentsMargins(5, 5, 5, 5)
        search_layout.setSpacing(10)
        search_layout.addWidget(QtWidgets.QLabel("Surah:"))
        search_layout.addWidget(self.surah_combo)
        search_layout.addWidget(QtWidgets.QLabel("Version:"))
        search_layout.addWidget(self.version_combo)
        search_layout.addWidget(QtWidgets.QLabel("Method:"))
        search_layout.addWidget(self.search_method_combo)
        search_layout.addWidget(self.search_input)
        search_layout.addWidget(self.clear_button)

        # Ensure the search bar does not expand vertically.
        search_bar.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        search_bar.setMaximumHeight(50)

        # Use QVBoxLayout to stack search bar and results view.
        central = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(central)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)
        layout.addWidget(search_bar)  # Compact search bar at the top.

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
            self.result_count.setText(f"{self.results_count_int} نتائج، {self._status_msg}")
            self.result_count.setStyleSheet("")


    def setup_shortcuts(self):
        QtWidgets.QShortcut(QtGui.QKeySequence("Space"), self, activated=self.handle_space)
        QtWidgets.QShortcut(QtGui.QKeySequence("Escape"), self, activated=self.toggle_version)
        QtWidgets.QShortcut(QtGui.QKeySequence("Backspace"), self, activated=self.handle_backspace)
        QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+F"), self, activated=self.input_focus)
        QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+D"), self, activated=self.toggle_theme)
        QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+P"), self, activated=self.handle_ctrlp)
        #QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+R"), self, activated=self.handle_ctrlr)
        QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+R"), self, activated=self.handle_repeat_all_results)
        QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+Shift+R"), self, 
                            activated=lambda: self.handle_repeat_all_results(limited=True))
        QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+S"), self, activated=self.handle_ctrls)
        QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+W"), self, activated=self.handle_ctrlw)
        QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+Shift+W"), self, activated=self.handle_ctrlsw)
        QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+A"), self.results_view, activated=self.audio_controller.play_current_surah)
        QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+M"), self, activated=self.backto_current_surah)
        QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+Shift+H"), self, activated=self.show_help_dialog)
        QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+H"), self, activated=self.show_compact_help)
        QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+J"), self, activated=self.handle_ctrlj)
        QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+K"), self, activated=self.load_surah_from_current_playback)
        QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+N"), self, activated=self.new_note)
        QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+Shift+N"), self, activated=self.show_notes_manager)
        QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+E"), self, activated=self.show_data_transfer)
        QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+I"), self, activated=self.show_data_transfer)
        QtWidgets.QShortcut(QtGui.QKeySequence("Delete"), self, activated=self.delete_note)
        QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+Shift+P"), self, activated=self.audio_controller.play_all_results)
        QtWidgets.QShortcut(QtGui.QKeySequence("Left"), self, activated=self.navigate_surah_left)
        QtWidgets.QShortcut(QtGui.QKeySequence("Right"), self, activated=self.navigate_surah_right)
        QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+Shift+T"), self, activated=self.show_ayah_selector)
        QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+T"), self, activated=self.add_ayah_to_course)
        QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+Shift+B"), self, activated=self.show_bookmarks)
        QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+B"), self, activated=self.bookmark_current_ayah)
        QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+="), self, activated=self.increase_font_size)  # Ctrl++
        QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl++"), self, activated=self.increase_font_size) 
        QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+-"), self, activated=self.decrease_font_size)
        QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+MouseWheelUp"), self, activated=self.increase_font_size)
        QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+MouseWheelDown"), self, activated=self.decrease_font_size)
        QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+Shift+C"), self, activated=self.copy_all_results)
        QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+C"), self, activated=self.copy_selected_results)
        QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+Alt+N"), self, activated=self.show_quick_note_dialog)

    def increase_font_size(self):
        new_size = self.delegate.base_font_size + 1
        if new_size <= 38:
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
        """Copy selected results to clipboard with verse references"""
        selected = self.results_view.selectionModel().selectedIndexes()
        
        if not selected:
            self.showMessage("No verses selected", 3000, bg="red")
            return
            
        version = self.get_current_version()
        text_list = []
        
        for index in selected:
            result = self.model.data(index, QtCore.Qt.UserRole)
            if result:
                # Remove span tags
                raw_text = result.get(f'text_{version}', '')
                clean_text = re.sub(r'<span[^>]*>|</span>', '', raw_text)
                
                surah_num = result.get('surah', '')
                ayah = result.get('ayah', '')
                chapter = self.search_engine.get_chapter_name(surah_num)
                text_list.append(f"{clean_text} ({chapter} {ayah})")

        full_text = "\n".join(text_list)
        clipboard = QtWidgets.QApplication.clipboard()
        clipboard.setText(full_text)
        self.showMessage(f"Copied {len(selected)} selected verses", 3000)



    def copy_all_results(self):
        """Copy all search results to clipboard with verse references (without span tags)"""
        if not self.model.results:
            self.showMessage("No results to copy", 3000, bg="red")
            return
            
        version = self.get_current_version()
        text_list = []
        
        for result in self.model.results:
            # Remove span tags using regular expression
            raw_text = result.get(f'text_{version}', '')
            clean_text = re.sub(r'<span[^>]*>|</span>', '', raw_text)
            
            surah_num = result.get('surah', '')
            ayah = result.get('ayah', '')
            chapter = self.search_engine.get_chapter_name(surah_num)
            text_list.append(f"{clean_text} ({chapter} {ayah})")
        
        full_text = "\n".join(text_list)
        clipboard = QtWidgets.QApplication.clipboard()
        clipboard.setText(full_text)
        self.showMessage("Copied all results to clipboard", 3000)

    def new_note(self):
        if self.detail_view.isVisible():
            self.detail_view.notes_widget.new_note()

    def show_notes_manager(self):
        if not self.notes_dialog:
            self.notes_dialog = NotesManagerDialog(self.notes_manager, self.search_engine, self)
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
        if self.detail_view.isVisible():
            self.detail_view.notes_widget.delete_note()

    def showMessage(self, message, timeout=3000, bg="#4CAF50"):
        """Temporarily override the left status label"""
        # Cancel any pending reverts
        self.message_timer.stop()
        
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

    def show_ayah_selector(self):
        if not self.ayah_selector:
            self.ayah_selector = AyahSelectorDialog(self.notes_manager, self)
            self.ayah_selector.play_requested.connect(self.audio_controller.play_ayah_range)
            self.ayah_selector.search_requested.connect(self.handle_course_search)
        self.ayah_selector.show()

    def handle_course_search(self, query):
        self.search_input.setText(query)
        self.search()

    def show_quick_note_dialog(self):
        index = self.results_view.currentIndex()
        if not index.isValid():
            self.showMessage("No verse selected", 3000, bg="red")
            return
        
        result = self.model.data(index, QtCore.Qt.UserRole)
        if not result:
            return
        
        try:
            surah = int(result['surah'])
            ayah = int(result['ayah'])
        except (KeyError, ValueError):
            self.showMessage("Invalid verse data", 3000, bg="red")
            return
        
        if not hasattr(self, 'note_dialog'):
            self.note_dialog = NoteDialog(self)
            self.note_dialog.accepted.connect(self.save_quick_note)
        
        self.note_dialog.surah = surah
        self.note_dialog.ayah = ayah
        self.note_dialog.chapter = self.search_engine.get_chapter_name(surah)
        self.note_dialog.editor.clear()
        
        # Update the label with the desired text
        self.note_dialog.info_label.setText(
            f"إضافة تسجيل الى الآية {ayah} من سورة {self.note_dialog.chapter}"
        )
        
        self.note_dialog.show()
        self.note_dialog.raise_()
        self.note_dialog.activateWindow()


    def save_quick_note(self):
        content = self.note_dialog.editor.toPlainText().strip()
        if not content:
            return
        
        self.notes_manager.add_note(
            self.note_dialog.surah,
            self.note_dialog.ayah,
            content
        )
        
        # Refresh notes if detail view is visible
        if self.detail_view.isVisible():
            self.detail_view.notes_widget.load_notes()
        
        self.showMessage("Note saved successfully", 2000)


    def setup_menu(self):
        menu = self.menuBar().addMenu("&Menu")
        self.theme_action = QtWidgets.QAction("Dark Mode", self, checkable=True)
        self.theme_action.toggled.connect(self.update_theme_style)
        menu.addAction(self.theme_action)
        
        # Initialize delegate now that theme_action exists
        self.delegate = QuranDelegate(parent=self.results_view, 
                                    is_dark=self.theme_action.isChecked())
        self.results_view.setItemDelegate(self.delegate)

        # New action: Set Audio Directory.
        audio_dir_action = QtWidgets.QAction("Set Audio Directory", self)
        audio_dir_action.triggered.connect(self.audio_controller.choose_audio_directory)
        menu.addAction(audio_dir_action)

        # bookmark action
        bookmark_action = QtWidgets.QAction("Bookmark Manager", self)
        bookmark_action.triggered.connect(self.show_bookmarks)
        menu.addAction(bookmark_action)

        # notes manager
        notes_action = QtWidgets.QAction("Notes Manager", self)
        notes_action.triggered.connect(self.show_notes_manager)
        menu.addAction(notes_action)

        # bookmark action
        course_action = QtWidgets.QAction("Course Manager", self)
        course_action.triggered.connect(self.show_ayah_selector)
        menu.addAction(course_action)

        # data export/import
        data_transfer_action = QtWidgets.QAction("Data Transfer", self)
        data_transfer_action.triggered.connect(self.show_data_transfer)
        menu.addAction(data_transfer_action)

        # Add About action
        about_action = QtWidgets.QAction("About", self)
        about_action.triggered.connect(self.about_dialog)
        menu.addAction(about_action)
        # Add Help action
        help_action = QtWidgets.QAction("Help", self)
        help_action.triggered.connect(self.show_help_dialog)
        menu.addAction(help_action)
        # Exit action
        exit_action = QtWidgets.QAction("Exit", self)
        exit_action.triggered.connect(self.close)
        menu.addAction(exit_action)


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
                self.notes_manager.export_to_csv(file_path)
                self.showMessage(f"Notes exported to {file_path}", 5000)
            except Exception as e:
                self.showMessage(f"Export failed: {str(e)}", 5000, bg="red")

    def import_notes(self):
        """Handles importing notes from a CSV file."""
        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Import Notes", "", "CSV Files (*.csv)")
        if file_path:
            try:
                imported, duplicates, errors = self.notes_manager.import_from_csv(file_path)
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
        dialog.exec_()

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
        version = self.get_current_version()
        self.delegate.update_version(version)
        self.results_view.viewport().update()
        if self.detail_view.isVisible() and self.current_detail_result:
            is_dark_theme = self.theme_action.isChecked()
            self.detail_view.display_ayah(self.current_detail_result, self.search_engine, version,is_dark_theme)

    def get_current_version(self):
        return "uthmani" if "Uthmani" in self.version_combo.currentText() else "simplified"

    def handle_surah_selection(self, index):
        if index < 0:
            index = self.surah_combo.currentIndex()
        surah = index + 1
        try:
            results = self.search_engine.search_by_surah(surah)
            for result in results:
                if self.notes_manager.has_note(result['surah'], result['ayah']):
                    #bullet = "◉ "  # smaller bullet than "●" "• "
                    bullet = "<span style='font-size:32px;'>•</span> "
                    result['text_simplified'] = bullet + result['text_simplified']
                    result['text_uthmani'] = bullet + result['text_uthmani']
            self.update_results(results, f"Surah {surah} (Automatic Selection)")
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
            results = self.search_engine.search_by_surah(surah)
            for result in results:
                if self.notes_manager.has_note(result['surah'], result['ayah']):
                    #bullet = "◉ "  # smaller bullet than "●" "• "
                    bullet = "<span style='font-size:32px;'>•</span> "
                    result['text_simplified'] = bullet + result['text_simplified']
                    result['text_uthmani'] = bullet + result['text_uthmani']
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
        self.handle_surah_selection(self.current_surah-1)
        current_ayah = self.current_start_ayah + self.current_sequence_index -1
        self._scroll_to_ayah(self.current_surah,current_ayah)

    def load_surah_from_current_playback(self):
        """
        If a playback sequence is active, use its current surah and the
        last played (or currently playing) ayah to load that surah and scroll to it.
        Bind this method to Ctrl+K.
        """
        current_media = self.audio_controller.player.media()
        if current_media is not None:
            url = current_media.canonicalUrl()
            if url.isLocalFile():
                file_path = url.toLocalFile()
                current_surah = int(os.path.basename(file_path)[:3])
                current_ayah = int(os.path.basename(file_path)[3:6])
                self.load_surah_from_current_ayah(surah=current_surah, selected_ayah=current_ayah)

    # def focus_notes(self):
    #     if self.detail_view.isVisible():
    #         self.detail_view.notes_widget.editor.setFocus()

    def search(self):
        if self.detail_view.isVisible():
            self.show_results_view()

        query = self.search_input.text().strip()
        method = self.search_method_combo.currentText()
        if not query and method == "Text":
            self.showMessage("Please enter a search query", 3000, bg="red")
            return
        self.search_input.update_history(query)
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

    def handle_search_results(self, results):
        self.model.updateResults(results)
        self.results_count_int = len(results)
        self.result_count.setText(f"Found {self.results_count_int} results")
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
        self.results_count_int = len(self.model.results)
        self.result_count.setText(f"Found {self.results_count_int} results.")
        self.model.loading_complete.disconnect()  # Clean up connection

    def update_results(self, results, query):
        self.model.updateResults(results)
        self.results_count_int = len(results)
        self.result_count.setText(f"Found {self.results_count_int} results.")
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
        if self.detail_view.isVisible():
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
        self.play_current(count=6)

    def handle_ctrlr(self):
        method = self.search_method_combo.currentText()
        if not method == "Surah FirstAyah LastAyah":
            self.showMessage("Please select a range to repeat using 'Surah FirstAyah LastAyah' search method", 10000, bg="red")
            return
        self.playing_range = 1
        self.playing_range_max = self.results_count_int
        self.play_current(count=self.playing_range_max)

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
                
            self.max_repeats = count
            self.repeat_count = 0
            self.showMessage(f"Repeating {self.max_repeats} times", 3000)
        else:
            # Original infinite repeat behavior
            self.max_repeats = 0  
            self.repeat_count = 0
            self.showMessage("Repeating all results continuously", 3000)
        
        # Common playback start logic
        self.repeat_all = True
        self.audio_controller.play_all_results()

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
        # First try existing items
        for row in range(self.model.rowCount()):
            index = self.model.index(row, 0)
            result = self.model.data(index, QtCore.Qt.UserRole)
            if (result['surah'] == surah and 
                result['ayah'] == ayah):
                self.results_view.setCurrentIndex(index)
                self.results_view.scrollTo(index, 
                    QtWidgets.QAbstractItemView.PositionAtCenter)
                return True
                
        # If not found, check if more results need loading
        if self.model._displayed_results < len(self.model.results):
            self.model.load_remaining_results()
            
        return False



    def add_ayah_to_course(self):
        index = self.results_view.currentIndex()
        if not index.isValid():
            self.showMessage("No verse selected", 3000, bg="red")
            return
            
        result = self.model.data(index, QtCore.Qt.UserRole)
        try:
            surah = int(result['surah'])
            ayah = int(result['ayah'])
        except (KeyError, ValueError):
            self.showMessage("Invalid verse data", 3000, bg="red")
            return

        dialog = CourseSelectionDialog(self.notes_manager, self)
        if dialog.exec_() == QtWidgets.QDialog.Accepted:
            course_id = dialog.get_selected_course()
            if course_id:
                self._add_to_course(course_id, surah, ayah)
                self.show_ayah_selector()
                self.ayah_selector.load_course_by_id(course_id)

    def _add_to_course(self, course_id, surah, ayah):
        # Get existing course data
        courses = self.notes_manager.get_all_courses()
        course = next((c for c in courses if c[0] == course_id), None)
        if not course:
            return

        # Create new item entry
        new_entry = {
            "text": f"Surah {surah}: Ayah {ayah}",
            "user_data": {
                "type": "ayah",
                "surah": surah,
                "start": ayah,
                "end": ayah
            }
        }

        # Update course items
        _, title, items = course
        updated_items = items.copy()
        updated_items.append(json.dumps(new_entry))

        # Save updated course
        self.notes_manager.save_course(course_id, title, updated_items)
        self.showMessage(f"Added to course: {title}", 3000)


    def bookmark_current_ayah(self):
        index = self.results_view.currentIndex()
        if index.isValid():
            result = self.model.data(index, QtCore.Qt.UserRole)
            if result:
                self.notes_manager.add_bookmark(result['surah'], result['ayah'])
                self.showMessage("تم حفظ الآية في المرجعية", 2000)

    def show_bookmarks(self):
        if not hasattr(self, 'bookmark_dialog') or not self.bookmark_dialog:
            self.bookmark_dialog = BookmarkDialog(self)
            self.bookmark_dialog.list_view.doubleClicked.connect(self.load_and_close_dialog)
        
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
        self.search_input.clear()
        self.model.updateResults([])
        self.result_count.clear()
        self.surah_combo.setCurrentIndex(0)

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
