import sys
import io
import folium
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QComboBox, QDateEdit, QListWidget, QSpinBox,
    QPushButton, QAbstractItemView, QGroupBox, QDoubleSpinBox, QCheckBox
)
from PySide6.QtCore import QDate
from PySide6.QtWebEngineWidgets import QWebEngineView
import sqlite3
from db_queries import search_events

class EonetUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.db_path = "data/eonet.db"
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
        filters_layout.addWidget(self.category_list)

        # Limit wyników (limit)
        filters_layout.addWidget(QLabel("Limit wyników:"))
        self.limit_spin = QSpinBox()
        self.limit_spin.setRange(1, 1000)
        self.limit_spin.setValue(100) # Domyślnie 100 tak jak w funkcji kolegi
        filters_layout.addWidget(self.limit_spin)

        # Kategorie - Czarna lista (black_list)
        filters_layout.addWidget(QLabel("Kategorie (Czarna lista):"))
        self.black_list_widget = QListWidget()
        self.black_list_widget.setSelectionMode(QAbstractItemView.SelectionMode.MultiSelection)
        filters_layout.addWidget(self.black_list_widget)

        self.load_categories()

        # Sortowanie (sort_by)
        filters_layout.addWidget(QLabel("Sortowanie:"))
        self.sort_combo = QComboBox()
        self.sort_combo.addItems(["Najnowsze", "Najstarsze"])
        filters_layout.addWidget(self.sort_combo)

        # Współrzędne Geograficzne (BBox)
        bbox_group = QGroupBox("Ogranicz obszar wyszukiwania")
        bbox_layout = QVBoxLayout()
        
        self.enable_bbox_cb = QCheckBox("Aktywuj filtr współrzędnych")
        bbox_layout.addWidget(self.enable_bbox_cb)

        # Pola liczbowe z ułamkami (z domyślnymi zakresami dla globu)
        self.min_lon = QDoubleSpinBox(); self.min_lon.setRange(-180, 180); self.min_lon.setEnabled(False)
        self.max_lon = QDoubleSpinBox(); self.max_lon.setRange(-180, 180); self.max_lon.setEnabled(False)
        self.min_lat = QDoubleSpinBox(); self.min_lat.setRange(-90, 90); self.min_lat.setEnabled(False)
        self.max_lat = QDoubleSpinBox(); self.max_lat.setRange(-90, 90); self.max_lat.setEnabled(False)

        # Podpięcie logiki: kliknięcie checkboxa włącza/wyłącza pola
        self.enable_bbox_cb.toggled.connect(self.min_lon.setEnabled)
        self.enable_bbox_cb.toggled.connect(self.max_lon.setEnabled)
        self.enable_bbox_cb.toggled.connect(self.min_lat.setEnabled)
        self.enable_bbox_cb.toggled.connect(self.max_lat.setEnabled)

        bbox_layout.addWidget(QLabel("Min Długość (Lon):")); bbox_layout.addWidget(self.min_lon)
        bbox_layout.addWidget(QLabel("Max Długość (Lon):")); bbox_layout.addWidget(self.max_lon)
        bbox_layout.addWidget(QLabel("Min Szerokość (Lat):")); bbox_layout.addWidget(self.min_lat)
        bbox_layout.addWidget(QLabel("Max Szerokość (Lat):")); bbox_layout.addWidget(self.max_lat)
        
        bbox_group.setLayout(bbox_layout)
        filters_layout.addWidget(bbox_group)

        # Przycisk wyszukiwania
        self.search_btn = QPushButton("Szukaj na mapie")
        self.search_btn.clicked.connect(self.perform_search) 
        
        # Ostylowanie przycisku dla lepszego wyglądu
        self.search_btn.setStyleSheet("background-color: #2b5c8f; color: white; padding: 8px; font-weight: bold;")
        filters_layout.addWidget(self.search_btn)
        
        filters_layout.addStretch() # Wypycha elementy ładnie do góry, żeby nie wisiały na środku

        # --- PRAWY PANEL (Mapa Folium w silniku przeglądarki) ---
        self.web_view = QWebEngineView()
        self.init_map()

        main_layout.addWidget(self.web_view)    
        main_layout.addWidget(filters_group)


    def load_categories(self):
        """Pobiera unikalne kategorie z bazy i wrzuca do listy w UI"""
        self.category_list.clear() # Czyścimy to, co było wpisane na sztywno
        try:
            with sqlite3.connect(self.db_path) as conn:
                cur = conn.cursor()
                # Zapytanie wyciągające nazwy kategorii
                cur.execute("SELECT title FROM categories ORDER BY title")
                categories = [row[0] for row in cur.fetchall()]
                self.category_list.addItems(categories)
                self.black_list_widget.addItems(categories)
        except sqlite3.Error as e:
            print(f"Błąd bazy danych przy ładowaniu kategorii: {e}")


    def init_map(self):
            """Generuje startową mapę folium i wstrzykuje ją do widoku PyQt"""
            # location=[0,0] to środek globu, zoom_start=2 pokazuje ładnie cały świat
            m = folium.Map(location=[0, 0], zoom_start=2, tiles="CartoDB positron", world_copy_jump=True)
            
            # Przykładowa pinezka, żebyś widział, jak to działa
            folium.Marker(
                location=[37.77, -122.42],
                popup="San Francisco - Tu coś się dzieje!",
                icon=folium.Icon(color="red", icon="info-sign")
            ).add_to(m)

            # Zamiana mapy Pythona na kod HTML i przekazanie jej bez zapisywania pliku na dysku
            data = io.BytesIO()
            m.save(data, close_file=False)
            html_content = data.getvalue().decode()
            self.web_view.setHtml(html_content)


    def perform_search(self):
        """Zbiera dane z UI i wywołuje funkcję search_events"""
        status_val = self.status_combo.currentText()
        if status_val == "Wszystkie": status_val = None
            
        date_from_val = self.date_from.date().toString("yyyy-MM-dd")
        date_to_val = self.date_to.date().toString("yyyy-MM-dd")
        limit_val = self.limit_spin.value()
        
        # Listy kategorii
        sel_white = self.category_list.selectedItems()
        white_list_val = [item.text() for item in sel_white] if sel_white else None
        
        sel_black = self.black_list_widget.selectedItems()
        black_list_val = [item.text() for item in sel_black] if sel_black else None

        # Sortowanie (Mapowanie z polskiego UI na angielske zapytanie SQL)
        sort_val = "oldest" if self.sort_combo.currentText() == "Najstarsze" else "recent"

        # BBox (Współrzędne) - sprawdzamy czy użytkownik zaznaczył checkbox
        if self.enable_bbox_cb.isChecked():
            min_lon_val = self.min_lon.value()
            max_lon_val = self.max_lon.value()
            min_lat_val = self.min_lat.value()
            max_lat_val = self.max_lat.value()
        else:
            min_lon_val = max_lon_val = min_lat_val = max_lat_val = None

        print("Szukam zdarzeń...")
        try:
            results = search_events(
                db_path=self.db_path, status=status_val, date_from=date_from_val,
                date_to=date_to_val, limit=limit_val, sort_by=sort_val,
                white_list=white_list_val, black_list=black_list_val,
                min_lon=min_lon_val, max_lon=max_lon_val, 
                min_lat=min_lat_val, max_lat=max_lat_val
            )
            print(f"Znaleziono {len(results)} zdarzeń z podanymi filtrami!")
            self.update_map(results)
            
        except ValueError as e:
            # Przechwytujemy błąd kolegi (gdy ta sama kategoria jest na obu listach)
            print(f"Błąd filtrów: {e}")


    def update_map(self, events):
        """Rysuje mapę od nowa na podstawie wyników z bazy danych"""
        m = folium.Map(location=[0, 0], zoom_start=2, tiles="CartoDB positron", world_copy_jump=True)
        
        for event in events:
            # Struktura krotki wg SQL Twojego kolegi: 
            # 0:id, 1:title, 2:status, 3:created_at, 4:category_name, 5:lon, 6:lat
            title = event[1]
            cat_name = event[4]
            lon = event[5]
            lat = event[6]
            
            # Zdarzenia z NASA czasem nie mają dokładnych współrzędnych, więc zabezpieczamy się:
            if lat is not None and lon is not None:
                folium.Marker(
                    location=[lat, lon],
                    popup=f"<b>{title}</b><br>Kategoria: {cat_name}",
                    icon=folium.Icon(color="red", icon="info-sign")
                ).add_to(m)

        # Wstrzyknięcie zaktualizowanej mapy do widoku
        data = io.BytesIO()
        m.save(data, close_file=False)
        self.web_view.setHtml(data.getvalue().decode())


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = EonetUI()
    window.show()
    sys.exit(app.exec())        