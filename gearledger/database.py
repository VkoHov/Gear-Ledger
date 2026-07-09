# -*- coding: utf-8 -*-
"""
SQLite database backend for concurrent multi-device access.
"""
import sqlite3
import threading
import datetime
from typing import List, Dict, Any, Optional
from pathlib import Path


class Database:
    """Thread-safe SQLite database for results storage."""

    def __init__(self, db_path: str = None):
        """Initialize database connection."""
        if db_path is None:
            # Default to user's data directory
            data_dir = Path.home() / ".gearledger" / "data"
            data_dir.mkdir(parents=True, exist_ok=True)
            db_path = str(data_dir / "gearledger.db")

        self.db_path = db_path
        self._local = threading.local()
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        """Get thread-local database connection."""
        if not hasattr(self._local, "connection") or self._local.connection is None:
            self._local.connection = sqlite3.connect(
                self.db_path,
                check_same_thread=False,
                timeout=30.0,
            )
            # Enable WAL mode for better concurrency
            self._local.connection.execute("PRAGMA journal_mode=WAL")
            self._local.connection.execute("PRAGMA busy_timeout=30000")
            self._local.connection.row_factory = sqlite3.Row
        return self._local.connection

    def _init_db(self):
        """Initialize database schema."""
        conn = self._get_connection()
        cursor = conn.cursor()

        # Create results table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                artikul TEXT NOT NULL,
                client TEXT NOT NULL,
                quantity INTEGER DEFAULT 1,
                weight REAL DEFAULT 0,
                last_updated TEXT,
                brand TEXT DEFAULT '',
                description TEXT DEFAULT '',
                sale_price REAL DEFAULT 0,
                total_price REAL DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(artikul, client)
            )
        """
        )

        # Create index for faster lookups
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_artikul_client 
            ON results(artikul, client)
        """
        )

        conn.commit()

    def add_or_update_result(
        self,
        artikul: str,
        client: str,
        quantity: int = 1,
        weight: float = 0,
        brand: str = "",
        description: str = "",
        sale_price: float = 0,
    ) -> Dict[str, Any]:
        """
        Add a new result or update existing one.
        If item exists for client, increment quantity (not weight).
        """
        print(f"[DATABASE] add_or_update_result called:")
        print(f"[DATABASE]   artikul={artikul}, client={client}")
        print(f"[DATABASE]   quantity={quantity}, weight={weight}, price={sale_price}")

        conn = self._get_connection()
        cursor = conn.cursor()
        now = datetime.datetime.now().isoformat()

        # Normalize artikul for matching
        artikul_norm = self._normalize(artikul)
        print(f"[DATABASE]   normalized artikul: {artikul_norm}")

        # Check if exists
        cursor.execute(
            """
            SELECT id, quantity, weight, sale_price 
            FROM results 
            WHERE REPLACE(REPLACE(REPLACE(UPPER(artikul), ' ', ''), '-', ''), '.', '') = ?
            AND UPPER(client) = UPPER(?)
            """,
            (artikul_norm, client),
        )
        existing = cursor.fetchone()
        print(f"[DATABASE]   existing record: {dict(existing) if existing else None}")

        if existing:
            # Update existing - increment quantity only, keep weight
            new_quantity = existing["quantity"] + quantity
            # Use new price if provided, else keep existing
            final_price = sale_price if sale_price > 0 else existing["sale_price"]
            total = final_price * new_quantity
            print(
                f"[DATABASE]   UPDATING: new_quantity={new_quantity}, price={final_price}"
            )

            cursor.execute(
                """
                UPDATE results 
                SET quantity = ?, 
                    last_updated = ?,
                    sale_price = ?,
                    total_price = ?,
                    brand = COALESCE(NULLIF(?, ''), brand),
                    description = COALESCE(NULLIF(?, ''), description)
                WHERE id = ?
                """,
                (
                    new_quantity,
                    now,
                    final_price,
                    total,
                    brand,
                    description,
                    existing["id"],
                ),
            )
            conn.commit()
            print(f"[DATABASE]   UPDATE committed, id={existing['id']}")
            return {"ok": True, "action": "updated", "id": existing["id"]}
        else:
            # Insert new
            total = sale_price * quantity
            print(f"[DATABASE]   INSERTING new record: total={total}")
            cursor.execute(
                """
                INSERT INTO results 
                (artikul, client, quantity, weight, last_updated, brand, description, sale_price, total_price)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    artikul,
                    client,
                    quantity,
                    weight,
                    now,
                    brand,
                    description,
                    sale_price,
                    total,
                ),
            )
            conn.commit()
            print(f"[DATABASE]   INSERT committed, id={cursor.lastrowid}")
            return {"ok": True, "action": "inserted", "id": cursor.lastrowid}

    def get_all_results(self, client: str = None) -> List[Dict[str, Any]]:
        """Get all results, optionally filtered by client."""
        conn = self._get_connection()
        cursor = conn.cursor()

        if client:
            cursor.execute(
                """
                SELECT * FROM results 
                WHERE UPPER(client) = UPPER(?)
                ORDER BY last_updated DESC
                """,
                (client,),
            )
        else:
            cursor.execute("SELECT * FROM results ORDER BY last_updated DESC")

        rows = cursor.fetchall()
        return [dict(row) for row in rows]

    def get_result_by_id(self, result_id: int) -> Optional[Dict[str, Any]]:
        """Get a single result by ID."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM results WHERE id = ?", (result_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

    def update_result(self, result_id: int, **kwargs) -> bool:
        """Update specific fields of a result."""
        conn = self._get_connection()
        cursor = conn.cursor()

        allowed_fields = [
            "artikul",
            "client",
            "quantity",
            "weight",
            "brand",
            "description",
            "sale_price",
            "total_price",
        ]

        updates = []
        values = []
        for field, value in kwargs.items():
            if field in allowed_fields:
                updates.append(f"{field} = ?")
                values.append(value)

        if not updates:
            return False

        updates.append("last_updated = ?")
        values.append(datetime.datetime.now().isoformat())
        values.append(result_id)

        cursor.execute(
            f"UPDATE results SET {', '.join(updates)} WHERE id = ?",
            values,
        )
        conn.commit()
        return cursor.rowcount > 0

    def delete_result(self, result_id: int) -> bool:
        """Delete a result by ID."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM results WHERE id = ?", (result_id,))
        conn.commit()
        return cursor.rowcount > 0

    def delete_result_by_key(self, artikul: str, client: str) -> int:
        """Delete the result row matching (artikul, client). Returns rows deleted."""
        conn = self._get_connection()
        cursor = conn.cursor()
        artikul_norm = self._normalize(artikul)
        cursor.execute(
            """
            DELETE FROM results
            WHERE REPLACE(REPLACE(REPLACE(UPPER(artikul), ' ', ''), '-', ''), '.', '') = ?
            AND UPPER(client) = UPPER(?)
            """,
            (artikul_norm, client),
        )
        conn.commit()
        return cursor.rowcount

    def update_result_quantity_by_key(self, artikul: str, client: str, new_quantity: int) -> bool:
        """Set the recorded quantity for (artikul, client), recomputing
        total_price from the existing per-unit sale_price. Returns True if a
        row was updated."""
        conn = self._get_connection()
        cursor = conn.cursor()
        artikul_norm = self._normalize(artikul)
        cursor.execute(
            """
            SELECT id, sale_price FROM results
            WHERE REPLACE(REPLACE(REPLACE(UPPER(artikul), ' ', ''), '-', ''), '.', '') = ?
            AND UPPER(client) = UPPER(?)
            """,
            (artikul_norm, client),
        )
        row = cursor.fetchone()
        if not row:
            return False
        total = (row["sale_price"] or 0) * new_quantity
        cursor.execute(
            "UPDATE results SET quantity = ?, total_price = ?, last_updated = ? WHERE id = ?",
            (new_quantity, total, datetime.datetime.now().isoformat(), row["id"]),
        )
        conn.commit()
        return cursor.rowcount > 0

    def clear_all_results(self, client: str = None) -> int:
        """Clear all results, optionally for a specific client."""
        conn = self._get_connection()
        cursor = conn.cursor()

        if client:
            cursor.execute(
                "DELETE FROM results WHERE UPPER(client) = UPPER(?)",
                (client,),
            )
        else:
            cursor.execute("DELETE FROM results")

        conn.commit()
        return cursor.rowcount

    def archive_results_before_clear(self, versions_dir: str, client: str = None) -> int:
        """Export current results to an Excel version file, then clear them.

        Used by server/client-mode Reset so a database wipe gets the same
        version-history safety net as the standalone Excel file does.
        Returns the number of rows cleared.
        """
        rows = self.get_all_results(client)
        if rows:
            from .result_ledger import rows_to_dataframe, unique_version_path

            df = rows_to_dataframe(rows)
            df.to_excel(unique_version_path(versions_dir), index=False)
        return self.clear_all_results(client)

    def get_clients(self) -> List[str]:
        """Get list of unique clients."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT client FROM results ORDER BY client")
        return [row[0] for row in cursor.fetchall()]

    def export_to_dict(self) -> Dict[str, List[Dict[str, Any]]]:
        """Export all data grouped by client for Excel export."""
        results = self.get_all_results()
        by_client = {}
        for r in results:
            client = r["client"]
            if client not in by_client:
                by_client[client] = []
            by_client[client].append(r)
        return by_client

    def _normalize(self, s: str) -> str:
        """Normalize string for matching.

        Canonicalize non-breaking spaces and em/en-dashes first — a code
        scanned from a label often comes back with these instead of plain
        ASCII, so it wouldn't otherwise match a manually-typed query that
        looks identical but isn't byte-identical.
        """
        s = str(s or "").replace("\xa0", " ").replace("—", "-").replace("–", "-")
        return s.replace(" ", "").replace("-", "").replace(".", "").upper()

    def close(self):
        """Close database connection."""
        if hasattr(self._local, "connection") and self._local.connection:
            self._local.connection.close()
            self._local.connection = None


# Global database instance
_db_instance: Optional[Database] = None


def get_database(db_path: str = None) -> Database:
    """Get or create global database instance."""
    global _db_instance
    if _db_instance is None:
        _db_instance = Database(db_path)
    return _db_instance


def reset_database():
    """Reset database instance (for testing or switching modes)."""
    global _db_instance
    if _db_instance:
        _db_instance.close()
    _db_instance = None
