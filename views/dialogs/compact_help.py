

from PyQt5 import QtWidgets, QtCore, QtGui
from views.delegates import ShortsTableDelegate

class CompactHelpDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("اختصارات لوحة المفاتيح")
        self.resize(700, 600)
        self.init_ui()

    def init_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        
        # Create table with 2 columns
        self.table = QtWidgets.QTableWidget()
        self.table.setColumnCount(2)
        self.table.setLayoutDirection(QtCore.Qt.RightToLeft)
        self.table.setHorizontalHeaderLabels(["الاختصار", "الوظيفة"])
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        # Column 0 resizes to fit contents, column 1 stretches to fill the remaining space
        #self.table.horizontalHeader().setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QtWidgets.QHeaderView.Stretch)
        self.setStyleSheet("""
            font-family: Amiri;
            font-size: 14pt;
            color: #000;
        """)
        
        self.table.setItemDelegate(ShortsTableDelegate(15, 15, self.table))
        # Data structure:
        # For header rows, tuple: (True, "Category header text")
        # For normal rows, tuple: (False, (category, shortcut, function))
        rows = [
            (True, " لمزيد من التفاصيل : Ctrl + Shift + H"),
            (False,("","","")),

            (True, "التنقل والبحث"),
            (False, ("التنقل", "Ctrl + F", "الانتقال إلى حقل البحث")),
            (False, ("التنقل", "Ctrl + Shift + F", "التحول الى \"البحث بالكلمات\" ثم الانتقال إلى حقل البحث")),
            (False, ("التنقل", "Ctrl + W", "التحول الى \"البحث بالسورة\" ثم الانتقال إلى حقل البحث")),
            (False, ("التنقل", "Ctrl + Shift + W", "التحول الى \"البحث بنطاق الآيات\" ثم الانتقال إلى حقل البحث")),
            (False, ("التنقل", "Ctrl + J", "الانتقال إلى سورة الآية المحددة")),
            (False, ("التنقل", "Ctrl + K", "العودة إلى سورة التشغيل الحالية")),
            (False, ("التنقل", "Ctrl + M", "العودة إلى السورة الحالية")),
            (False, ("التنقل", "← Left / Right →", "التنقل بين السور")),
            (False, ("التنقل", "↑ Up / Down ↓", "التنقل بين الآيات")),
            (False, ("التنقل", "Backspace", "العودة الى النتائج من سياق الآية")),
            (False, ("التنقل", "Ctrl + C", " نسخ الآيات المحددة")),
            (False, ("التنقل", "Ctrl + Shift + C", " نسخ جميع النتائج ")),

            (True, "التشغيل الصوتي"),
            (False, ("الصوت", "Space", "تلاوة الآية المحددة أو توقيف/تشغيل التلاوة")),
            (False, ("الصوت", "Ctrl + P", "تلاوة الآية و 5 بعدها")),
            (False, ("الصوت", "Ctrl + A", "تلاوة السورة كاملة و الاستمرار في تلاوة القرآن")),
            (False, ("الصوت", "Ctrl + Shift + P", "تلاوة جميع النتائج")),
            (False, ("الصوت", "Ctrl + R", "تكرار الإستماع لجميع النتائج")),
            (False, ("الصوت", "Ctrl + Shift + R", "تكرار الإستماع لجميع النتائج عددا محددا من المرات")),
            (False, ("الصوت", "Ctrl + S", "توقيف وإنهاء التلاوة")),
            
            (True, "إدارة الملاحظات"),
            (False, ("الملاحظات", "Ctrl + Shift + N", " إظهار نافذة إدارة الملاحظات")),
            (False, ("الملاحظات", "Ctrl + N", " ملاحظة جديدة (وضع سياق الآية)")),
            (False, ("الملاحظات", "Ctrl + Alt + N", "ملاحظة جديدة")),
            (False, ("الملاحظات", "Ctrl + S", "حفظ الملاحظة")),
            (False, ("الملاحظات", "Delete", "حذف الملاحظة")),
            (False, ("الملاحظات", "Ctrl + E", "تصدير و استيراد الملاحظات")),
            (False, ("الملاحظات", "Ctrl + I", "تصدير و استيراد الملاحظات")),
            
            (True, "إدارة الدروس"),
            (False, ("الدروس", "Ctrl + Shift + T", "إظهار نافذة الدروس")),
            (False, ("الدروس", "← Left / Right →", "التنقل بين الدروس")),
            (False, ("الدروس", "↑ Up / Down ↓", "التنقل بين التسجيلات")),
            (False, ("الدروس", "Delete", "حذف التسجيل المحدد  ")),
            (False, ("الدروس", "Ctrl + Delete", "حذف الدرس الحالي  ")),
            (False, ("الدروس", "↑ Ctrl + Up / Ctrl + Down ↓", "تغيير ترتيب التسجيلات")),
            (False, ("الدروس", "Ctrl + T", "إضافة الآية المحددة إلى أحد الدروس")),
            (False, ("الدروس", "Ctrl + Y", "إضافة البحث الحالي إلى أحد الدروس")),
            
            (True, "إدارة المرجعيات"),
            (False, ("المرجعيات", "Ctrl + Shift + B", "فتح نافذة المرجعيات")),
            (False, ("المرجعيات", "Ctrl + B", "إضافة الآية المحددة الى قائمة المرجعيات")),
            (False, ("المرجعيات", "Delete", "حذف الآية المحددة من قائمة المرجعيات")),

            (True, "إدارة الآيات المثبتة"),
            (False, ("الآيات المثبتة", "Ctrl + Shift + O", "فتح نافذة الآيات المثبتة")),
            (False, ("الآيات المثبتة", "Ctrl + O", "إضافة الآية المحددة الى قائمة الآيات المثبتة")),
            (False, ("الآيات المثبتة", "Ctrl + O", "حذف الآية المحددة من قائمة الآيات المثبتة")),
            
            
            (True, "الإعدادات العامة"),
            (False, ("التخصيص", "Ctrl + D", "تبديل الوضع الليلي")),
            (False, ("المساعدة", "Ctrl + H", "إظهار نافذة اختصارات لوحة المفاتيح")),
            (False, ("المساعدة", "Ctrl + Shift + H", "إظهار نافذة المساعدة")),
            (False, ("التخصيص", "Esc", "تبديل نوع الخط : عثماني / مبسط")),
            (False, ("التخصيص", "Ctrl + =", "زيادة حجم الخط")),
            (False, ("التخصيص", "Ctrl + +", "زيادة حجم الخط")),
            (False, ("التخصيص", "Ctrl + -", "نقصان حجم الخط"))
        ]
        
        self.table.setRowCount(len(rows))
        
        # Colors: header rows get a distinct background.
        header_bg = QtGui.QColor("#5D6D7E")
        
        row_index = 0
        for is_header, data in rows:
            if is_header:
                # Create header row spanning both columns.
                item = QtWidgets.QTableWidgetItem(data)
                item.setBackground(header_bg)
                item.setTextAlignment(QtCore.Qt.AlignCenter)
                self.table.setItem(row_index, 0, item)
                self.table.setSpan(row_index, 0, 1, 2)
                row_index += 1
            else:
                # Only add the shortcut and function columns.
                category, shortcut, function = data
                item_short = QtWidgets.QTableWidgetItem("\u202A" + shortcut + "\u202C")
                item_short.setTextAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
                item_func = QtWidgets.QTableWidgetItem(function)
                self.table.setItem(row_index, 0, item_short)
                self.table.setItem(row_index, 1, item_func)
                row_index += 1

        layout.addWidget(self.table)
        close_btn = QtWidgets.QPushButton("إغلاق")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)


