from PyQt5 import QtWidgets, QtCore

from models.quran_model import BookmarkModel
from views.delegates import BookMarksDelegate

class BookmarkDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.setWindowTitle("الآيات المرجعية")
        self.resize(600, 400)
        self.setWindowModality(QtCore.Qt.NonModal)
        
        # Create model and delegate
        self.model = BookmarkModel()
        self.delegate = BookMarksDelegate()
        
        # Setup UI
        self.list_view = QtWidgets.QListView()
        self.list_view.setItemDelegate(self.delegate)
        self.list_view.setModel(self.model)
        self.list_view.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.list_view.setFocusPolicy(QtCore.Qt.StrongFocus)
        self.list_view.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.list_view.setFocus()
        self.list_view.setVerticalScrollMode(QtWidgets.QAbstractItemView.ScrollPerPixel)
        self.list_view.verticalScrollBar().setSingleStep(20)
        self.list_view.setStyleSheet("""
            QListView {
                show-decoration-selected: 1;
            }
            QListView::item {
                padding-right: 25px;
            }
            QListView::item:selected {
                background: palette(highlight);
                color: palette(highlighted-text);
            }
            QScrollBar:vertical {
                width: 12px;
            }
        """)

        # Connect scrollbar to load more
        self.list_view.verticalScrollBar().valueChanged.connect(
            self.check_scroll_position
        )
        
        # Buttons
        self.remove_btn = QtWidgets.QPushButton("حذف المحدد")
        self.close_btn = QtWidgets.QPushButton("إغلاق")
        
        # Layout
        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(self.list_view)
        
        btn_layout = QtWidgets.QHBoxLayout()
        btn_layout.addWidget(self.remove_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(self.close_btn)
        layout.addLayout(btn_layout)
        
        # Connections
        self.close_btn.clicked.connect(self.hide)
        self.remove_btn.clicked.connect(self.remove_selected)
        self.list_view.doubleClicked.connect(self.load_and_close)

        self.list_view.installEventFilter(self)


    def check_scroll_position(self):
        if self.model._loaded_count < len(self.model._bookmarks):
            self.model.load_next_chunk()

    def eventFilter(self, source, event):
        if source is self.list_view and event.type() == QtCore.QEvent.KeyPress:
            if event.key() in (QtCore.Qt.Key_Return, QtCore.Qt.Key_Enter):
                self.load_and_close()
                return True
            elif event.key() == QtCore.Qt.Key_Delete:
                self.remove_selected()
                return True
            elif event.key() in (QtCore.Qt.Key_Up, QtCore.Qt.Key_Down):
                # Allow default navigation
                return False
        return super().eventFilter(source, event)
    
    def showEvent(self, event):
        self.load_bookmarks()
        # Auto-select first item if exists
        if self.model.rowCount() > 0:
            index = self.model.index(0)
            self.list_view.setCurrentIndex(index)

    def load_bookmarks(self):
        bookmarks = self.parent.notes_manager.get_all_bookmarks(self.parent.search_engine)
        self.model.load_bookmarks(bookmarks)
        # Show first items immediately
        self.model._loaded_count = min(50, len(bookmarks))
        self.model.layoutChanged.emit()

    def load_and_close(self):
        self.parent.load_selected_bookmark()
        #self.hide()

    def remove_selected(self):
        selected = self.list_view.selectionModel().selectedIndexes()
        if not selected:
            return
            
        # Remove in reverse order
        for index in sorted(selected, reverse=True):
            row = index.row()
            if row >= len(self.model._bookmarks):
                continue  # Prevent invalid access
                
            bm = self.model.data(index, Qt.UserRole)
            self.parent.notes_manager.delete_bookmark(bm['surah'], bm['ayah'])
            
            self.model.beginRemoveRows(QtCore.QModelIndex(), row, row)
            del self.model._bookmarks[row]
            self.model._loaded_count = min(self.model._loaded_count, len(self.model._bookmarks))
            self.model.endRemoveRows()

