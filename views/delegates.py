
from collections import OrderedDict

from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtGui import QColor
from utils.settings import AppSettings


class QuranDelegate(QtWidgets.QStyledItemDelegate):
    """Custom delegate for rendering Quran verses with proper RTL support."""
    def __init__(self, version="uthmani", parent=None,is_dark=False):
        super().__init__(parent)
        self.version = version
        self.is_dark = is_dark
        self.query = ""
        self.update_theme(is_dark)
        self.settings = AppSettings()
        self.base_font_size = self.settings.value("resultFontSize", 16, type=int)

    def update_font_size(self, new_size):
        self.base_font_size = new_size
        self.settings.set("resultFontSize", self.base_font_size)
        self.sizeHintChanged.emit(QtCore.QModelIndex())  # Notify view of size changes

    def update_theme(self, is_dark):
        self.is_dark = is_dark
        if self.is_dark:
            self.highlight_color = "#5D6D7E"
        else:
            self.highlight_color = "#a0c4ff"
        if self.parent():
            self.parent().viewport().update()

    def update_version(self, version):
        self.version = version
        if self.parent():
            self.parent().viewport().update()

    def paint(self, painter, option, index):
        painter.save()
        result = index.data(QtCore.Qt.UserRole)

        # Check if pinned
        is_pinned = hasattr(self.parent().window(), 'pinned_verses') and any(
            v['surah'] == result['surah'] and v['ayah'] == result['ayah']
            for v in self.parent().window().pinned_verses
        )

        # Draw pinned background (only if not selected)
        if is_pinned and not (option.state & QtWidgets.QStyle.State_Selected):
            bg_color = QtGui.QColor("#3b3b1f" if self.is_dark else "#F0E68C")
            painter.fillRect(option.rect, bg_color)

        # Render text
        doc = QtGui.QTextDocument()
        doc.setDocumentMargin(2)
        text = self._format_text(result, self.version)
        doc.setHtml(text)
        text_option = doc.defaultTextOption()
        text_option.setTextDirection(QtCore.Qt.RightToLeft)
        text_option.setAlignment(QtCore.Qt.AlignRight)
        doc.setDefaultTextOption(text_option)
        doc.setTextWidth(option.rect.width() - 20)

        if option.state & QtWidgets.QStyle.State_Selected:
            painter.fillRect(option.rect, option.palette.highlight())

        painter.translate(option.rect.topLeft())
        doc.drawContents(painter)
        painter.restore()

    def _format_text(self, result, version):
        text = result.get(f"text_{version}", "")

        # Check if verse is pinned
        is_pinned = hasattr(self.parent().window(), 'pinned_verses') and any(
            v['surah'] == result['surah'] and v['ayah'] == result['ayah']
            for v in self.parent().window().pinned_verses
        )

        # Indicator icon
        pin_indicator = """<span style="color: goldenrod;">&#9733;</span> """ if is_pinned else ""

        # Background color depending on theme
        pinned_bg = "#3b3b1f" if self.is_dark else "#F0E68C"  # Dark: olive-brown / Light: cornsilk
        normal_bg = "transparent"

        bg_color = pinned_bg if is_pinned else normal_bg
        
        # Apply highlighting if enabled
        main_window = self.parent().window()
        if hasattr(main_window, 'highlight_action') and main_window.highlight_action.isChecked():
            highlight_words = main_window.highlight_words
            if highlight_words:
                is_dark = main_window.theme_action.isChecked()
                highlight_color = "yellow" if is_dark else "red"
                
                # Apply highlighting for each word
                for word in highlight_words:
                    # Replace every occurrence of the word with highlighted version
                    text = text.replace(
                        word, 
                        f"<span style='color: {highlight_color};'>{word}</span>"
                    )

        return f"""
        <div dir="rtl" style="text-align:left; background-color: {bg_color}; width:100%; margin:0; padding:10px;">
            <div style="font-family: 'Amiri';
                        font-size: {self.base_font_size}pt;
                        margin: 5px;">
                {pin_indicator}{text}
                <span style="color: #006400;
                            font-size: {self.base_font_size - 2}pt;">
                    ({result.get('surah', '')}-{result.get('chapter', '')} {result.get('ayah', '')})
                </span>
            </div>
        </div>
        """


    def sizeHint(self, option, index):
        result = index.data(QtCore.Qt.UserRole)
        if not result:
            return QtCore.QSize(0, 0)
        
        doc = QtGui.QTextDocument()
        doc.setHtml(self._format_text(result, self.version))
        doc.setTextWidth(option.rect.width() - 20)
        return QtCore.QSize(int(doc.idealWidth()) + 20, int(doc.size().height()))





#class BookMarksDelegate(QtWidgets.QStyledItemDelegate):
    # Keep all original methods:
    # - paint
    # - sizeHint
    # - clear_cache


class BookMarksDelegate(QtWidgets.QStyledItemDelegate):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.doc_cache = OrderedDict()
        self.max_cache_size = 100

    def paint(self, painter, option, index):
        painter.save()
        
        # Setup style options
        option = QtWidgets.QStyleOptionViewItem(option)
        self.initStyleOption(option, index)
        
        # Use style's drawing capabilities
        style = option.widget.style() if option.widget else QtWidgets.QApplication.style()
        
        # Draw background
        style.drawPrimitive(QtWidgets.QStyle.PE_PanelItemViewItem, option, painter, option.widget)
        
        # Setup HTML document
        doc = QtGui.QTextDocument()
        doc.setHtml(option.text)
        doc.setDocumentMargin(2)
        
        # Set text color based on state
        if option.state & QtWidgets.QStyle.State_Selected:
            doc.setDefaultStyleSheet(f"body {{ color: {option.palette.highlightedText().color().name()}; }}")
        else:
            doc.setDefaultStyleSheet(f"body {{ color: {option.palette.text().color().name()}; }}")
        
        # Calculate positioning
        text_rect = style.subElementRect(QtWidgets.QStyle.SE_ItemViewItemText, option, option.widget)
        painter.translate(text_rect.topLeft())
        doc.setTextWidth(text_rect.width())
        doc.drawContents(painter)
        
        painter.restore()

    def sizeHint(self, option, index):
        if not index.isValid():
            return QtCore.QSize(0, 0)
        
        # Use timestamp + surah + ayah as unique cache key
        bm_data = index.data(QtCore.Qt.UserRole)
        cache_key = f"{bm_data['timestamp']}-{bm_data['surah']}-{bm_data['ayah']}"
        
        # Return cached size if available
        if cache_key in self.doc_cache:
            return self.doc_cache[cache_key]
        
        # Calculate new size
        doc = QtGui.QTextDocument()
        doc.setHtml(index.data(QtCore.Qt.DisplayRole))
        doc.setDocumentMargin(2)
        doc.setTextWidth(option.rect.width() - 20)
        
        size = QtCore.QSize(
            int(doc.idealWidth()) + 20,
            int(doc.size().height()) + 8
        )
        
        # Manage cache size
        if len(self.doc_cache) >= self.max_cache_size:
            self.doc_cache.popitem(last=False)  # Remove oldest entry
        self.doc_cache[cache_key] = size
        
        return size

    def clear_cache(self):
        self.doc_cache.clear()


class ShortsTableDelegate(QtWidgets.QStyledItemDelegate):
    def __init__(self, left=25, right=25, parent=None):
        super().__init__(parent)
        self.left = left
        self.right = right

    def paint(self, painter, option, index):
        # Make a copy of the option and adjust the rectangle for padding.
        new_option = QtWidgets.QStyleOptionViewItem(option)
        new_option.palette.setColor(QtGui.QPalette.HighlightedText, QColor("#000"))
        new_option.rect = option.rect.adjusted(self.left, 0, -self.right, 0)

        super().paint(painter, new_option, index)