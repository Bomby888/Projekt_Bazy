
from db_queries import search_events

# --- Testy db_queries ---
db = "data/eonet.db"

print("\n--- TEST 1: TYLKO BURZE (White List) ---")
try:
    wyniki_white = search_events(db, white_list=["Severe Storms"], limit=10)
    for w in wyniki_white:
        print(w)
except Exception as e:
    print(e)

print("\n--- TEST 2: WSZYSTKO OPRÓCZ POŻARÓW i WULKANÓW (Black List) ---")
wyniki_black = search_events(db, black_list=["Wildfires","Volcanoes"], limit=10)
for w in wyniki_black:
    print(w)

print("\n--- TEST 3: WSPÓŁRZĘDNE (Szybki filtr na wybrany kwadrat geograficzny [-130, -60] x [20, 50]) ---")
# Przykład: szukamy zdarzeń w okolicach Ameryki Północnej / Europy
wyniki_obszar = search_events(db, min_lon=-130.0, max_lon=-60.0, min_lat=20.0, max_lat=50.0, limit=10)
for w in wyniki_obszar:
    print(w)