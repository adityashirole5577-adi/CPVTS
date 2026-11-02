"""SQLite persistence. Tables are created automatically on first launch."""

import os
import sqlite3
from typing import List, Optional

from models import (
    FOUR_WHEELER_SLOT_IDS,
    STATUS_AVAILABLE,
    TWO_WHEELER_SLOT_IDS,
    VEHICLE_FOUR,
    VEHICLE_TWO,
    ZONE_FOUR,
    ZONE_TWO,
    ParkingSlot,
    ParkingTransaction,
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_DIR = os.path.join(BASE_DIR, "database")
DB_PATH = os.path.join(DB_DIR, "parking.db")


class DatabaseError(Exception):
    """Raised when a database operation fails."""


def get_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    path = db_path or DB_PATH
    os.makedirs(os.path.dirname(path), exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def initialize_database(db_path: Optional[str] = None) -> None:
    """Create tables and seed 15 available slots if they do not already exist."""
    conn = get_connection(db_path)
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS PARKING_SLOTS (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                slot_id TEXT UNIQUE NOT NULL,
                zone TEXT NOT NULL,
                vehicle_type TEXT NOT NULL,
                status TEXT NOT NULL,
                vehicle_number TEXT,
                entry_time INTEGER,
                owner_category TEXT,
                is_reserved INTEGER DEFAULT 0
            )
            """
        )
        try:
            conn.execute("ALTER TABLE PARKING_SLOTS ADD COLUMN is_reserved INTEGER DEFAULT 0")
        except sqlite3.OperationalError:
            pass

        conn.execute("UPDATE PARKING_SLOTS SET is_reserved = 1 WHERE status = 'Reserved'")
        conn.commit()
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS PARKING_TRANSACTIONS (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                vehicle_number TEXT NOT NULL,
                vehicle_type TEXT NOT NULL,
                owner_category TEXT NOT NULL,
                slot_id TEXT NOT NULL,
                entry_time INTEGER NOT NULL,
                exit_time INTEGER,
                duration INTEGER,
                fee INTEGER,
                parking_date TEXT NOT NULL,
                status TEXT NOT NULL
            )
            """
        )

        existing = conn.execute("SELECT COUNT(*) AS c FROM PARKING_SLOTS").fetchone()["c"]
        if existing == 0:
            rows = []
            for slot_id in TWO_WHEELER_SLOT_IDS:
                rows.append((slot_id, ZONE_TWO, VEHICLE_TWO, STATUS_AVAILABLE, None, None, None, 0))
            for slot_id in FOUR_WHEELER_SLOT_IDS:
                rows.append((slot_id, ZONE_FOUR, VEHICLE_FOUR, STATUS_AVAILABLE, None, None, None, 0))
            conn.executemany(
                """
                INSERT INTO PARKING_SLOTS
                    (slot_id, zone, vehicle_type, status, vehicle_number, entry_time, owner_category, is_reserved)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )
        else:
            # Ensure every required slot exists without wiping live occupancy.
            for slot_id in TWO_WHEELER_SLOT_IDS:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO PARKING_SLOTS
                        (slot_id, zone, vehicle_type, status, vehicle_number, entry_time, owner_category)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (slot_id, ZONE_TWO, VEHICLE_TWO, STATUS_AVAILABLE, None, None, None),
                )
            for slot_id in FOUR_WHEELER_SLOT_IDS:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO PARKING_SLOTS
                        (slot_id, zone, vehicle_type, status, vehicle_number, entry_time, owner_category)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (slot_id, ZONE_FOUR, VEHICLE_FOUR, STATUS_AVAILABLE, None, None, None),
                )
        conn.commit()
    except sqlite3.Error as exc:
        conn.rollback()
        raise DatabaseError("Could not initialize the parking database.") from exc
    finally:
        conn.close()


def _row_to_slot(row: sqlite3.Row) -> ParkingSlot:
    has_is_reserved = "is_reserved" in row.keys()
    is_res = bool(row["is_reserved"]) if has_is_reserved else (row["status"] == "Reserved")
    return ParkingSlot(
        db_id=row["id"],
        slot_id=row["slot_id"],
        zone=row["zone"],
        vehicle_type=row["vehicle_type"],
        status=row["status"],
        vehicle_number=row["vehicle_number"],
        entry_time=row["entry_time"],
        owner_category=row["owner_category"],
        is_reserved=is_res,
    )


def _row_to_transaction(row: sqlite3.Row) -> ParkingTransaction:
    return ParkingTransaction(
        db_id=row["id"],
        vehicle_number=row["vehicle_number"],
        vehicle_type=row["vehicle_type"],
        owner_category=row["owner_category"],
        slot_id=row["slot_id"],
        entry_time=row["entry_time"],
        exit_time=row["exit_time"],
        duration=row["duration"],
        fee=row["fee"],
        parking_date=row["parking_date"],
        status=row["status"],
    )


def load_slots(db_path: Optional[str] = None) -> List[ParkingSlot]:
    conn = get_connection(db_path)
    try:
        rows = conn.execute(
            """
            SELECT * FROM PARKING_SLOTS
            ORDER BY CASE WHEN slot_id LIKE 'T-%' THEN 0 ELSE 1 END, slot_id
            """
        ).fetchall()
        return [_row_to_slot(r) for r in rows]
    except sqlite3.Error as exc:
        raise DatabaseError("Could not load parking slots.") from exc
    finally:
        conn.close()


def save_slot(slot: ParkingSlot, db_path: Optional[str] = None) -> None:
    conn = get_connection(db_path)
    try:
        cols = [c["name"] for c in conn.execute("PRAGMA table_info(PARKING_SLOTS)").fetchall()]
        if "is_reserved" in cols:
            conn.execute(
                """
                UPDATE PARKING_SLOTS
                SET status = ?, vehicle_number = ?, entry_time = ?, owner_category = ?, is_reserved = ?
                WHERE slot_id = ?
                """,
                (
                    slot.status,
                    slot.vehicle_number,
                    slot.entry_time,
                    slot.owner_category,
                    1 if slot.is_reserved() else 0,
                    slot.slot_id,
                ),
            )
        else:
            conn.execute(
                """
                UPDATE PARKING_SLOTS
                SET status = ?, vehicle_number = ?, entry_time = ?, owner_category = ?
                WHERE slot_id = ?
                """,
                (slot.status, slot.vehicle_number, slot.entry_time, slot.owner_category, slot.slot_id),
            )
        conn.commit()
    except sqlite3.Error as exc:
        conn.rollback()
        raise DatabaseError("Could not update parking slot.") from exc
    finally:
        conn.close()


def insert_transaction(txn: ParkingTransaction, db_path: Optional[str] = None) -> int:
    conn = get_connection(db_path)
    try:
        cursor = conn.execute(
            """
            INSERT INTO PARKING_TRANSACTIONS
                (vehicle_number, vehicle_type, owner_category, slot_id,
                 entry_time, exit_time, duration, fee, parking_date, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                txn.vehicle_number,
                txn.vehicle_type,
                txn.owner_category,
                txn.slot_id,
                txn.entry_time,
                txn.exit_time,
                txn.duration,
                txn.fee,
                txn.parking_date,
                txn.status,
            ),
        )
        conn.commit()
        return int(cursor.lastrowid)
    except sqlite3.Error as exc:
        conn.rollback()
        raise DatabaseError("Could not save parking transaction.") from exc
    finally:
        conn.close()


def update_transaction(txn: ParkingTransaction, db_path: Optional[str] = None) -> None:
    conn = get_connection(db_path)
    try:
        conn.execute(
            """
            UPDATE PARKING_TRANSACTIONS
            SET exit_time = ?, duration = ?, fee = ?, status = ?
            WHERE id = ?
            """,
            (txn.exit_time, txn.duration, txn.fee, txn.status, txn.db_id),
        )
        conn.commit()
    except sqlite3.Error as exc:
        conn.rollback()
        raise DatabaseError("Could not update parking transaction.") from exc
    finally:
        conn.close()


def get_transaction(transaction_id: int, db_path: Optional[str] = None) -> Optional[ParkingTransaction]:
    conn = get_connection(db_path)
    try:
        row = conn.execute(
            "SELECT * FROM PARKING_TRANSACTIONS WHERE id = ?",
            (transaction_id,),
        ).fetchone()
        return _row_to_transaction(row) if row else None
    except sqlite3.Error as exc:
        raise DatabaseError("Could not load parking receipt.") from exc
    finally:
        conn.close()


def find_active_transaction(vehicle_number: str, slot_id: str, db_path: Optional[str] = None) -> Optional[ParkingTransaction]:
    conn = get_connection(db_path)
    try:
        row = conn.execute(
            """
            SELECT * FROM PARKING_TRANSACTIONS
            WHERE vehicle_number = ? AND slot_id = ? AND status = 'ACTIVE'
            ORDER BY id DESC
            LIMIT 1
            """,
            (vehicle_number, slot_id),
        ).fetchone()
        return _row_to_transaction(row) if row else None
    except sqlite3.Error as exc:
        raise DatabaseError("Could not look up active parking record.") from exc
    finally:
        conn.close()


def list_recent_transactions(limit: int = 20, db_path: Optional[str] = None) -> List[ParkingTransaction]:
    conn = get_connection(db_path)
    try:
        rows = conn.execute(
            """
            SELECT * FROM PARKING_TRANSACTIONS
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [_row_to_transaction(r) for r in rows]
    except sqlite3.Error as exc:
        raise DatabaseError("Could not load recent transactions.") from exc
    finally:
        conn.close()


def daily_entry_count(parking_date: str, db_path: Optional[str] = None) -> int:
    conn = get_connection(db_path)
    try:
        row = conn.execute(
            """
            SELECT COUNT(*) AS c FROM PARKING_TRANSACTIONS
            WHERE parking_date = ?
            """,
            (parking_date,),
        ).fetchone()
        return int(row["c"])
    except sqlite3.Error as exc:
        raise DatabaseError("Could not calculate daily vehicle count.") from exc
    finally:
        conn.close()


def daily_fees_collected(parking_date: str, db_path: Optional[str] = None) -> int:
    conn = get_connection(db_path)
    try:
        row = conn.execute(
            """
            SELECT COALESCE(SUM(fee), 0) AS total FROM PARKING_TRANSACTIONS
            WHERE parking_date = ? AND status = 'COMPLETED'
            """,
            (parking_date,),
        ).fetchone()
        return int(row["total"])
    except sqlite3.Error as exc:
        raise DatabaseError("Could not calculate daily fees.") from exc
    finally:
        conn.close()
