
import os

from PyQt5.QtWebEngineWidgets import QWebEnginePage
from PyQt5.QtGui import QDesktopServices

os.environ['QTWEBENGINE_CHROMIUM_FLAGS'] = '--password-store=disable'

class CustomWebEnginePage(QWebEnginePage):
    def acceptNavigationRequest(self, url, nav_type, isMainFrame):
        if nav_type == QWebEnginePage.NavigationTypeLinkClicked:
            # Open the URL in the default browser
            QDesktopServices.openUrl(url)
            return False  # Prevent the link from loading in the current view
        return super().acceptNavigationRequest(url, nav_type, isMainFrame)

