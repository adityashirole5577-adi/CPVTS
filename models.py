"""Core domain objects for Campus Parking & Vehicle Tracking System."""

from typing import Optional


STATUS_AVAILABLE = "Available"
STATUS_OCCUPIED = "Occupied"
STATUS_RESERVED = "Reserved"
STATUS_ACTIVE = "ACTIVE"
STATUS_COMPLETED = "COMPLETED"

VEHICLE_TWO = "Two-Wheeler"
VEHICLE_FOUR = "Four-Wheeler"

ZONE_TWO = "Two-Wheeler Zone"
ZONE_FOUR = "Four-Wheeler Zone"

CATEGORY_VIP = "VIP/Emergency"
CATEGORIES = ("Staff", "Student", "Visitor", CATEGORY_VIP)
VEHICLE_TYPES = (VEHICLE_TWO, VEHICLE_FOUR)

TWO_WHEELER_SLOT_IDS = [f"T-{i:02d}" for i in range(1, 11)]
FOUR_WHEELER_SLOT_IDS = [f"F-{i:02d}" for i in range(1, 6)]
ALL_SLOT_IDS = TWO_WHEELER_SLOT_IDS + FOUR_WHEELER_SLOT_IDS


def format_hour(hour) -> str:
    """Format an integer hour (0-23) as HH:00."""
    return f"{int(hour):02d}:00"


def format_hour_ampm(hour) -> str:
    """Format an integer hour as HH:00 AM/PM (24-hour clock with meridian)."""
    hour = int(hour)
    meridian = "AM" if hour < 12 else "PM"
    return f"{hour:02d}:00 {meridian}"


class ParkingSlot:
    """One campus parking bay. A slot holds at most one active vehicle."""

    def __init__(
        self,
        slot_id: str,
        zone: str,
        vehicle_type: str,
        status: str = STATUS_AVAILABLE,
        vehicle_number: Optional[str] = None,
        entry_time: Optional[int] = None,
        owner_category: Optional[str] = None,
        db_id: Optional[int] = None,
        is_reserved: bool = False,
    ):
        self.db_id = db_id
        self.slot_id = slot_id
        self.zone = zone
        self.vehicle_type = vehicle_type
        self.status = status
        self.vehicle_number = vehicle_number
        self.entry_time = entry_time
        self.owner_category = owner_category
        self._is_reserved = bool(is_reserved or (status == STATUS_RESERVED))

    def is_available(self) -> bool:
        return self.status == STATUS_AVAILABLE and not self._is_reserved

    def is_reserved(self) -> bool:
        return self._is_reserved

    def reserve(self) -> None:
        self._is_reserved = True
        if self.status != STATUS_OCCUPIED:
            self.status = STATUS_RESERVED

    def unreserve(self) -> None:
        self._is_reserved = False
        if self.status != STATUS_OCCUPIED:
            self.status = STATUS_AVAILABLE

    def occupy(self, vehicle: "Vehicle") -> None:
        self.status = STATUS_OCCUPIED
        self.vehicle_number = vehicle.vehicle_number
        self.entry_time = vehicle.entry_time
        self.owner_category = vehicle.owner_category

    def vacate(self) -> None:
        self.vehicle_number = None
        self.entry_time = None
        self.owner_category = None
        if self.is_reserved():
            self.status = STATUS_RESERVED
        else:
            self.status = STATUS_AVAILABLE

    def to_dict(self) -> dict:
        return {
            "id": self.db_id,
            "slot_id": self.slot_id,
            "zone": self.zone,
            "vehicle_type": self.vehicle_type,
            "status": self.status,
            "is_reserved": self.is_reserved(),
            "vehicle_number": self.vehicle_number,
            "entry_time": self.entry_time,
            "entry_time_display": format_hour(self.entry_time) if self.entry_time is not None else None,
            "owner_category": self.owner_category,
        }


class Vehicle:
    """A vehicle presented at check-in."""

    def __init__(self, vehicle_number: str, vehicle_type: str, owner_category: str, entry_time: int):
        self.vehicle_number = vehicle_number
        self.vehicle_type = vehicle_type
        self.owner_category = owner_category
        self.entry_time = int(entry_time)

    def to_dict(self) -> dict:
        return {
            "vehicle_number": self.vehicle_number,
            "vehicle_type": self.vehicle_type,
            "owner_category": self.owner_category,
            "entry_time": self.entry_time,
            "entry_time_display": format_hour(self.entry_time),
        }


class ParkingTransaction:
    """Entry/exit record used for receipts, history, and fee collection."""

    def __init__(
        self,
        vehicle_number: str,
        vehicle_type: str,
        owner_category: str,
        slot_id: str,
        entry_time: int,
        exit_time: Optional[int] = None,
        duration: Optional[int] = None,
        fee: Optional[int] = None,
        parking_date: Optional[str] = None,
        status: str = STATUS_ACTIVE,
        db_id: Optional[int] = None,
        fee_lines: Optional[list] = None,
    ):
        self.db_id = db_id
        self.vehicle_number = vehicle_number
        self.vehicle_type = vehicle_type
        self.owner_category = owner_category
        self.slot_id = slot_id
        self.entry_time = entry_time
        self.exit_time = exit_time
        self.duration = duration
        self.fee = fee
        self.parking_date = parking_date
        self.status = status
        self.fee_lines = fee_lines or []

    def duration_label(self) -> str:
        if self.duration is None or self.exit_time is None:
            return "--"
        return f"{self.duration} Hours ({format_hour(self.entry_time)} to {format_hour(self.exit_time)})"

    def to_dict(self) -> dict:
        return {
            "id": self.db_id,
            "vehicle_number": self.vehicle_number,
            "vehicle_type": self.vehicle_type,
            "owner_category": self.owner_category,
            "slot_id": self.slot_id,
            "entry_time": self.entry_time,
            "entry_time_display": format_hour(self.entry_time) if self.entry_time is not None else None,
            "exit_time": self.exit_time,
            "exit_time_display": format_hour(self.exit_time) if self.exit_time is not None else None,
            "duration": self.duration,
            "duration_label": self.duration_label() if self.duration is not None else "--",
            "fee": self.fee,
            "parking_date": self.parking_date,
            "status": self.status,
            "fee_lines": self.fee_lines,
        }
