import sys
import io
import folium
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QComboBox, QDateEdit, QListWidget, QSpinBox,
    QPushButton, QAbstractItemView, QGroupBox
)
from PySide6.QtCore import QDate
from PySide6.QtWebEngineWidgets import QWebEngineView

class EonetUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("NASA EONET - Wyszukiwarka Zdarzeń")
        self.resize(1200, 800) # Startowy rozmiar okna


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = EonetUI()
    window.show()
    sys.exit(app.exec())        