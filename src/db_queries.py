import sqlite3
from typing import Any

def search_events(
    db_path: str,
    status: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int = 100,
    sort_by: str = "recent",
    white_list: list[str] | None = None,      # Zastępuje category_title
    black_list: list[str] | None = None,      # Czarna lista
    min_lon: float | None = None,             # Filtry współrzędnych (BBox)
    max_lon: float | None = None,
    min_lat: float | None = None,
    max_lat: float | None = None
) -> list[tuple]:
    
    # 1. Walidacja konfliktów między listami
    if white_list and black_list:
        conflicts = set(white_list).intersection(set(black_list))
        if conflicts:
            raise ValueError(f"Błąd logiczny: Kategorie {conflicts} znajdują się jednocześnie na Białej i Czarnej liście!")

    # 2. Baza zapytania SQL
    query = """
        SELECT DISTINCT 
            e.id, 
            e.title, 
            e.status, 
            e.created_at, 
            c.title AS category_name,
            eg.longitude,
            eg.latitude
        FROM events e
        LEFT JOIN event_categories ec ON e.id = ec.event_id
        LEFT JOIN categories c ON ec.category_id = c.id
        LEFT JOIN event_geometries eg ON e.id = eg.event_id
        WHERE 1=1
    """
    
    params = []

    # 3. Dynamiczne warunki WHERE (Status i Daty)
    if status:
        query += " AND e.status = ?"
        params.append(status)

    if date_from:
        query += " AND date(e.created_at) >= date(?)"
        params.append(date_from)

    if date_to:
        query += " AND date(e.created_at) <= date(?)"
        params.append(date_to)
        
    # 4. Logika Białej i Czarnej listy (White list ma priorytet)
    if white_list:
        placeholders = ", ".join(["?"] * len(white_list))
        query += f" AND c.title IN ({placeholders})"
        params.extend(white_list)
    elif black_list:
        placeholders = ", ".join(["?"] * len(black_list))
        query += f" AND c.title NOT IN ({placeholders})"
        params.extend(black_list)

    # 5. Filtrowanie obszaru (Współrzędne geograficzne)
    if min_lon is not None:
        query += " AND eg.longitude >= ?"
        params.append(min_lon)
    if max_lon is not None:
        query += " AND eg.longitude <= ?"
        params.append(max_lon)
    if min_lat is not None:
        query += " AND eg.latitude >= ?"
        params.append(min_lat)
    if max_lat is not None:
        query += " AND eg.latitude <= ?"
        params.append(max_lat)

    # 6. Sortowanie
    match sort_by.lower():
        case "oldest":
            query += " ORDER BY e.created_at ASC"
        case "recent" | _:
            query += " ORDER BY e.created_at DESC"

    # 7. Limit
    query += " LIMIT ?"
    params.append(limit)

    # 8. Wykonanie zapytania
    with sqlite3.connect(db_path) as conn:
        cur = conn.cursor()
        cur.execute(query, params)
        results = cur.fetchall()
        
    return results