from PyQt5 import QtWidgets, QtCore
from views.widgets.notes_widget import NotesWidget

class DetailView(QtWidgets.QWidget):
    backRequested = QtCore.pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.notes_widget = NotesWidget()
        self.notes_widget.back_button.clicked.connect(self.handle_back_requested)
        self.initUI()

    def handle_back_requested(self):
        if not self.notes_widget.edit_checkbox.isChecked():
            self.backRequested.emit()

    def initUI(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Create a vertical splitter
        splitter = QtWidgets.QSplitter(QtCore.Qt.Vertical)
        
        # Context View
        self.text_browser = QtWidgets.QTextBrowser()
        splitter.addWidget(self.text_browser)
        
        # Notes widget
        splitter.addWidget(self.notes_widget)
        
        # Set initial sizes (context view gets 70%, notes 30%)
        splitter.setSizes([700, 300])
        
        layout.addWidget(splitter)

    def display_ayah(self, result, search_engine, version, is_dark_theme):
        verses = search_engine.get_ayah_with_context(result['surah'], result['ayah'])
        html = []

        # Set colors based on theme
        text_color = "#000000" if is_dark_theme else "#000000"
        link_color = "#90CAF9" if is_dark_theme else "#1565C0"
        bg_color = self.palette().window().color().name()

        for verse in verses:
            text = verse.get(f'text_{version}', "")
            current_class = "current-ayah" if verse['ayah'] == result['ayah'] else ""
            html.append(f"""
            <div class="verse {current_class}" dir="rtl" style="text-align:left;">
                <div style="font-family: 'Amiri';
                            font-size: 16pt;
                            margin: 5px;
                            color: {text_color};">
                    {text}
                    <span style="color: {link_color};
                                font-size: 14pt;
                                text-decoration: none;">
                        ({verse.get('surah', '')}-{verse.get('chapter', '')} {verse.get('ayah', '')})
                    </span>
                </div>
            </div>
            """)

        self.text_browser.setHtml(f"""
        <html>
            <style>
                body {{
                    background: {bg_color};
                    color: {text_color};
                }}
                a {{
                    color: {link_color};
                    text-decoration: none;
                }}
            </style>
            {''.join(html)}
        </html>
        """)

        # Update notes widget
        self.notes_widget.set_ayah(result['surah'], result['ayah'])