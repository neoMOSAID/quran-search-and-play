

from PyQt5 import QtWidgets
from PyQt5.QtCore import Qt

class CourseSelectionDialog(QtWidgets.QDialog):
    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self.selected_course_id = None
        self.init_ui()
        self.load_courses()

    def init_ui(self):
        self.setWindowTitle("Add to Course")
        self.resize(400, 400)
        
        layout = QtWidgets.QVBoxLayout()
        
        # Course list
        self.course_list = QtWidgets.QListWidget()
        self.course_list.itemDoubleClicked.connect(self.accept)
        layout.addWidget(self.course_list)
        
        # Button layout
        button_layout = QtWidgets.QHBoxLayout()
        
        # New Course button
        self.new_btn = QtWidgets.QPushButton("New Course")
        self.new_btn.clicked.connect(self.create_new_course)
        button_layout.addWidget(self.new_btn)
        
        # Spacer
        button_layout.addStretch()
        
        # Dialog buttons
        self.button_box = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
        )
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        button_layout.addWidget(self.button_box)
        
        layout.addLayout(button_layout)
        self.setLayout(layout)

    def create_new_course(self):
        """Create a new course and refresh the list"""
        new_id = self.db.create_new_course()
        self.load_courses()
        
        # Select the new course
        for i in range(self.course_list.count()):
            item = self.course_list.item(i)
            if item.data(Qt.UserRole) == new_id:
                self.course_list.setCurrentItem(item)
                break

    def load_courses(self):
        self.course_list.clear()
        courses = self.db.get_all_courses()
        for course_id, title, _ in courses:
            item = QtWidgets.QListWidgetItem(title)
            item.setData(Qt.UserRole, course_id)
            self.course_list.addItem(item)

    def get_selected_course(self):
        selected = self.course_list.currentItem()
        if selected:
            return selected.data(Qt.UserRole)
        return None
            


