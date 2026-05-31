import sqlite3
from typing import Any

def search_events(
    db_path: str,
    category_title: str | None = None,
    status: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int = 100,
    sort_by: str = "recent"
) -> list[tuple]:
    
    # 1. Baza zapytania
    query = """
        SELECT DISTINCT e.id, e.title, e.status, e.created_at, c.title AS category_name
        FROM events e
        LEFT JOIN event_categories ec ON e.id = ec.event_id
        LEFT JOIN categories c ON ec.category_id = c.id
        WHERE 1=1
    """
    
    params = []

    # 2. Dynamiczne warunki WHERE
    if category_title:
        query += " AND c.title = ?"
        params.append(category_title)

    if status:
        query += " AND e.status = ?"
        params.append(status)

    if date_from:
        query += " AND date(e.created_at) >= date(?)"
        params.append(date_from)

    if date_to:
        query += " AND date(e.created_at) <= date(?)"
        params.append(date_to)
        
    # 3. PYTHON SWITCH-CASE (match-case): Bezpieczne doklejanie sortowania
    match sort_by.lower():
        case "alphabetical":
            # Sortowanie standardowe od A do Z po tytule
            query += " ORDER BY e.title ASC"
            
        case "location":
            # Ciekawy trik: ponieważ w danych od NASA lokalizacja (np. 'Blaine, Idaho') 
            # jest na końcu tytułu po przecinku, sortujemy od końca. 
            # Działa to świetnie dla amerykańskich formatów 'Nazwa, Stan'.
            query += " ORDER BY SUBSTR(e.title, INSTR(e.title, ', ') + 2) ASC"
            
        case "recent" | _:
            # Domyślne sortowanie (najnowsze zdarzenia na górze)
            # Znak | działa jak "lub", a _ to opcja domyślna (fallback)
            query += " ORDER BY e.created_at DESC"

    # 4. Limit na samym końcu
    query += " LIMIT ?"
    params.append(limit)

    # 5. Wykonanie zapytania
    with sqlite3.connect(db_path) as conn:
        cur = conn.cursor()
        cur.execute(query, params)
        results = cur.fetchall()
        
    return results


db = "data/eonet.db"

wyniki_lokalizacja = search_events(db, sort_by="location", limit=10)

wyniki = search_events(db, limit=10)

print("\n--- SORTOWANIE DOMYŚLNE (Najnowsze) ---\n")
for w in wyniki:
    print(w)
print("\n--- SORTOWANIE PO LOKALIZACJI ---\n")
for w in wyniki_lokalizacja:
    print(w)