import sys
from PyQt5 import QtWidgets 
from views.main_window import QuranBrowser
from PyQt5.QtGui import QGuiApplication


def main():
    app = QtWidgets.QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setApplicationName("QuranSearch")
    app.setOrganizationName("MOSAID")
    window = QuranBrowser()
    window.setWindowTitle("Quran Search")  # Proper window title
    window.setWindowRole("QuranSearch")
    window.show()
    QGuiApplication.instance().setApplicationDisplayName("QuranSearch")
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()