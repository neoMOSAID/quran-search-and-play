from PyQt5 import QtWidgets, QtCore
from views.widgets.notes_widget import NotesWidget

class DetailView(QtWidgets.QWidget):
    backRequested = QtCore.pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.notes_widget = NotesWidget()
        self.initUI()


    def initUI(self):
        # Split view
        splitter = QtWidgets.QSplitter(QtCore.Qt.Vertical)

        # Context View
        context_widget = QtWidgets.QWidget()
        context_layout = QtWidgets.QVBoxLayout(context_widget)
        self.back_button = QtWidgets.QPushButton("← Back to Results")
        self.text_browser = QtWidgets.QTextBrowser()
        context_layout.addWidget(self.back_button)
        context_layout.addWidget(self.text_browser)

        # Add widgets to splitter
        splitter.addWidget(context_widget)
        splitter.addWidget(self.notes_widget)
        splitter.setSizes([250, 350])  # Initial sizes

        # Main layout
        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(splitter)

        # Connections
        self.back_button.clicked.connect(self.backRequested.emit)

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
