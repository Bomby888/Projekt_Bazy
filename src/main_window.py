import sys
import io
import folium
from collections import Counter
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QComboBox, QDateEdit, QListWidget, QSpinBox,
    QPushButton, QAbstractItemView, QGroupBox, QDoubleSpinBox, QCheckBox, 
    QMessageBox, QTabWidget
)
import plotly.express as px 
from PySide6.QtCore import QDate
from PySide6.QtWebEngineWidgets import QWebEngineView
import sqlite3
from db_queries import search_events, get_status_distribution, get_top_categories, get_events_over_time

class EonetUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.db_path = "data/eonet.db"
        self.setWindowTitle("NASA EONET - Wyszukiwarka Zdarzeń")
        self.resize(1300, 850) # Startowy rozmiar okna

        # 1. GŁÓWNY WIDŻET I UKŁAD
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget) # Układ poziomy całego okna

        # --- LEWY PANEL (Filtry - teraz widoczne globalnie) ---
        filters_layout = QVBoxLayout()
        filters_group = QGroupBox("Filtry Wyszukiwania")
        filters_group.setFixedWidth(300)
        filters_group.setLayout(filters_layout)

        # Status
        filters_layout.addWidget(QLabel("Status zdarzenia:"))
        self.status_combo = QComboBox()
        self.status_combo.addItems(["Wszystkie", "open", "closed"])
        filters_layout.addWidget(self.status_combo)

        # Daty
        filters_layout.addWidget(QLabel("Data od:"))
        self.date_from = QDateEdit(calendarPopup=True)
        self.date_from.setDate(QDate.currentDate().addDays(-2000)) 
        filters_layout.addWidget(self.date_from)

        filters_layout.addWidget(QLabel("Data do:"))
        self.date_to = QDateEdit(calendarPopup=True)
        self.date_to.setDate(QDate.currentDate())
        filters_layout.addWidget(self.date_to)

        # Kategorie (Biała lista)
        filters_layout.addWidget(QLabel("Kategorie (Biała lista):"))
        self.category_list = QListWidget()
        self.category_list.setSelectionMode(QAbstractItemView.SelectionMode.MultiSelection)
        filters_layout.addWidget(self.category_list)

        # Limit
        filters_layout.addWidget(QLabel("Limit wyników:"))
        self.limit_spin = QSpinBox()
        self.limit_spin.setRange(1, 500)
        self.limit_spin.setValue(100)
        filters_layout.addWidget(self.limit_spin)

        # Czarna lista
        filters_layout.addWidget(QLabel("Kategorie (Czarna lista):"))
        self.black_list_widget = QListWidget()
        self.black_list_widget.setSelectionMode(QAbstractItemView.SelectionMode.MultiSelection)
        filters_layout.addWidget(self.black_list_widget)

        self.load_categories()

        # Sortowanie
        filters_layout.addWidget(QLabel("Sortowanie:"))
        self.sort_combo = QComboBox()
        self.sort_combo.addItems(["Najnowsze", "Najstarsze"])
        filters_layout.addWidget(self.sort_combo)

        # BBox
        bbox_group = QGroupBox("Ogranicz obszar wyszukiwania")
        bbox_layout = QVBoxLayout()
        self.enable_bbox_cb = QCheckBox("Aktywuj filtr współrzędnych")
        bbox_layout.addWidget(self.enable_bbox_cb)

        self.min_lon = QDoubleSpinBox(); self.min_lon.setRange(-180, 180); self.min_lon.setEnabled(False)
        self.max_lon = QDoubleSpinBox(); self.max_lon.setRange(-180, 180); self.max_lon.setEnabled(False)
        self.min_lat = QDoubleSpinBox(); self.min_lat.setRange(-90, 90); self.min_lat.setEnabled(False)
        self.max_lat = QDoubleSpinBox(); self.max_lat.setRange(-90, 90); self.max_lat.setEnabled(False)

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

        # Przycisk filtrów
        self.apply_btn = QPushButton("Zastosuj filtry")
        self.apply_btn.clicked.connect(self.apply_all_filters) # <--- NOWA FUNKCJA
        self.apply_btn.setStyleSheet("background-color: #2b5c8f; color: white; padding: 12px; font-weight: bold; font-size: 14px;")
        filters_layout.addWidget(self.apply_btn)
        filters_layout.addStretch()

        # --- PRAWY PANEL (ZAKŁADKI) ---
        self.tabs = QTabWidget()

        # Zakładka 1: Mapa
        self.tab_map = QWidget()
        map_layout = QVBoxLayout(self.tab_map)
        map_layout.setContentsMargins(0, 0, 0, 0) # Mapa na całą szerokość
        self.web_view = QWebEngineView()
        self.init_map()
        map_layout.addWidget(self.web_view)
        self.tabs.addTab(self.tab_map, "Mapa")

        # Zakładka 2: Dashboard
        self.tab_dashboard = QWidget()
        dash_layout = QVBoxLayout(self.tab_dashboard)
        
        pie_charts_layout = QHBoxLayout()
        self.chart_status_view = QWebEngineView()
        self.chart_categories_view = QWebEngineView()
        pie_charts_layout.addWidget(self.chart_status_view)
        pie_charts_layout.addWidget(self.chart_categories_view)
        
        self.chart_time_view = QWebEngineView()
        dash_layout.addLayout(pie_charts_layout)
        dash_layout.addWidget(self.chart_time_view)
        self.tabs.addTab(self.tab_dashboard, "Raporty i Analizy")

        # Złożenie całości w main_layout
        main_layout.addWidget(filters_group)
        main_layout.addWidget(self.tabs)

        self.statusBar().showMessage("Aplikacja gotowa do pracy.")


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
        bbox_coords = None # Zmienna do przekazania narysowania obszaru
        if self.enable_bbox_cb.isChecked():
            min_lon_val = self.min_lon.value()
            max_lon_val = self.max_lon.value()
            min_lat_val = self.min_lat.value()
            max_lat_val = self.max_lat.value()

            # Zapisujemy do krotki, żeby przekazać do rysowania
            bbox_coords = (min_lon_val, max_lon_val, min_lat_val, max_lat_val)
        else:
            min_lon_val = max_lon_val = min_lat_val = max_lat_val = None

        self.statusBar().showMessage("Szukam zdarzeń...")
        QApplication.processEvents() # Wymusza odświeżenie UI, żeby napis od razu się pojawił
        try:
            results = search_events(
                db_path=self.db_path, status=status_val, date_from=date_from_val,
                date_to=date_to_val, limit=limit_val, sort_by=sort_val,
                white_list=white_list_val, black_list=black_list_val,
                min_lon=min_lon_val, max_lon=max_lon_val, 
                min_lat=min_lat_val, max_lat=max_lat_val
            )            
            # ZMIANA: Przekazujemy bbox_coords do aktualizacji mapy
            self.update_map(results, bbox=bbox_coords)
            return results
        
        except Exception as e:
            # Komunikat o błędzie na pasku i w wyskakującym oknie
            self.statusBar().showMessage("Błąd wyszukiwania lub rysowania mapy!")
            QMessageBox.critical(self, "Błąd Systemu", f"Wystąpił nieoczekiwany błąd:\n{str(e)}")
            return None


    def update_map(self, events, bbox = None):
        """Rysuje mapę od nowa na podstawie wyników z bazy danych"""
        m = folium.Map(location=[0, 0], zoom_start=2, tiles="CartoDB positron", world_copy_jump=True)
        
        if bbox:
            min_lon, max_lon, min_lat, max_lat = bbox
            real_min_lat = min(min_lat, max_lat)
            real_max_lat = max(min_lat, max_lat)
            real_min_lon = min(min_lon, max_lon)
            real_max_lon = max(min_lon, max_lon)
            # Definiujemy rogi prostokąta (Folium wymaga formatu [lat, lon])
            if (real_max_lat > real_min_lat) and (real_max_lon > real_min_lon):
                bounds = [[real_min_lat, real_min_lon], [real_max_lat, real_max_lon]]
                
                folium.Rectangle(
                    bounds=bounds,
                    color="#0078A8",       # Kolor obramowania
                    weight=2,              # Grubość linii
                    fill=True,
                    fill_color="#0078A8",  # Kolor wypełnienia
                    fill_opacity=0.2       # Przezroczystość (20%)
                ).add_to(m)
                
                # Automatyczne dostosowanie kamery do narysowanego obszaru
                m.fit_bounds(bounds)
            else:
                self.statusBar().showMessage("Uwaga: Obszar współrzędnych jest zbyt mały, by go narysować!")
                QMessageBox.critical(self, "Błąd Współrzędnych", "Wystąpił błąd podczas rysowania")
                            
        for event in events:
            title = event[1]
            cat_name = event[4]
            lon = event[5]
            lat = event[6]
            
            if lat is not None and lon is not None:
                folium.Marker(
                    location=[float(lat), float(lon)],
                    popup=f"<b>{title}</b><br>Kategoria: {cat_name}",
                    icon=folium.Icon(color="red", icon="info-sign")
                ).add_to(m)

        # Wstrzyknięcie zaktualizowanej mapy do widoku
        data = io.BytesIO()
        m.save(data, close_file=False)
        self.web_view.setHtml(data.getvalue().decode())


    def generate_dashboard(self, events):
        """Generuje wykresy Plotly zliczając wartości bezpośrednio z przekazanej listy zdarzeń"""
        
        # Zabezpieczenie: Jeśli lista jest pusta, czyścimy wykresy
        if not events:
            self.chart_status_view.setHtml("<h2 style='text-align:center; font-family:sans-serif;'>Brak danych do wyświetlenia</h2>")
            self.chart_categories_view.setHtml("<h2 style='text-align:center; font-family:sans-serif;'>Brak danych do wyświetlenia</h2>")
            self.chart_time_view.setHtml("<h2 style='text-align:center; font-family:sans-serif;'>Brak danych do wyświetlenia</h2>")
            return

        try:
            # 1. Wykres: Status (e[2] to status)
            status_counts = Counter([e[2] for e in events if e[2]])
            if status_counts:
                labels = [s.capitalize() for s in status_counts.keys()]
                values = list(status_counts.values())
                fig_status = px.pie(names=labels, values=values, title="Status zdarzeń", color_discrete_sequence=['#ef553b', '#636efa'])
                fig_status.update_layout(title_y=0.9, margin=dict(t=80, b=20, l=20, r=20)) 
                self.chart_status_view.setHtml(fig_status.to_html(include_plotlyjs='cdn'))

            # 2. Wykres: Udział kategorii (e[4] to kategoria)
            cat_counts = Counter([e[4] for e in events if e[4]])
            if cat_counts:
                top_cats = cat_counts.most_common(10) # Bierzemy Top 10 zliczonych
                labels = [c[0] for c in top_cats]
                values = [c[1] for c in top_cats]
                fig_cat = px.pie(names=labels, values=values, hole=0.4)
                fig_cat.update_layout(
                    title={'text': "Rozkład Kategorii Zdarzeń", 'y':0.95, 'x':0.5, 'xanchor': 'center', 'yanchor': 'top'},
                    margin=dict(t=80, b=20, l=20, r=20)
                )
                self.chart_categories_view.setHtml(fig_cat.to_html(include_plotlyjs='cdn'))

            # 3. Wykres: Zdarzenia w czasie (e[3] to data z czasem, bierzemy samo YYYY-MM-DD, czyli [:10])
            date_counts = Counter([e[3][:10] for e in events if e[3]])
            if date_counts:
                sorted_dates = sorted(date_counts.items()) # Sortujemy chronologicznie
                x_months = [d[0] for d in sorted_dates]
                y_counts = [d[1] for d in sorted_dates]
                
                fig_time = px.scatter(
                    x=x_months, y=y_counts, 
                    title="Liczba zdarzeń w czasie (Dni)", 
                    labels={'x': 'Data', 'y': 'Liczba zdarzeń z nałożonym limitem'}
                )
                fig_time.update_traces(marker=dict(color="#0078A8", size=8))
                fig_time.update_layout(margin=dict(t=50, b=20, l=20, r=20))
                self.chart_time_view.setHtml(fig_time.to_html(include_plotlyjs='cdn'))

        except Exception as e:
            QMessageBox.critical(self, "Błąd generowania raportów", f"Wystąpił błąd przy budowaniu wykresów:\n{e}")


    def apply_all_filters(self):
        """Uruchamia odświeżanie mapy oraz dashboardu na podstawie filtrów"""
        self.statusBar().showMessage("Przetwarzanie danych, proszę czekać...")
        QApplication.processEvents()
        
        # Pobieramy pełne wyniki z funkcji wyszukującej (która od razu aktualizuje mapę)
        events = self.perform_search()

        # Generujemy wykresy bazując DOKŁADNIE na tych samych danych co mapa
        if events is not None:
            self.generate_dashboard(events)
            self.statusBar().showMessage(f"Poprawnie wygenerowano raporty i mapę dla {len(events)} zdarzeń.")
        else:
            self.statusBar().showMessage("Wystąpił błąd lub brak wyników.")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = EonetUI()
    window.show()
    sys.exit(app.exec())        