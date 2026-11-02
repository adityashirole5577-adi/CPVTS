"""Exact parking fee matrix. All fee math lives here — nowhere else."""

from models import VEHICLE_FOUR, VEHICLE_TWO


class PricingError(ValueError):
    """Raised when category, vehicle type, or duration cannot be priced."""


def calculate_fee(owner_category: str, vehicle_type: str, duration: int) -> int:
    """
    Return the parking fee in rupees for the given category, type, and hours.

    Staff: always ₹0
    Student Two-Wheeler: first 2 hours free, then ₹10/hour
    Student Four-Wheeler: first 2 hours free, then ₹20/hour
    Visitor Two-Wheeler: ₹20/hour
    Visitor Four-Wheeler: ₹40/hour
    """
    if duration is None or int(duration) < 0:
        raise PricingError("Duration cannot be negative.")

    duration = int(duration)
    category = (owner_category or "").strip()
    vtype = (vehicle_type or "").strip()

    if category in ("Staff", "VIP/Emergency"):
        return 0

    if category == "Student":
        if vtype == VEHICLE_TWO:
            return 0 if duration <= 2 else (duration - 2) * 10
        if vtype == VEHICLE_FOUR:
            return 0 if duration <= 2 else (duration - 2) * 20
        raise PricingError("Invalid vehicle type for student pricing.")

    if category == "Visitor":
        if vtype == VEHICLE_TWO:
            return duration * 20
        if vtype == VEHICLE_FOUR:
            return duration * 40
        raise PricingError("Invalid vehicle type for visitor pricing.")

    raise PricingError("Invalid owner category.")


def fee_breakdown(owner_category: str, vehicle_type: str, duration: int) -> list:
    """
    Human-readable receipt lines matching the problem statement.

    Each item is a dict: {label, detail, amount}.
    """
    duration = int(duration)
    category = (owner_category or "").strip()
    vtype = (vehicle_type or "").strip()
    fee = calculate_fee(category, vtype, duration)
    lines = []

    if category == "Staff":
        lines.append(
            {
                "label": "Staff parking",
                "detail": "FREE",
                "amount": 0,
                "text": "Staff parking: FREE (₹0)",
            }
        )
        return lines

    if category == "VIP/Emergency":
        lines.append(
            {
                "label": "VIP/Emergency parking",
                "detail": "FREE",
                "amount": 0,
                "text": "VIP/Emergency parking: FREE (₹0)",
            }
        )
        return lines

    if category == "Student":
        lines.append(
            {
                "label": "First 2 Hours",
                "detail": "Free (₹0)",
                "amount": 0,
                "text": "First 2 Hours: Free (₹0)",
            }
        )
        if duration > 2:
            extra = duration - 2
            rate = 10 if vtype == VEHICLE_TWO else 20
            extra_fee = extra * rate
            hour_word = "hr" if extra == 1 else "hrs"
            lines.append(
                {
                    "label": f"Next {extra} Hours",
                    "detail": f"{extra} {hour_word} × ₹{rate} = ₹{extra_fee}",
                    "amount": extra_fee,
                    "text": f"Next {extra} Hours: {extra} {hour_word} × ₹{rate} = ₹{extra_fee}",
                }
            )
        return lines

    if category == "Visitor":
        rate = 20 if vtype == VEHICLE_TWO else 40
        hour_word = "hr" if duration == 1 else "hrs"
        lines.append(
            {
                "label": "Hourly visitor rate",
                "detail": f"{duration} {hour_word} × ₹{rate} = ₹{fee}",
                "amount": fee,
                "text": f"{duration} {hour_word} × ₹{rate} = ₹{fee}",
            }
        )
        return lines

    raise PricingError("Invalid owner category.")
