"""Parking operations: allocation, search, checkout, dashboard stats."""

from datetime import date
from typing import List, Optional

from database import (
    DatabaseError,
    daily_entry_count,
    daily_fees_collected,
    find_active_transaction,
    get_transaction,
    initialize_database,
    insert_transaction,
    list_recent_transactions,
    load_slots,
    save_slot,
    update_transaction,
)
from models import (
    ALL_SLOT_IDS,
    CATEGORIES,
    CATEGORY_VIP,
    FOUR_WHEELER_SLOT_IDS,
    STATUS_ACTIVE,
    STATUS_AVAILABLE,
    STATUS_COMPLETED,
    STATUS_OCCUPIED,
    STATUS_RESERVED,
    TWO_WHEELER_SLOT_IDS,
    VEHICLE_FOUR,
    VEHICLE_TWO,
    VEHICLE_TYPES,
    ParkingSlot,
    ParkingTransaction,
    Vehicle,
    format_hour,
    format_hour_ampm,
)
from pricing import calculate_fee, fee_breakdown


class ParkingError(Exception):
    """User-facing parking business error."""


class ParkingManager:
    """
    Coordinates in-memory slot lists with SQLite persistence.

    Slot search, occupancy counts, and duplicate checks use Python lists
    and dictionaries. SQLite stores the same state across restarts.
    """

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path
        initialize_database(self.db_path)
        self.slots: List[ParkingSlot] = []
        self.reload()

    def reload(self) -> None:
        self.slots = load_slots(self.db_path)

    def _slots_by_id(self) -> dict:
        """Dictionary index for O(1) slot lookup by slot_id."""
        return {slot.slot_id: slot for slot in self.slots}

    def _zone_slot_ids(self, vehicle_type: str) -> List[str]:
        if vehicle_type == VEHICLE_TWO:
            return list(TWO_WHEELER_SLOT_IDS)
        if vehicle_type == VEHICLE_FOUR:
            return list(FOUR_WHEELER_SLOT_IDS)
        raise ParkingError("Vehicle type must be selected.")

    def find_first_available(self, vehicle_type: str) -> Optional[ParkingSlot]:
        """Walk the zone in slot-id order and return the first vacant bay."""
        index = self._slots_by_id()
        for slot_id in self._zone_slot_ids(vehicle_type):
            slot = index.get(slot_id)
            if slot is not None and slot.is_available():
                return slot
        return None

    def is_vehicle_parked(self, vehicle_number: str) -> bool:
        for slot in self.slots:
            if (
                slot.status == STATUS_OCCUPIED
                and slot.vehicle_number
                and slot.vehicle_number.upper() == vehicle_number.upper()
            ):
                return True
        return False

    def find_by_vehicle(self, vehicle_number: str) -> Optional[ParkingSlot]:
        target = vehicle_number.upper()
        for slot in self.slots:
            if slot.status == STATUS_OCCUPIED and slot.vehicle_number == target:
                return slot
        return None

    def find_by_slot_id(self, slot_id: str) -> Optional[ParkingSlot]:
        return self._slots_by_id().get(slot_id.upper())

    def occupied_slots(self) -> List[ParkingSlot]:
        return [slot for slot in self.slots if slot.status == STATUS_OCCUPIED]

    def available_slots(self) -> List[ParkingSlot]:
        return [slot for slot in self.slots if slot.is_available()]

    def reserved_slots(self) -> List[ParkingSlot]:
        return [slot for slot in self.slots if slot.is_reserved()]

    def vacant_reserved_slots(self, vehicle_type: Optional[str] = None) -> List[ParkingSlot]:
        """List unoccupied VIP-reserved bays (optionally filtered by vehicle type)."""
        slots = [
            s for s in self.slots
            if s.is_reserved() and s.status != STATUS_OCCUPIED and s.vehicle_number is None
        ]
        if vehicle_type:
            slots = [s for s in slots if s.vehicle_type == vehicle_type]
        return slots

    def find_first_available_vip(self, vehicle_type: str) -> Optional[ParkingSlot]:
        """Walk the zone in slot-id order and return the first unoccupied VIP-reserved bay."""
        index = self._slots_by_id()
        for slot_id in self._zone_slot_ids(vehicle_type):
            slot = index.get(slot_id)
            if (
                slot is not None
                and slot.is_reserved()
                and slot.status != STATUS_OCCUPIED
                and slot.vehicle_number is None
            ):
                return slot
        return None

    def reserve_slot(self, slot_id: str, is_security: bool = True) -> ParkingSlot:
        """Reserve a vacant slot for Fast-Track VIP / Emergency vehicles."""
        if not is_security:
            raise ParkingError("Unauthorized: Security privileges required to manage VIP slot reservations.")
        self.reload()
        sid = (slot_id or "").strip().upper()
        if not sid or sid not in ALL_SLOT_IDS:
            raise ParkingError("Invalid slot ID.")
        slot = self.find_by_slot_id(sid)
        if slot is None:
            raise ParkingError("Invalid slot ID.")
        if slot.status == STATUS_OCCUPIED or slot.vehicle_number is not None:
            raise ParkingError(f"Slot {slot.slot_id} is currently occupied and cannot be reserved.")
        if slot.is_reserved():
            raise ParkingError(f"Slot {slot.slot_id} is already reserved for VIP/Emergency.")

        slot.reserve()
        save_slot(slot, self.db_path)
        self.reload()
        return slot

    def unreserve_slot(self, slot_id: str, is_security: bool = True) -> ParkingSlot:
        """Release a reserved slot back to normal allocation if physically unoccupied."""
        if not is_security:
            raise ParkingError("Unauthorized: Security privileges required to manage VIP slot reservations.")
        self.reload()
        sid = (slot_id or "").strip().upper()
        if not sid or sid not in ALL_SLOT_IDS:
            raise ParkingError("Invalid slot ID.")
        slot = self.find_by_slot_id(sid)
        if slot is None:
            raise ParkingError("Invalid slot ID.")
        if slot.status == STATUS_OCCUPIED or slot.vehicle_number is not None:
            raise ParkingError(f"Slot {slot.slot_id} is currently occupied and cannot be unreserved.")
        if not slot.is_reserved():
            raise ParkingError(f"Slot {slot.slot_id} is not currently reserved.")

        slot.unreserve()
        save_slot(slot, self.db_path)
        self.reload()
        return slot

    def check_in(
        self,
        vehicle_number: str,
        vehicle_type: str,
        owner_category: str,
        entry_time,
        slot_id: Optional[str] = None,
    ) -> dict:
        """Validate, allocate slot (VIP-reserved or normal), persist, return success payload."""
        self.reload()
        number = normalize_vehicle_number(vehicle_number)
        vtype = (vehicle_type or "").strip()
        category = (owner_category or "").strip()
        hour = parse_hour(entry_time, field="Entry time")

        if not number:
            raise ParkingError("Vehicle number cannot be empty.")
        if vtype not in VEHICLE_TYPES:
            raise ParkingError("Vehicle type must be selected.")
        if category not in CATEGORIES:
            raise ParkingError("Owner category must be selected.")
        if self.is_vehicle_parked(number):
            raise ParkingError("Vehicle already parked.")

        target_slot_id = (slot_id or "").strip().upper()

        if category == CATEGORY_VIP:
            if target_slot_id:
                if target_slot_id not in ALL_SLOT_IDS:
                    raise ParkingError("Invalid slot ID.")
                slot = self.find_by_slot_id(target_slot_id)
                if slot is None:
                    raise ParkingError("Invalid slot ID.")
                if not slot.is_reserved():
                    raise ParkingError(f"Slot {slot.slot_id} is not reserved for VIP/Emergency use.")
                if slot.vehicle_type != vtype:
                    raise ParkingError(
                        f"Slot {slot.slot_id} ({slot.vehicle_type}) is incompatible with vehicle type '{vtype}'."
                    )
                if slot.status == STATUS_OCCUPIED or slot.vehicle_number is not None:
                    raise ParkingError(f"Slot {slot.slot_id} is currently occupied.")
            else:
                slot = self.find_first_available_vip(vtype)
                if slot is None:
                    raise ParkingError(f"No available VIP-reserved slot found for {vtype}.")
        else:
            if target_slot_id:
                if target_slot_id not in ALL_SLOT_IDS:
                    raise ParkingError("Invalid slot ID.")
                slot = self.find_by_slot_id(target_slot_id)
                if slot is None or not slot.is_available() or slot.is_reserved():
                    raise ParkingError(f"Slot {target_slot_id} is not available for regular vehicles.")
                if slot.vehicle_type != vtype:
                    raise ParkingError("Could not allocate a slot in the correct parking zone.")
            else:
                slot = self.find_first_available(vtype)
                if slot is None:
                    if vtype == VEHICLE_TWO:
                        raise ParkingError("Two-Wheeler parking is FULL.")
                    raise ParkingError("Four-Wheeler parking is FULL.")

        # Never allocate across zones (belt-and-suspenders with ordered search).
        if slot.vehicle_type != vtype:
            raise ParkingError("Could not allocate a slot in the correct parking zone.")

        vehicle = Vehicle(number, vtype, category, hour)
        slot.occupy(vehicle)
        save_slot(slot, self.db_path)

        txn = ParkingTransaction(
            vehicle_number=number,
            vehicle_type=vtype,
            owner_category=category,
            slot_id=slot.slot_id,
            entry_time=hour,
            parking_date=today_iso(),
            status=STATUS_ACTIVE,
        )
        txn_id = insert_transaction(txn, self.db_path)
        self.reload()

        return {
            "success": True,
            "message": "SUCCESS",
            "headline": "Vehicle Successfully Parked",
            "vehicle_number": number,
            "slot_id": slot.slot_id,
            "entry_time": hour,
            "entry_time_display": format_hour(hour),
            "entry_time_ampm": format_hour_ampm(hour),
            "vehicle_type": vtype,
            "owner_category": category,
            "transaction_id": txn_id,
            "detail": f"VIP/Emergency Vehicle {number} parked at Reserved Slot {slot.slot_id}."
            if category == CATEGORY_VIP
            else f"Vehicle {number} parked at Slot {slot.slot_id}.",
        }

    def check_out(self, search_by: str, identifier: str, exit_time) -> ParkingTransaction:
        """Locate an occupied vehicle, price the stay, vacate the slot, save the receipt."""
        self.reload()
        hour = parse_hour(exit_time, field="Exit time")
        mode = (search_by or "").strip().lower()
        raw = (identifier or "").strip()

        if not raw:
            raise ParkingError("Enter a vehicle number or spot ID.")

        slot = None
        if mode in ("spot", "spot_id", "slot", "slot_id"):
            spot_id = raw.upper()
            if spot_id not in ALL_SLOT_IDS:
                raise ParkingError("Invalid spot ID.")
            slot = self.find_by_slot_id(spot_id)
            if slot is None or slot.is_available() or not slot.vehicle_number:
                raise ParkingError("Vehicle/Spot not found or already vacant.")
        elif mode in ("vehicle", "vehicle_number", ""):
            number = normalize_vehicle_number(raw)
            if not number:
                raise ParkingError("Vehicle number cannot be empty.")
            slot = self.find_by_vehicle(number)
            if slot is None:
                raise ParkingError("Vehicle/Spot not found or already vacant.")
        else:
            raise ParkingError("Search by vehicle number or spot ID.")

        entry_hour = int(slot.entry_time)
        if hour < entry_hour:
            raise ParkingError("Exit time cannot be earlier than entry time.")

        duration = hour - entry_hour
        fee = calculate_fee(slot.owner_category, slot.vehicle_type, duration)
        lines = fee_breakdown(slot.owner_category, slot.vehicle_type, duration)

        txn = find_active_transaction(slot.vehicle_number, slot.slot_id, self.db_path)
        if txn is None:
            txn = ParkingTransaction(
                vehicle_number=slot.vehicle_number,
                vehicle_type=slot.vehicle_type,
                owner_category=slot.owner_category,
                slot_id=slot.slot_id,
                entry_time=entry_hour,
                parking_date=today_iso(),
                status=STATUS_ACTIVE,
            )
            txn.db_id = insert_transaction(txn, self.db_path)

        txn.exit_time = hour
        txn.duration = duration
        txn.fee = fee
        txn.status = STATUS_COMPLETED
        txn.fee_lines = lines
        update_transaction(txn, self.db_path)

        vacated_id = slot.slot_id
        slot.vacate()
        save_slot(slot, self.db_path)
        self.reload()

        txn.fee_lines = lines
        txn.slot_id = vacated_id
        return txn

    def search_vehicle(self, vehicle_number: str) -> dict:
        self.reload()
        number = normalize_vehicle_number(vehicle_number)
        if not number:
            raise ParkingError("Vehicle number cannot be empty.")
        slot = self.find_by_vehicle(number)
        if slot is None:
            return {"found": False, "message": "Vehicle is not currently parked.", "vehicle_number": number}
        return {
            "found": True,
            "vehicle_number": slot.vehicle_number,
            "vehicle_type": slot.vehicle_type,
            "owner_category": slot.owner_category,
            "slot_id": slot.slot_id,
            "entry_time": slot.entry_time,
            "entry_time_display": format_hour(slot.entry_time),
            "status": "OCCUPIED",
        }

    def dashboard(self) -> dict:
        self.reload()
        two = [s for s in self.slots if s.vehicle_type == VEHICLE_TWO]
        four = [s for s in self.slots if s.vehicle_type == VEHICLE_FOUR]
        occupied = self.occupied_slots()
        available = self.available_slots()
        reserved = self.reserved_slots()
        two_available = [s for s in two if s.is_available()]
        four_available = [s for s in four if s.is_available()]
        two_occupied = [s for s in two if s.status == STATUS_OCCUPIED]
        four_occupied = [s for s in four if s.status == STATUS_OCCUPIED]
        two_reserved = [s for s in two if s.is_reserved()]
        four_reserved = [s for s in four if s.is_reserved()]
        total = len(self.slots)
        occupied_count = len(occupied)
        occupancy_pct = round((occupied_count / total) * 100, 1) if total else 0.0
        today = today_iso()

        recent = [txn.to_dict() for txn in list_recent_transactions(20, self.db_path)]
        for item in recent:
            if item["status"] == STATUS_ACTIVE:
                item["exit_time_display"] = "--"
                item["fee_display"] = "--"
            else:
                item["fee_display"] = f"₹{item['fee']}"

        return {
            "total_slots": total,
            "two_wheeler_slots": len(two),
            "four_wheeler_slots": len(four),
            "occupied_slots": occupied_count,
            "available_slots": len(available),
            "reserved_slots": len(reserved),
            "two_wheeler_available": len(two_available),
            "two_wheeler_occupied": len(two_occupied),
            "two_wheeler_reserved": len(two_reserved),
            "four_wheeler_available": len(four_available),
            "four_wheeler_occupied": len(four_occupied),
            "four_wheeler_reserved": len(four_reserved),
            "vehicles_today": daily_entry_count(today, self.db_path),
            "fees_collected": daily_fees_collected(today, self.db_path),
            "occupancy_percent": occupancy_pct,
            "parking_date": today,
            "slots": [s.to_dict() for s in self.slots],
            "two_wheeler_zone": [s.to_dict() for s in two],
            "four_wheeler_zone": [s.to_dict() for s in four],
            "recent_transactions": recent,
        }

    def receipt_data(self, transaction_id: int) -> dict:
        txn = get_transaction(int(transaction_id), self.db_path)
        if txn is None:
            raise ParkingError("Receipt not found.")
        if txn.status != STATUS_COMPLETED:
            raise ParkingError("Receipt is available only after checkout.")
        txn.fee_lines = fee_breakdown(txn.owner_category, txn.vehicle_type, txn.duration)
        payload = txn.to_dict()
        payload["fee_lines"] = txn.fee_lines
        payload["status_line"] = f"Slot {txn.slot_id} is now VACANT."
        return payload


def today_iso() -> str:
    return date.today().isoformat()


def normalize_vehicle_number(value: Optional[str]) -> str:
    if value is None:
        return ""
    return " ".join(str(value).strip().split()).upper()


def parse_hour(value, field: str = "Time") -> int:
    if value is None or str(value).strip() == "":
        raise ParkingError(f"{field} must be an integer from 0 to 23.")
    try:
        hour = int(str(value).strip())
    except (TypeError, ValueError):
        raise ParkingError(f"{field} must be an integer from 0 to 23.")
    if hour < 0 or hour > 23:
        raise ParkingError(f"{field} must be between 0 and 23.")
    return hour
