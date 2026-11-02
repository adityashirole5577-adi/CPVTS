"""Self-tests for CPVTS pricing, allocation, validation, and dashboard stats."""

import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from parking import ParkingError, ParkingManager
from pricing import calculate_fee, fee_breakdown


class PricingTests(unittest.TestCase):
    def test_staff_two_wheeler(self):
        self.assertEqual(calculate_fee("Staff", "Two-Wheeler", 4), 0)

    def test_staff_four_wheeler(self):
        self.assertEqual(calculate_fee("Staff", "Four-Wheeler", 11), 0)

    def test_student_two_one_hour(self):
        self.assertEqual(calculate_fee("Student", "Two-Wheeler", 1), 0)

    def test_student_two_two_hours(self):
        self.assertEqual(calculate_fee("Student", "Two-Wheeler", 2), 0)

    def test_student_two_three_hours(self):
        self.assertEqual(calculate_fee("Student", "Two-Wheeler", 3), 10)

    def test_student_two_four_hours_sample(self):
        self.assertEqual(calculate_fee("Student", "Two-Wheeler", 4), 20)
        lines = fee_breakdown("Student", "Two-Wheeler", 4)
        self.assertEqual(lines[0]["text"], "First 2 Hours: Free (₹0)")
        self.assertEqual(lines[1]["text"], "Next 2 Hours: 2 hrs × ₹10 = ₹20")

    def test_student_four_four_hours(self):
        self.assertEqual(calculate_fee("Student", "Four-Wheeler", 4), 40)

    def test_visitor_two_four_hours(self):
        self.assertEqual(calculate_fee("Visitor", "Two-Wheeler", 4), 80)

    def test_visitor_four_four_hours(self):
        self.assertEqual(calculate_fee("Visitor", "Four-Wheeler", 4), 160)


class ParkingFlowTests(unittest.TestCase):
    def setUp(self):
        handle, path = tempfile.mkstemp(suffix=".db")
        os.close(handle)
        self.db_path = path
        self.manager = ParkingManager(db_path=path)

    def tearDown(self):
        try:
            os.remove(self.db_path)
        except OSError:
            pass

    def test_initial_slots_available(self):
        dash = self.manager.dashboard()
        self.assertEqual(dash["total_slots"], 15)
        self.assertEqual(dash["occupied_slots"], 0)
        self.assertEqual(dash["available_slots"], 15)
        self.assertEqual(dash["two_wheeler_available"], 10)
        self.assertEqual(dash["four_wheeler_available"], 5)

    def test_first_two_wheeler_gets_t01(self):
        result = self.manager.check_in("ka-22-xy-9876", "Two-Wheeler", "Student", 9)
        self.assertEqual(result["vehicle_number"], "KA-22-XY-9876")
        self.assertEqual(result["slot_id"], "T-01")

    def test_duplicate_rejected(self):
        self.manager.check_in("KA-22-XY-9876", "Two-Wheeler", "Student", 9)
        with self.assertRaises(ParkingError) as ctx:
            self.manager.check_in("KA-22-XY-9876", "Two-Wheeler", "Student", 10)
        self.assertEqual(str(ctx.exception), "Vehicle already parked.")

    def test_exit_before_entry_rejected(self):
        self.manager.check_in("KA-11-AA-1111", "Two-Wheeler", "Student", 15)
        with self.assertRaises(ParkingError) as ctx:
            self.manager.check_out("vehicle", "KA-11-AA-1111", 12)
        self.assertEqual(str(ctx.exception), "Exit time cannot be earlier than entry time.")

    def test_sample_checkout_fee_and_release(self):
        self.manager.check_in("KA-22-XY-9876", "Two-Wheeler", "Student", 9)
        txn = self.manager.check_out("vehicle", "KA-22-XY-9876", 13)
        self.assertEqual(txn.duration, 4)
        self.assertEqual(txn.fee, 20)
        dash = self.manager.dashboard()
        self.assertEqual(dash["occupied_slots"], 0)
        self.assertEqual(dash["available_slots"], 15)
        self.assertEqual(dash["fees_collected"], 20)
        self.assertEqual(dash["vehicles_today"], 1)
        search = self.manager.search_vehicle("KA-22-XY-9876")
        self.assertFalse(search["found"])

    def test_exit_by_spot_id(self):
        self.manager.check_in("KA-33-BB-2222", "Four-Wheeler", "Visitor", 9)
        txn = self.manager.check_out("spot", "F-01", 13)
        self.assertEqual(txn.slot_id, "F-01")
        self.assertEqual(txn.fee, 160)

    def test_vacant_spot_exit(self):
        with self.assertRaises(ParkingError) as ctx:
            self.manager.check_out("spot", "T-05", 10)
        self.assertEqual(str(ctx.exception), "Vehicle/Spot not found or already vacant.")

    def test_invalid_spot_id(self):
        with self.assertRaises(ParkingError) as ctx:
            self.manager.check_out("spot", "X-99", 10)
        self.assertEqual(str(ctx.exception), "Invalid spot ID.")

    def test_search_missing(self):
        result = self.manager.search_vehicle("NO-SUCH-CAR")
        self.assertFalse(result["found"])
        self.assertEqual(result["message"], "Vehicle is not currently parked.")

    def test_two_wheeler_zone_full(self):
        for i in range(10):
            self.manager.check_in(f"TW-{i:02d}", "Two-Wheeler", "Staff", 8)
        with self.assertRaises(ParkingError) as ctx:
            self.manager.check_in("TW-99", "Two-Wheeler", "Staff", 8)
        self.assertEqual(str(ctx.exception), "Two-Wheeler parking is FULL.")
        result = self.manager.check_in("FW-01", "Four-Wheeler", "Staff", 8)
        self.assertTrue(result["slot_id"].startswith("F-"))

    def test_four_wheeler_zone_full(self):
        for i in range(5):
            self.manager.check_in(f"FW-{i:02d}", "Four-Wheeler", "Visitor", 8)
        with self.assertRaises(ParkingError) as ctx:
            self.manager.check_in("FW-99", "Four-Wheeler", "Visitor", 8)
        self.assertEqual(str(ctx.exception), "Four-Wheeler parking is FULL.")
        result = self.manager.check_in("TW-01", "Two-Wheeler", "Visitor", 8)
        self.assertTrue(result["slot_id"].startswith("T-"))

    def test_allocation_skips_occupied(self):
        self.manager.check_in("A-1", "Two-Wheeler", "Staff", 9)
        result = self.manager.check_in("A-2", "Two-Wheeler", "Staff", 9)
        self.assertEqual(result["slot_id"], "T-02")

    def test_rejected_entry_not_counted(self):
        self.manager.check_in("A-1", "Two-Wheeler", "Staff", 9)
        try:
            self.manager.check_in("A-1", "Two-Wheeler", "Staff", 9)
        except ParkingError:
            pass
        dash = self.manager.dashboard()
        self.assertEqual(dash["vehicles_today"], 1)

    def test_empty_vehicle_number(self):
        with self.assertRaises(ParkingError):
            self.manager.check_in("   ", "Two-Wheeler", "Staff", 9)

    def test_invalid_entry_hour(self):
        with self.assertRaises(ParkingError):
            self.manager.check_in("A-1", "Two-Wheeler", "Staff", 24)
        with self.assertRaises(ParkingError):
            self.manager.check_in("A-1", "Two-Wheeler", "Staff", -1)


class FlaskRouteTests(unittest.TestCase):
    def setUp(self):
        handle, path = tempfile.mkstemp(suffix=".db")
        os.close(handle)
        self.db_path = path
        import app as app_module

        self.app_module = app_module
        self.previous = app_module.manager
        app_module.manager = ParkingManager(db_path=path)
        self.client = app_module.app.test_client()

    def tearDown(self):
        self.app_module.manager = self.previous
        try:
            os.remove(self.db_path)
        except OSError:
            pass

    def test_dashboard_and_apis(self):
        home = self.client.get("/")
        self.assertEqual(home.status_code, 200)
        self.assertIn(b"Total Slots", home.data)
        dash = self.client.get("/api/dashboard")
        self.assertEqual(dash.status_code, 200)
        payload = dash.get_json()
        self.assertEqual(payload["total_slots"], 15)
        self.assertEqual(payload["available_slots"], 15)
        slots = self.client.get("/api/slots")
        self.assertEqual(slots.status_code, 200)
        self.assertEqual(len(slots.get_json()["slots"]), 15)

    def test_entry_exit_search_receipt_pages(self):
        self.assertEqual(self.client.get("/entry").status_code, 200)
        posted = self.client.post(
            "/entry",
            data={
                "vehicle_number": " ka-22-xy-9876 ",
                "vehicle_type": "Two-Wheeler",
                "owner_category": "Student",
                "entry_time": "9",
            },
            follow_redirects=True,
        )
        self.assertEqual(posted.status_code, 200)
        self.assertIn(b"T-01", posted.data)

        found = self.client.get("/api/vehicle/KA-22-XY-9876")
        self.assertEqual(found.status_code, 200)
        self.assertEqual(found.get_json()["slot_id"], "T-01")

        search = self.client.post("/search", data={"vehicle_number": "KA-22-XY-9876"})
        self.assertIn(b"OCCUPIED", search.data)

        exited = self.client.post(
            "/exit",
            data={"search_by": "vehicle", "identifier": "KA-22-XY-9876", "exit_time": "13"},
            follow_redirects=True,
        )
        self.assertEqual(exited.status_code, 200)
        self.assertIn(b"TOTAL AMOUNT DUE", exited.data)
        self.assertIn(b"\xe2\x82\xb920", exited.data)
        missing = self.client.get("/api/vehicle/KA-22-XY-9876")
        self.assertEqual(missing.status_code, 404)

    def test_pages_exist(self):
        for path in ("/exit", "/search", "/slots", "/reserve"):
            self.assertEqual(self.client.get(path).status_code, 200)

    def test_navigation_includes_reserve_vip_slot(self):
        resp = self.client.get("/")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"Reserve VIP Slot", resp.data)


class VIPReservationTests(unittest.TestCase):
    def setUp(self):
        handle, path = tempfile.mkstemp(suffix=".db")
        os.close(handle)
        self.db_path = path
        self.manager = ParkingManager(db_path=path)
        import app as app_module
        self.app_module = app_module
        self.previous_mgr = app_module.manager
        app_module.manager = self.manager
        self.client = app_module.app.test_client()

    def tearDown(self):
        self.app_module.manager = self.previous_mgr
        try:
            os.remove(self.db_path)
        except OSError:
            pass

    def test_1_authorized_security_can_reserve_valid_unoccupied_slot(self):
        # 1. An authorized security user can reserve a valid, unoccupied slot.
        slot = self.manager.reserve_slot("F-01", is_security=True)
        self.assertEqual(slot.slot_id, "F-01")
        self.assertEqual(slot.status, "Reserved")
        self.assertTrue(slot.is_reserved())
        self.assertFalse(slot.is_available())

        # Check via dashboard
        dash = self.manager.dashboard()
        self.assertEqual(dash["reserved_slots"], 1)
        self.assertEqual(dash["four_wheeler_reserved"], 1)
        self.assertEqual(dash["available_slots"], 14)
        self.assertEqual(dash["four_wheeler_available"], 4)

    def test_2_authorized_security_can_unreserve_reserved_unoccupied_slot(self):
        # 2. An authorized security user can unreserve a reserved, unoccupied slot.
        self.manager.reserve_slot("F-01", is_security=True)
        released = self.manager.unreserve_slot("F-01", is_security=True)
        self.assertEqual(released.slot_id, "F-01")
        self.assertEqual(released.status, "Available")
        self.assertFalse(released.is_reserved())
        self.assertTrue(released.is_available())

        dash = self.manager.dashboard()
        self.assertEqual(dash["reserved_slots"], 0)
        self.assertEqual(dash["available_slots"], 15)
        self.assertEqual(dash["four_wheeler_available"], 5)

    def test_3_regular_vehicle_cannot_be_assigned_reserved_slot(self):
        # 3. A regular vehicle cannot be assigned a reserved slot.
        # Reserve F-01 (normally first Four-Wheeler slot)
        self.manager.reserve_slot("F-01", is_security=True)

        # Check in a regular Four-Wheeler - should get F-02, skipping reserved F-01
        res1 = self.manager.check_in("KA-01-FW-1001", "Four-Wheeler", "Staff", 8)
        self.assertEqual(res1["slot_id"], "F-02")
        self.assertNotEqual(res1["slot_id"], "F-01")

        # Fill the remaining Four-Wheeler slots (F-03, F-04, F-05)
        self.manager.check_in("KA-01-FW-1002", "Four-Wheeler", "Staff", 8)  # F-03
        self.manager.check_in("KA-01-FW-1003", "Four-Wheeler", "Staff", 8)  # F-04
        self.manager.check_in("KA-01-FW-1004", "Four-Wheeler", "Staff", 8)  # F-05

        # All compatible normal slots are full, but F-01 is VIP-reserved.
        # Next four-wheeler must be told Four-Wheeler parking is FULL, and NOT get F-01.
        with self.assertRaises(ParkingError) as ctx:
            self.manager.check_in("KA-01-FW-9999", "Four-Wheeler", "Visitor", 8)
        self.assertEqual(str(ctx.exception), "Four-Wheeler parking is FULL.")

        # F-01 is still reserved and vacant
        f01 = self.manager.find_by_slot_id("F-01")
        self.assertEqual(f01.status, "Reserved")
        self.assertIsNone(f01.vehicle_number)

    def test_4_reserved_slot_persists_across_restart(self):
        # 4. A reserved slot remains reserved after an application restart or database reload.
        self.manager.reserve_slot("T-01", is_security=True)
        self.manager.reserve_slot("F-01", is_security=True)

        # Simulate full restart by instantiating a new ParkingManager pointing to same DB
        reloaded_mgr = ParkingManager(db_path=self.db_path)
        t01 = reloaded_mgr.find_by_slot_id("T-01")
        f01 = reloaded_mgr.find_by_slot_id("F-01")

        self.assertEqual(t01.status, "Reserved")
        self.assertTrue(t01.is_reserved())
        self.assertFalse(t01.is_available())

        self.assertEqual(f01.status, "Reserved")
        self.assertTrue(f01.is_reserved())
        self.assertFalse(f01.is_available())

        dash = reloaded_mgr.dashboard()
        self.assertEqual(dash["reserved_slots"], 2)
        self.assertEqual(dash["two_wheeler_reserved"], 1)
        self.assertEqual(dash["four_wheeler_reserved"], 1)
        self.assertEqual(dash["available_slots"], 13)

        # Even after reload, normal allocation skips the reserved slot
        tw_res = reloaded_mgr.check_in("KA-02-TW-2001", "Two-Wheeler", "Student", 9)
        self.assertEqual(tw_res["slot_id"], "T-02")

    def test_5_invalid_slot_ids_rejected(self):
        # 5. Invalid slot IDs are rejected.
        for invalid_id in ("X-99", "INVALID", "F-99", "T-15", "", "   "):
            with self.assertRaises(ParkingError) as ctx:
                self.manager.reserve_slot(invalid_id, is_security=True)
            self.assertEqual(str(ctx.exception), "Invalid slot ID.")

            with self.assertRaises(ParkingError) as ctx:
                self.manager.unreserve_slot(invalid_id, is_security=True)
            self.assertEqual(str(ctx.exception), "Invalid slot ID.")

    def test_6_occupied_slot_cannot_be_reserved_or_unreserved(self):
        # 6. An occupied slot cannot be reserved or unreserved in a way that creates an inconsistent state.
        # Check in a vehicle into T-01
        self.manager.check_in("KA-05-AA-5555", "Two-Wheeler", "Staff", 10)
        t01 = self.manager.find_by_slot_id("T-01")
        self.assertEqual(t01.status, "Occupied")

        # Attempt to reserve occupied slot -> rejected
        with self.assertRaises(ParkingError) as ctx:
            self.manager.reserve_slot("T-01", is_security=True)
        self.assertIn("occupied and cannot be reserved", str(ctx.exception))

        # Attempt to unreserve occupied slot -> rejected
        with self.assertRaises(ParkingError) as ctx:
            self.manager.unreserve_slot("T-01", is_security=True)
        self.assertIn("occupied and cannot be unreserved", str(ctx.exception))

        # Duplicate reservation: reserve T-02, then try to reserve T-02 again
        self.manager.reserve_slot("T-02", is_security=True)
        with self.assertRaises(ParkingError) as ctx:
            self.manager.reserve_slot("T-02", is_security=True)
        self.assertIn("already reserved", str(ctx.exception))

        # Conflicting action: unreserve an unoccupied slot that is not reserved (T-03 is Available)
        with self.assertRaises(ParkingError) as ctx:
            self.manager.unreserve_slot("T-03", is_security=True)
        self.assertIn("not currently reserved", str(ctx.exception))

    def test_7_normal_parking_allocation_works_when_other_slots_available(self):
        # 7. Normal parking allocation works correctly when other slots are available.
        # Reserve T-01 and T-02
        self.manager.reserve_slot("T-01", is_security=True)
        self.manager.reserve_slot("T-02", is_security=True)

        res1 = self.manager.check_in("KA-10-TW-0001", "Two-Wheeler", "Student", 10)
        self.assertEqual(res1["slot_id"], "T-03")

        res2 = self.manager.check_in("KA-10-TW-0002", "Two-Wheeler", "Student", 10)
        self.assertEqual(res2["slot_id"], "T-04")

        # Release T-02
        self.manager.unreserve_slot("T-02", is_security=True)

        # Now T-02 is free and earliest in line (T-01 still reserved)
        res3 = self.manager.check_in("KA-10-TW-0003", "Two-Wheeler", "Student", 10)
        self.assertEqual(res3["slot_id"], "T-02")

    def test_8_existing_functionality_unchanged_with_reservations(self):
        # 8. Existing vehicle entry, vehicle exit, fee calculation, receipts, and other functionality remain unchanged.
        # Reserve a slot in each zone
        self.manager.reserve_slot("T-01", is_security=True)
        self.manager.reserve_slot("F-01", is_security=True)

        # Normal entry
        res = self.manager.check_in("KA-04-CR-4444", "Four-Wheeler", "Visitor", 10)
        self.assertEqual(res["slot_id"], "F-02")

        # Search
        search = self.manager.search_vehicle("KA-04-CR-4444")
        self.assertTrue(search["found"])
        self.assertEqual(search["slot_id"], "F-02")

        # Normal checkout after 3 hours (Visitor Four-Wheeler: 3 * 40 = 120)
        txn = self.manager.check_out("vehicle", "KA-04-CR-4444", 13)
        self.assertEqual(txn.duration, 3)
        self.assertEqual(txn.fee, 120)
        self.assertEqual(txn.slot_id, "F-02")

        # Receipt
        rcpt = self.manager.receipt_data(txn.db_id)
        self.assertEqual(rcpt["fee"], 120)
        self.assertIn("F-02 is now VACANT", rcpt["status_line"])

        # Reserved slots F-01 and T-01 remain reserved throughout
        self.assertTrue(self.manager.find_by_slot_id("F-01").is_reserved())
        self.assertTrue(self.manager.find_by_slot_id("T-01").is_reserved())

    def test_9_unauthorized_user_cannot_change_reservation_status(self):
        # 9. Unauthorized users cannot change reservation status, where authentication is supported.
        # Direct manager layer with is_security=False
        with self.assertRaises(ParkingError) as ctx:
            self.manager.reserve_slot("F-01", is_security=False)
        self.assertIn("Unauthorized", str(ctx.exception))

        self.manager.reserve_slot("F-01", is_security=True)
        with self.assertRaises(ParkingError) as ctx:
            self.manager.unreserve_slot("F-01", is_security=False)
        self.assertIn("Unauthorized", str(ctx.exception))

        # Via API route with unauthorized role header
        api_unauth = self.client.post(
            "/api/reserve",
            json={"slot_id": "T-05", "action": "reserve"},
            headers={"X-User-Role": "visitor"},
        )
        self.assertEqual(api_unauth.status_code, 403)
        self.assertIn("Unauthorized", api_unauth.get_json()["error"])
        # Slot T-05 was not reserved
        self.assertTrue(self.manager.find_by_slot_id("T-05").is_available())

        # Via API route with security role (or default operator)
        api_auth = self.client.post(
            "/api/reserve",
            json={"slot_id": "T-05", "action": "reserve"},
        )
        self.assertEqual(api_auth.status_code, 200)
        self.assertTrue(self.manager.find_by_slot_id("T-05").is_reserved())

        # Web form route: POST /reserve with unauthorized role redirected with flash
        form_unauth = self.client.post(
            "/reserve",
            data={"slot_id": "T-06", "action": "reserve", "role": "unauthorized"},
            follow_redirects=True,
        )
        self.assertIn(b"Unauthorized", form_unauth.data)
        self.assertTrue(self.manager.find_by_slot_id("T-06").is_available())

        # Web form route: POST /reserve as security operator succeeds
        form_auth = self.client.post(
            "/reserve",
            data={"slot_id": "T-06", "action": "reserve"},
            follow_redirects=True,
        )
        self.assertIn(b"SUCCESS", form_auth.data)
        self.assertTrue(self.manager.find_by_slot_id("T-06").is_reserved())


class VIPVehicleEntryTests(unittest.TestCase):
    def setUp(self):
        handle, path = tempfile.mkstemp(suffix=".db")
        os.close(handle)
        self.db_path = path
        self.manager = ParkingManager(db_path=path)
        import app as app_module
        self.app_module = app_module
        self.previous_mgr = app_module.manager
        app_module.manager = self.manager
        self.client = app_module.app.test_client()

    def tearDown(self):
        self.app_module.manager = self.previous_mgr
        try:
            os.remove(self.db_path)
        except OSError:
            pass

    def test_1_vip_vehicle_can_enter_free_compatible_reserved_slot(self):
        # 1. A VIP vehicle can enter a free, compatible VIP-reserved slot.
        self.manager.reserve_slot("F-01", is_security=True)

        # Check in specifying slot_id F-01
        res = self.manager.check_in(
            "VIP-0001",
            "Four-Wheeler",
            "VIP/Emergency",
            9,
            slot_id="F-01",
        )
        self.assertEqual(res["slot_id"], "F-01")
        self.assertEqual(res["vehicle_number"], "VIP-0001")
        self.assertEqual(res["owner_category"], "VIP/Emergency")

        slot = self.manager.find_by_slot_id("F-01")
        self.assertEqual(slot.status, "Occupied")
        self.assertTrue(slot.is_reserved())
        self.assertEqual(slot.vehicle_number, "VIP-0001")

        # Also test auto-allocation without specifying slot_id:
        self.manager.reserve_slot("T-01", is_security=True)
        res_tw = self.manager.check_in(
            "AMB-9999",
            "Two-Wheeler",
            "VIP/Emergency",
            10,
        )
        self.assertEqual(res_tw["slot_id"], "T-01")
        self.assertEqual(res_tw["vehicle_number"], "AMB-9999")

    def test_2_regular_vehicle_cannot_enter_vip_reserved_slot(self):
        # 2. A regular vehicle cannot enter a VIP-reserved slot.
        self.manager.reserve_slot("F-01", is_security=True)

        # Auto-allocation must skip F-01
        res = self.manager.check_in("KA-01-REG-1111", "Four-Wheeler", "Staff", 8)
        self.assertEqual(res["slot_id"], "F-02")

        # Explicit slot targeting of a reserved slot by regular vehicle must be rejected
        with self.assertRaises(ParkingError) as ctx:
            self.manager.check_in(
                "KA-01-REG-2222",
                "Four-Wheeler",
                "Student",
                8,
                slot_id="F-01",
            )
        self.assertIn("not available for regular vehicles", str(ctx.exception))

    def test_3_vip_vehicle_cannot_enter_occupied_slot(self):
        # 3. A VIP vehicle cannot enter an occupied slot.
        self.manager.reserve_slot("F-01", is_security=True)
        self.manager.check_in("VIP-0001", "Four-Wheeler", "VIP/Emergency", 9, slot_id="F-01")

        # Second VIP vehicle attempts to take the same occupied slot
        with self.assertRaises(ParkingError) as ctx:
            self.manager.check_in(
                "VIP-0002",
                "Four-Wheeler",
                "VIP/Emergency",
                10,
                slot_id="F-01",
            )
        self.assertIn("currently occupied", str(ctx.exception))

    def test_4_vip_vehicle_cannot_use_slot_incompatible_with_type(self):
        # 4. A VIP vehicle cannot use a slot incompatible with its vehicle type.
        self.manager.reserve_slot("F-01", is_security=True)  # Four-Wheeler slot

        with self.assertRaises(ParkingError) as ctx:
            self.manager.check_in(
                "VIP-BIKE-1",
                "Two-Wheeler",
                "VIP/Emergency",
                9,
                slot_id="F-01",
            )
        self.assertIn("incompatible with vehicle type", str(ctx.exception))

    def test_5_vip_vehicle_rejected_gracefully_when_no_reserved_slot_available(self):
        # 5. A VIP vehicle is rejected gracefully if no available VIP-reserved slot exists.
        # No Four-Wheeler slots are reserved (all normal slots are vacant)
        with self.assertRaises(ParkingError) as ctx:
            self.manager.check_in(
                "VIP-CAR-1",
                "Four-Wheeler",
                "VIP/Emergency",
                9,
            )
        self.assertIn("No available VIP-reserved slot found", str(ctx.exception))

        # Attempt to target an unreserved normal slot with VIP category
        with self.assertRaises(ParkingError) as ctx:
            self.manager.check_in(
                "VIP-CAR-1",
                "Four-Wheeler",
                "VIP/Emergency",
                9,
                slot_id="F-02",
            )
        self.assertIn("not reserved for VIP/Emergency", str(ctx.exception))

    def test_6_vip_entry_updates_database_and_dashboard_correctly(self):
        # 6. VIP entry updates the database and dashboard correctly.
        self.manager.reserve_slot("F-01", is_security=True)
        self.manager.check_in("VIP-POLICE-1", "Four-Wheeler", "VIP/Emergency", 8, slot_id="F-01")

        # Dashboard assertions
        dash = self.manager.dashboard()
        self.assertEqual(dash["occupied_slots"], 1)
        self.assertEqual(dash["four_wheeler_occupied"], 1)
        self.assertEqual(dash["four_wheeler_available"], 4)
        self.assertEqual(dash["reserved_slots"], 1)

        # Database assertions
        import sqlite3
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM PARKING_SLOTS WHERE slot_id = 'F-01'").fetchone()
        self.assertEqual(row["status"], "Occupied")
        self.assertEqual(row["is_reserved"], 1)
        self.assertEqual(row["vehicle_number"], "VIP-POLICE-1")
        self.assertEqual(row["owner_category"], "VIP/Emergency")
        conn.close()

    def test_7_vip_exit_releases_occupied_status_while_preserving_vip_reservation(self):
        # 7. VIP exit releases the occupied status while preserving the slot's VIP reservation.
        self.manager.reserve_slot("F-01", is_security=True)
        self.manager.check_in("VIP-GUEST-1", "Four-Wheeler", "VIP/Emergency", 9, slot_id="F-01")

        # Exit
        txn = self.manager.check_out("vehicle", "VIP-GUEST-1", 14)
        self.assertEqual(txn.duration, 5)
        self.assertEqual(txn.fee, 0)
        self.assertEqual(txn.slot_id, "F-01")

        # Slot F-01 must now be unoccupied, BUT still VIP-reserved!
        f01 = self.manager.find_by_slot_id("F-01")
        self.assertEqual(f01.status, "Reserved")
        self.assertTrue(f01.is_reserved())
        self.assertIsNone(f01.vehicle_number)
        self.assertFalse(f01.is_available())

        # Regular vehicles still cannot take F-01
        res = self.manager.check_in("KA-01-REG-3333", "Four-Wheeler", "Visitor", 15)
        self.assertEqual(res["slot_id"], "F-02")
        self.assertNotEqual(res["slot_id"], "F-01")

        # Another VIP vehicle can now use F-01
        res_vip2 = self.manager.check_in("VIP-GUEST-2", "Four-Wheeler", "VIP/Emergency", 15, slot_id="F-01")
        self.assertEqual(res_vip2["slot_id"], "F-01")

    def test_8_existing_regular_workflows_continue_to_work(self):
        # 8. Existing regular vehicle entry, exit, fee calculations, and receipts continue to work.
        self.manager.reserve_slot("F-01", is_security=True)
        self.manager.check_in("VIP-01", "Four-Wheeler", "VIP/Emergency", 8, slot_id="F-01")

        # Regular Two-Wheeler Visitor entry & checkout (4 hrs -> ₹80)
        self.manager.check_in("KA-01-TW-VISIT", "Two-Wheeler", "Visitor", 9)
        txn_vis = self.manager.check_out("vehicle", "KA-01-TW-VISIT", 13)
        self.assertEqual(txn_vis.fee, 80)
        self.assertEqual(txn_vis.slot_id, "T-01")

        # Regular Four-Wheeler Student entry & checkout (4 hrs -> ₹40)
        self.manager.check_in("KA-01-FW-STUD", "Four-Wheeler", "Student", 9)
        txn_stud = self.manager.check_out("vehicle", "KA-01-FW-STUD", 13)
        self.assertEqual(txn_stud.fee, 40)
        self.assertEqual(txn_stud.slot_id, "F-02")

        # VIP checkout (₹0)
        txn_vip = self.manager.check_out("vehicle", "VIP-01", 13)
        self.assertEqual(txn_vip.fee, 0)
        rcpt = self.manager.receipt_data(txn_vip.db_id)
        self.assertEqual(rcpt["fee"], 0)

        dash = self.manager.dashboard()
        self.assertEqual(dash["fees_collected"], 120)

    def test_9_web_entry_route_with_vip_category(self):
        # Web route test: POST /entry with VIP/Emergency and slot_id
        self.manager.reserve_slot("F-01", is_security=True)
        resp = self.client.post(
            "/entry",
            data={
                "vehicle_number": "KA-VIP-7777",
                "vehicle_type": "Four-Wheeler",
                "owner_category": "VIP/Emergency",
                "entry_time": "9",
                "slot_id": "F-01",
            },
            follow_redirects=True,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"KA-VIP-7777", resp.data)
        self.assertIn(b"F-01", resp.data)

        # Search for the VIP vehicle
        search = self.manager.search_vehicle("KA-VIP-7777")
        self.assertTrue(search["found"])
        self.assertEqual(search["slot_id"], "F-01")
        self.assertEqual(search["owner_category"], "VIP/Emergency")


if __name__ == "__main__":
    unittest.main()


