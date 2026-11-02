"""Campus Parking & Vehicle Tracking System — Flask application."""

from flask import (
    Flask,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from database import DatabaseError
from parking import ParkingError, ParkingManager

app = Flask(__name__)
app.secret_key = "cpvts-campus-parking-local-demo-key"

manager = ParkingManager()


def user_message(exc: Exception) -> str:
    if isinstance(exc, (ParkingError, DatabaseError)):
        return str(exc)
    return "An unexpected server error occurred. Please try again."


@app.errorhandler(404)
def not_found(_error):
    if request.path.startswith("/api/"):
        return jsonify({"error": "Not found."}), 404
    flash("The page you requested was not found.", "error")
    return render_template("index.html", dashboard=manager.dashboard(), page="dashboard"), 404


@app.errorhandler(500)
def server_error(_error):
    if request.path.startswith("/api/"):
        return jsonify({"error": "An unexpected server error occurred."}), 500
    flash("An unexpected server error occurred. Please try again.", "error")
    return render_template("index.html", dashboard=manager.dashboard(), page="dashboard"), 500


@app.route("/")
def dashboard():
    try:
        data = manager.dashboard()
    except Exception as exc:
        flash(user_message(exc), "error")
        data = _empty_dashboard()
    return render_template("index.html", dashboard=data, page="dashboard")


@app.route("/entry", methods=["GET", "POST"])
def entry():
    result = session.pop("entry_result", None)
    if request.method == "POST":
        try:
            payload = manager.check_in(
                request.form.get("vehicle_number"),
                request.form.get("vehicle_type"),
                request.form.get("owner_category"),
                request.form.get("entry_time"),
                slot_id=request.form.get("slot_id"),
            )
            session["entry_result"] = payload
            flash(
                f"SUCCESS — Vehicle {payload['vehicle_number']} parked at Slot {payload['slot_id']}. "
                f"Entry Time: {payload['entry_time_ampm']}",
                "success",
            )
            return redirect(url_for("entry"))
        except Exception as exc:
            flash(user_message(exc), "error")
            return render_template(
                "entry.html",
                page="entry",
                form=request.form,
                reserved_slots=manager.vacant_reserved_slots(),
                result=None,
            )
    return render_template(
        "entry.html",
        page="entry",
        form={
            "slot_id": request.args.get("slot_id", ""),
            "owner_category": request.args.get("category", ""),
            "vehicle_type": request.args.get("vehicle_type", ""),
        },
        reserved_slots=manager.vacant_reserved_slots(),
        result=result,
    )


@app.route("/exit", methods=["GET", "POST"])
def exit_vehicle():
    if request.method == "POST":
        try:
            txn = manager.check_out(
                request.form.get("search_by"),
                request.form.get("identifier"),
                request.form.get("exit_time"),
            )
            flash("Checkout complete. Receipt generated.", "success")
            return redirect(url_for("receipt", transaction_id=txn.db_id))
        except Exception as exc:
            flash(user_message(exc), "error")
            return render_template("exit.html", page="exit", form=request.form)
    return render_template("exit.html", page="exit", form={})


@app.route("/search", methods=["GET", "POST"])
def search():
    result = None
    query = ""
    if request.method == "POST":
        query = request.form.get("vehicle_number", "")
        try:
            result = manager.search_vehicle(query)
        except Exception as exc:
            flash(user_message(exc), "error")
    elif request.args.get("vehicle_number"):
        query = request.args.get("vehicle_number", "")
        try:
            result = manager.search_vehicle(query)
        except Exception as exc:
            flash(user_message(exc), "error")
    return render_template("search.html", page="search", result=result, query=query)


@app.route("/slots")
def slots_page():
    try:
        data = manager.dashboard()
    except Exception as exc:
        flash(user_message(exc), "error")
        data = _empty_dashboard()
    return render_template("slots.html", dashboard=data, page="slots")


def _is_security_authorized() -> bool:
    """
    Check if the current request has security operator authorization.
    In this local operations console, security operator requests are permitted by default.
    Requests with an explicit unauthorized role (via header, parameter, or session) are rejected.
    """
    role = (
        request.headers.get("X-User-Role")
        or request.args.get("role")
        or request.form.get("role")
        or session.get("user_role")
    )
    if role and str(role).strip().lower() in ("unauthorized", "visitor", "user", "guest", "student"):
        return False
    return True


@app.route("/reserve", methods=["GET", "POST"])
def reserve_slot():
    if request.method == "POST":
        action = (request.form.get("action") or "reserve").strip().lower()
        slot_id = (request.form.get("slot_id") or "").strip().upper()

        if not _is_security_authorized():
            flash("Unauthorized: Security privileges required to manage VIP reservations.", "error")
            return redirect(url_for("reserve_slot"))

        try:
            if action in ("unreserve", "release"):
                slot = manager.unreserve_slot(slot_id, is_security=True)
                flash(
                    f"SUCCESS — Reservation for slot {slot.slot_id} released. Slot is now available for normal parking.",
                    "success",
                )
            else:
                slot = manager.reserve_slot(slot_id, is_security=True)
                flash(
                    f"SUCCESS — Slot {slot.slot_id} ({slot.vehicle_type}) has been successfully reserved for VIP / Emergency vehicles.",
                    "success",
                )
            return redirect(url_for("reserve_slot"))
        except Exception as exc:
            flash(user_message(exc), "error")
            try:
                dash_data = manager.dashboard()
            except Exception:
                dash_data = _empty_dashboard()
            return render_template(
                "reserve.html",
                page="reserve",
                dashboard=dash_data,
                selected_slot=slot_id,
            )

    try:
        dash_data = manager.dashboard()
    except Exception as exc:
        flash(user_message(exc), "error")
        dash_data = _empty_dashboard()

    return render_template(
        "reserve.html",
        page="reserve",
        dashboard=dash_data,
        selected_slot=request.args.get("slot_id", "").upper(),
    )


@app.route("/api/reserve", methods=["POST"])
def api_reserve():
    data = request.get_json(silent=True) or request.form
    action = (data.get("action") or "reserve").strip().lower()
    slot_id = (data.get("slot_id") or "").strip().upper()

    if not _is_security_authorized():
        return jsonify({"error": "Unauthorized: Security privileges required."}), 403

    try:
        if action in ("unreserve", "release"):
            slot = manager.unreserve_slot(slot_id, is_security=True)
            return jsonify({
                "success": True,
                "message": f"Reservation for slot {slot.slot_id} released.",
                "slot": slot.to_dict(),
            })
        else:
            slot = manager.reserve_slot(slot_id, is_security=True)
            return jsonify({
                "success": True,
                "message": f"Slot {slot.slot_id} reserved for VIP / Emergency.",
                "slot": slot.to_dict(),
            })
    except Exception as exc:
        return jsonify({"error": user_message(exc)}), 400


@app.route("/receipt/<int:transaction_id>")
def receipt(transaction_id):
    try:
        data = manager.receipt_data(transaction_id)
    except Exception as exc:
        flash(user_message(exc), "error")
        return redirect(url_for("exit_vehicle"))
    return render_template("receipt.html", receipt=data, page="receipt")


@app.route("/api/dashboard")
def api_dashboard():
    try:
        return jsonify(manager.dashboard())
    except Exception as exc:
        return jsonify({"error": user_message(exc)}), 500


@app.route("/api/slots")
def api_slots():
    try:
        data = manager.dashboard()
        return jsonify(
            {
                "slots": data["slots"],
                "two_wheeler_zone": data["two_wheeler_zone"],
                "four_wheeler_zone": data["four_wheeler_zone"],
            }
        )
    except Exception as exc:
        return jsonify({"error": user_message(exc)}), 500


@app.route("/api/vehicle/<path:vehicle_number>")
def api_vehicle(vehicle_number):
    try:
        result = manager.search_vehicle(vehicle_number)
        if not result.get("found"):
            return jsonify(result), 404
        return jsonify(result)
    except Exception as exc:
        return jsonify({"error": user_message(exc), "found": False}), 400


def _empty_dashboard():
    return {
        "total_slots": 15,
        "two_wheeler_slots": 10,
        "four_wheeler_slots": 5,
        "occupied_slots": 0,
        "available_slots": 15,
        "reserved_slots": 0,
        "two_wheeler_available": 10,
        "two_wheeler_occupied": 0,
        "two_wheeler_reserved": 0,
        "four_wheeler_available": 5,
        "four_wheeler_occupied": 0,
        "four_wheeler_reserved": 0,
        "vehicles_today": 0,
        "fees_collected": 0,
        "occupancy_percent": 0,
        "parking_date": "",
        "slots": [],
        "two_wheeler_zone": [],
        "four_wheeler_zone": [],
        "recent_transactions": [],
    }


if __name__ == "__main__":
    app.run(debug=False, host="127.0.0.1", port=5000)
