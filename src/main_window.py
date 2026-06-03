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

        # 1. Główny widget i układ (Podział na Lewo: filtry, Prawo: mapa)
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)

        # --- LEWY PANEL (Kontrolki) ---
        filters_layout = QVBoxLayout()
        filters_group = QGroupBox("Filtry Wyszukiwania")
        filters_group.setFixedWidth(300) # Sztywna szerokość bocznego panelu
        filters_group.setLayout(filters_layout)

        # Status (Dopasowane do SQL: open / closed)
        filters_layout.addWidget(QLabel("Status zdarzenia:"))
        self.status_combo = QComboBox()
        self.status_combo.addItems(["Wszystkie", "open", "closed"])
        filters_layout.addWidget(self.status_combo)

        # Daty (date_from i date_to)
        filters_layout.addWidget(QLabel("Data od:"))
        self.date_from = QDateEdit(calendarPopup=True)
        # Ustawiamy domyślnie datę na miesiąc wstecz
        self.date_from.setDate(QDate.currentDate().addDays(-30)) 
        filters_layout.addWidget(self.date_from)

        filters_layout.addWidget(QLabel("Data do:"))
        self.date_to = QDateEdit(calendarPopup=True)
        self.date_to.setDate(QDate.currentDate())
        filters_layout.addWidget(self.date_to)

        # Kategorie - Biała lista (white_list)
        filters_layout.addWidget(QLabel("Kategorie (Biała lista):"))
        self.category_list = QListWidget()
        # Pozwala zaznaczać wiele elementów (z wciśniętym Ctrl lub Shift)
        self.category_list.setSelectionMode(QAbstractItemView.SelectionMode.MultiSelection)
        # Tu w przyszłości pobierzesz kategorie z bazy, na razie dodajemy na sztywno
        self.category_list.addItems(["Wildfires", "Volcanoes", "Severe Storms", "Sea and Lake Ice"])
        filters_layout.addWidget(self.category_list)

        # Limit wyników (limit)
        filters_layout.addWidget(QLabel("Limit wyników:"))
        self.limit_spin = QSpinBox()
        self.limit_spin.setRange(1, 1000)
        self.limit_spin.setValue(100) # Domyślnie 100 tak jak w funkcji kolegi
        filters_layout.addWidget(self.limit_spin)

        # Przycisk wyszukiwania
        self.search_btn = QPushButton("Szukaj na mapie")
        # Tu w przyszłości podepniemy wywołanie funkcji querries:
        # self.search_btn.clicked.connect(self.perform_search) 
        
        # Ostylowanie przycisku dla lepszego wyglądu
        self.search_btn.setStyleSheet("background-color: #2b5c8f; color: white; padding: 8px; font-weight: bold;")
        filters_layout.addWidget(self.search_btn)
        
        filters_layout.addStretch() # Wypycha elementy ładnie do góry, żeby nie wisiały na środku


        main_layout.addWidget(filters_group)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = EonetUI()
    window.show()
    sys.exit(app.exec())        