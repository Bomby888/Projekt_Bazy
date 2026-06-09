import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from db_queries import (
    search_events,
    get_status_distribution,
    get_top_categories,
    get_events_over_time,
)


@pytest.fixture
def test_db(tmp_path):
    db_path = tmp_path / "test.db"

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    cur.executescript("""
        CREATE TABLE events (
            id INTEGER PRIMARY KEY,
            title TEXT,
            status TEXT
        );

        CREATE TABLE categories (
            id INTEGER PRIMARY KEY,
            title TEXT
        );

        CREATE TABLE event_categories (
            event_id INTEGER,
            category_id INTEGER
        );

        CREATE TABLE event_geometries (
            id INTEGER PRIMARY KEY,
            event_id INTEGER,
            geometry_date TEXT,
            longitude REAL,
            latitude REAL
        );
    """)

    cur.executemany(
        "INSERT INTO events VALUES (?, ?, ?);",
        [
            (1, "Wildfire in Canada", "open"),
            (2, "Storm in USA", "closed"),
            (3, "Volcano in Iceland", "open"),
        ],
    )

    cur.executemany(
        "INSERT INTO categories VALUES (?, ?);",
        [
            (1, "Wildfires"),
            (2, "Severe Storms"),
            (3, "Volcanoes"),
        ],
    )

    cur.executemany(
        "INSERT INTO event_categories VALUES (?, ?);",
        [
            (1, 1),
            (2, 2),
            (3, 3),
        ],
    )

    cur.executemany(
        "INSERT INTO event_geometries VALUES (?, ?, ?, ?, ?);",
        [
            (1, 1, "2026-06-01T10:00:00Z", -100.0, 40.0),
            (2, 2, "2026-06-03T10:00:00Z", -80.0, 35.0),
            (3, 3, "2026-06-05T10:00:00Z", 20.0, 60.0),
        ],
    )

    conn.commit()
    conn.close()

    return str(db_path)


def test_search_events_by_status(test_db):
    results = search_events(test_db, status="open")

    assert len(results) == 2
    assert all(row[2] == "open" for row in results)


def test_search_events_white_list(test_db):
    results = search_events(test_db, white_list=["Severe Storms"])

    assert len(results) == 1
    assert results[0][4] == "Severe Storms"


def test_search_events_black_list(test_db):
    results = search_events(test_db, black_list=["Wildfires", "Volcanoes"])

    assert len(results) == 1
    assert results[0][4] == "Severe Storms"


def test_search_events_white_and_black_list_conflict(test_db):
    with pytest.raises(ValueError):
        search_events(
            test_db,
            white_list=["Wildfires"],
            black_list=["Wildfires"],
        )


def test_search_events_bbox_filter(test_db):
    results = search_events(
        test_db,
        min_lon=-130,
        max_lon=-60,
        min_lat=20,
        max_lat=50,
    )

    assert len(results) == 2
    titles = [row[1] for row in results]
    assert "Wildfire in Canada" in titles
    assert "Storm in USA" in titles


def test_search_events_oldest_sorting(test_db):
    results = search_events(test_db, sort_by="oldest")

    assert results[0][1] == "Wildfire in Canada"
    assert results[-1][1] == "Volcano in Iceland"


def test_get_status_distribution(test_db):
    results = get_status_distribution(test_db)

    assert ("open", 2) in results
    assert ("closed", 1) in results


def test_get_top_categories(test_db):
    results = get_top_categories(test_db, limit=2)

    assert len(results) == 2
    assert results[0][1] == 1


def test_get_events_over_time(test_db):
    results = get_events_over_time(test_db)

    assert ("2026-06-01", 1) in results
    assert ("2026-06-03", 1) in results
    assert ("2026-06-05", 1) in results