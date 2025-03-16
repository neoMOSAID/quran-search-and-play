
from PyQt5 import QtWidgets, QtCore, QtGui



class NoteDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("إضافة تسجيل")
        self.setWindowModality(QtCore.Qt.NonModal)  # Non-modal
        self.resize(400, 300)
        
        # Main vertical layout
        layout = QtWidgets.QVBoxLayout(self)
        
        # Text editor for note entry
        self.editor = QtWidgets.QTextEdit()
        self.editor.setPlaceholderText("Enter your note here...")
        self.editor.setStyleSheet("""
            font-family: 'Amiri';
            font-size: 14pt;
        """)

        layout.addWidget(self.editor)

        
        # Create a horizontal layout for the label and buttons
        h_layout = QtWidgets.QHBoxLayout()
        
        # Label to display verse information
        self.info_label = QtWidgets.QLabel("")
        h_layout.addWidget(self.info_label)
        
        # Dialog buttons
        button_box = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        h_layout.addWidget(button_box)
        
        # Add the horizontal layout to the main layout
        layout.addLayout(h_layout)

