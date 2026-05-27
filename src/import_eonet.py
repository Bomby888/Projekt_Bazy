from __future__ import annotations

import json
import os
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv


load_dotenv()

API_URL = os.getenv("EONET_API_URL", "https://eonet.gsfc.nasa.gov/api/v2.1/events")
DB_PATH = os.getenv("DB_PATH", "data/eonet.db")
EONET_DAYS = int(os.getenv("EONET_DAYS", "30"))
EONET_LIMIT = int(os.getenv("EONET_LIMIT", "100"))
EONET_STATUS = os.getenv("EONET_STATUS", "open")
TIMEOUT_SECONDS = 30


@dataclass
class ImportStats:
    records_downloaded: int
    events_saved: int
    categories_saved: int
    sources_saved: int
    geometries_saved: int


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def create_schema(conn: sqlite3.Connection) -> None:
    conn.execute("PRAGMA foreign_keys = ON;")

    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            eonet_id TEXT NOT NULL UNIQUE,
            title TEXT NOT NULL,
            description TEXT,
            link TEXT,
            status TEXT,
            closed_at TEXT,
            raw_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            eonet_category_id INTEGER NOT NULL UNIQUE,
            title TEXT NOT NULL,
            description TEXT,
            link TEXT,
            layers_link TEXT,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS event_categories (
            event_id INTEGER NOT NULL,
            category_id INTEGER NOT NULL,
            PRIMARY KEY (event_id, category_id),
            FOREIGN KEY (event_id) REFERENCES events(id),
            FOREIGN KEY (category_id) REFERENCES categories(id)
        );

        CREATE TABLE IF NOT EXISTS sources (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            eonet_source_id TEXT NOT NULL UNIQUE,
            title TEXT,
            source_url TEXT,
            link TEXT,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS event_sources (
            event_id INTEGER NOT NULL,
            source_id INTEGER NOT NULL,
            source_event_url TEXT,
            PRIMARY KEY (event_id, source_id),
            FOREIGN KEY (event_id) REFERENCES events(id),
            FOREIGN KEY (source_id) REFERENCES sources(id)
        );

        CREATE TABLE IF NOT EXISTS event_geometries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id INTEGER NOT NULL,
            geometry_date TEXT,
            geometry_type TEXT,
            longitude REAL,
            latitude REAL,
            coordinates_json TEXT,
            created_at TEXT NOT NULL,
            UNIQUE (event_id, geometry_date, geometry_type, coordinates_json),
            FOREIGN KEY (event_id) REFERENCES events(id)
        );

        CREATE TABLE IF NOT EXISTS import_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            started_at TEXT NOT NULL,
            finished_at TEXT,
            endpoint_url TEXT NOT NULL,
            status TEXT NOT NULL,
            records_downloaded INTEGER DEFAULT 0,
            records_inserted INTEGER DEFAULT 0,
            records_updated INTEGER DEFAULT 0,
            error_message TEXT
        );
        """
    )


def fetch_events() -> list[dict[str, Any]]:
    params = {
        "days": EONET_DAYS,
        "limit": EONET_LIMIT,
        "status": EONET_STATUS,
    }

    response = requests.get(API_URL, params=params, timeout=TIMEOUT_SECONDS)
    response.raise_for_status()

    data = response.json()
    return data.get("events", [])


def save_event(conn: sqlite3.Connection, event: dict[str, Any], timestamp: str) -> int:
    closed_at = event.get("closed")
    status = "closed" if closed_at else "open"

    conn.execute(
        """
        INSERT INTO events (
            eonet_id, title, description, link, status, closed_at,
            raw_json, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(eonet_id) DO UPDATE SET
            title = excluded.title,
            description = excluded.description,
            link = excluded.link,
            status = excluded.status,
            closed_at = excluded.closed_at,
            raw_json = excluded.raw_json,
            updated_at = excluded.updated_at;
        """,
        (
            event["id"],
            event.get("title", "brak tytułu"),
            event.get("description"),
            event.get("link"),
            status,
            closed_at,
            json.dumps(event, ensure_ascii=False),
            timestamp,
            timestamp,
        ),
    )

    row = conn.execute(
        "SELECT id FROM events WHERE eonet_id = ?;",
        (event["id"],),
    ).fetchone()

    return int(row[0])


def save_category(conn: sqlite3.Connection, category: dict[str, Any], timestamp: str) -> int | None:
    if not category.get("id"):
        return None

    conn.execute(
        """
        INSERT INTO categories (
            eonet_category_id, title, description, link, layers_link, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(eonet_category_id) DO UPDATE SET
            title = excluded.title,
            description = excluded.description,
            link = excluded.link,
            layers_link = excluded.layers_link,
            updated_at = excluded.updated_at;
        """,
        (
            category["id"],
            category.get("title", "brak nazwy"),
            category.get("description"),
            category.get("link"),
            category.get("layers"),
            timestamp,
        ),
    )

    row = conn.execute(
        "SELECT id FROM categories WHERE eonet_category_id = ?;",
        (category["id"],),
    ).fetchone()

    return int(row[0])


def save_source(conn: sqlite3.Connection, source: dict[str, Any], timestamp: str) -> int | None:
    if not source.get("id"):
        return None

    conn.execute(
        """
        INSERT INTO sources (
            eonet_source_id, title, source_url, link, updated_at
        )
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(eonet_source_id) DO UPDATE SET
            title = excluded.title,
            source_url = excluded.source_url,
            link = excluded.link,
            updated_at = excluded.updated_at;
        """,
        (
            source["id"],
            source.get("title"),
            source.get("source") or source.get("url"),
            source.get("link"),
            timestamp,
        ),
    )

    row = conn.execute(
        "SELECT id FROM sources WHERE eonet_source_id = ?;",
        (source["id"],),
    ).fetchone()

    return int(row[0])


def save_geometry(
    conn: sqlite3.Connection,
    event_id: int,
    geometry: dict[str, Any],
    timestamp: str,
) -> int:
    coordinates = geometry.get("coordinates")
    geometry_type = geometry.get("type")

    longitude = None
    latitude = None

    if geometry_type == "Point" and isinstance(coordinates, list) and len(coordinates) >= 2:
        longitude = coordinates[0]
        latitude = coordinates[1]

    conn.execute(
        """
        INSERT OR IGNORE INTO event_geometries (
            event_id, geometry_date, geometry_type, longitude, latitude,
            coordinates_json, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?);
        """,
        (
            event_id,
            geometry.get("date"),
            geometry_type,
            longitude,
            latitude,
            json.dumps(coordinates, ensure_ascii=False),
            timestamp,
        ),
    )

    return 1


def write_import_log(
    conn: sqlite3.Connection,
    *,
    started_at: str,
    finished_at: str | None,
    endpoint_url: str,
    status: str,
    records_downloaded: int = 0,
    records_inserted: int = 0,
    records_updated: int = 0,
    error_message: str | None = None,
) -> None:
    conn.execute(
        """
        INSERT INTO import_log (
            started_at, finished_at, endpoint_url, status,
            records_downloaded, records_inserted, records_updated, error_message
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?);
        """,
        (
            started_at,
            finished_at,
            endpoint_url,
            status,
            records_downloaded,
            records_inserted,
            records_updated,
            error_message,
        ),
    )
    conn.commit()


def run_import() -> ImportStats:
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)

    started_at = utc_now_iso()

    with closing(sqlite3.connect(DB_PATH)) as conn:
        create_schema(conn)

        try:
            events = fetch_events()

            events_saved = 0
            categories_saved = 0
            sources_saved = 0
            geometries_saved = 0

            for event in events:
                event_db_id = save_event(conn, event, started_at)
                events_saved += 1

                for category in event.get("categories", []):
                    category_db_id = save_category(conn, category, started_at)
                    if category_db_id:
                        conn.execute(
                            """
                            INSERT OR IGNORE INTO event_categories (event_id, category_id)
                            VALUES (?, ?);
                            """,
                            (event_db_id, category_db_id),
                        )
                        categories_saved += 1

                for source in event.get("sources", []):
                    source_db_id = save_source(conn, source, started_at)
                    if source_db_id:
                        conn.execute(
                            """
                            INSERT OR IGNORE INTO event_sources (
                                event_id, source_id, source_event_url
                            )
                            VALUES (?, ?, ?);
                            """,
                            (
                                event_db_id,
                                source_db_id,
                                source.get("url") or source.get("source") or source.get("link"),
                            ),
                        )
                        sources_saved += 1

                for geometry in event.get("geometries", []):
                    geometries_saved += save_geometry(conn, event_db_id, geometry, started_at)

            conn.commit()

            finished_at = utc_now_iso()
            write_import_log(
                conn,
                started_at=started_at,
                finished_at=finished_at,
                endpoint_url=API_URL,
                status="success",
                records_downloaded=len(events),
                records_inserted=events_saved,
                records_updated=0,
            )

            return ImportStats(
                records_downloaded=len(events),
                events_saved=events_saved,
                categories_saved=categories_saved,
                sources_saved=sources_saved,
                geometries_saved=geometries_saved,
            )

        except Exception as error:
            finished_at = utc_now_iso()
            write_import_log(
                conn,
                started_at=started_at,
                finished_at=finished_at,
                endpoint_url=API_URL,
                status="error",
                error_message=str(error),
            )
            raise


if __name__ == "__main__":
    stats = run_import()

    print("Import zakończony.")
    print(f"Pobrano zdarzeń: {stats.records_downloaded}")
    print(f"Zapisano/odświeżono events: {stats.events_saved}")
    print(f"Zapisano/odświeżono categories: {stats.categories_saved}")
    print(f"Zapisano/odświeżono sources: {stats.sources_saved}")
    print(f"Zapisano geometries: {stats.geometries_saved}")
    print(f"Baza danych: {DB_PATH}")