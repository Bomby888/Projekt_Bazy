# tests/test_import_eonet.py

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from import_eonet import (
    create_schema,
    save_event,
    save_category,
    save_source,
    save_geometry,
)


def test_create_schema_creates_required_tables():
    conn = sqlite3.connect(":memory:")
    create_schema(conn)

    tables = {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table';"
        )
    }

    assert "events" in tables
    assert "categories" in tables
    assert "sources" in tables
    assert "event_geometries" in tables
    assert "import_log" in tables


def test_save_event_inserts_event():
    conn = sqlite3.connect(":memory:")
    create_schema(conn)

    event = {
        "id": "EONET_001",
        "title": "Test wildfire",
        "description": "Example event",
        "link": "https://example.com",
        "closed": None,
    }

    event_id = save_event(conn, event, "2026-06-09T10:00:00+00:00")

    row = conn.execute(
        "SELECT eonet_id, title, status FROM events WHERE id = ?;",
        (event_id,),
    ).fetchone()

    assert row == ("EONET_001", "Test wildfire", "open")


def test_save_event_updates_existing_event():
    conn = sqlite3.connect(":memory:")
    create_schema(conn)

    event = {"id": "EONET_001", "title": "Old title"}
    save_event(conn, event, "2026-06-09T10:00:00+00:00")

    updated_event = {"id": "EONET_001", "title": "New title"}
    save_event(conn, updated_event, "2026-06-09T11:00:00+00:00")

    count = conn.execute("SELECT COUNT(*) FROM events;").fetchone()[0]
    title = conn.execute(
        "SELECT title FROM events WHERE eonet_id = 'EONET_001';"
    ).fetchone()[0]

    assert count == 1
    assert title == "New title"


def test_save_category_inserts_category():
    conn = sqlite3.connect(":memory:")
    create_schema(conn)

    category = {
        "id": 8,
        "title": "Wildfires",
        "description": "Fire events",
        "link": "https://example.com/category",
        "layers": "https://example.com/layers",
    }

    category_id = save_category(conn, category, "2026-06-09T10:00:00+00:00")

    row = conn.execute(
        "SELECT eonet_category_id, title FROM categories WHERE id = ?;",
        (category_id,),
    ).fetchone()

    assert row == (8, "Wildfires")


def test_save_source_inserts_source():
    conn = sqlite3.connect(":memory:")
    create_schema(conn)

    source = {
        "id": "NASA",
        "title": "NASA Source",
        "url": "https://example.com/source",
        "link": "https://example.com/link",
    }

    source_id = save_source(conn, source, "2026-06-09T10:00:00+00:00")

    row = conn.execute(
        "SELECT eonet_source_id, title FROM sources WHERE id = ?;",
        (source_id,),
    ).fetchone()

    assert row == ("NASA", "NASA Source")


def test_save_geometry_point_extracts_coordinates():
    conn = sqlite3.connect(":memory:")
    create_schema(conn)

    event_id = save_event(
        conn,
        {"id": "EONET_001", "title": "Test event"},
        "2026-06-09T10:00:00+00:00",
    )

    geometry = {
        "date": "2026-06-09T09:00:00Z",
        "type": "Point",
        "coordinates": [19.45, 51.75],
    }

    save_geometry(conn, event_id, geometry, "2026-06-09T10:00:00+00:00")

    row = conn.execute(
        """
        SELECT geometry_type, longitude, latitude
        FROM event_geometries
        WHERE event_id = ?;
        """,
        (event_id,),
    ).fetchone()

    assert row == ("Point", 19.45, 51.75)