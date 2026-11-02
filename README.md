# Campus Parking & Vehicle Tracking System (CPVTS)

Digitize college campus parking by automatically allocating slots, tracking parked vehicles, calculating charges from the official fee matrix, generating receipts, and showing live availability.

## Problem statement

Campus parking is often handled with paper slips and ad-hoc assignment. CPVTS gives security staff a local web console that:

- Allocates the first free bay in the correct zone
- Blocks duplicate active entries
- Prices stays from owner category and vehicle type
- Vacates the slot on checkout
- Keeps a persistent SQLite history of completed parking

## Features

- Two parking zones: 10 two-wheeler slots (`T-01`–`T-10`) and 5 four-wheeler slots (`F-01`–`F-05`)
- Automatic first-available slot allocation (no cross-zone parking)
- Vehicle check-in and check-out (by vehicle number or spot ID)
- Exact staff / student / visitor pricing
- Professional printable receipt
- Live dashboard statistics (not hardcoded)
- Slot grid with occupied vehicle details
- Vehicle finder for security staff
- Daily vehicle count and fee collection
- Client-side and server-side validation
- SQLite persistence that survives restarts

## Technology stack

| Layer | Choice |
| --- | --- |
| Frontend | HTML5, CSS3, JavaScript (responsive, no paid UI kits) |
| Backend | Python, Flask |
| Database | SQLite (`database/parking.db`) |
| In-memory logic | Lists, dictionaries, and classes (`ParkingSlot`, `Vehicle`, `ParkingManager`, `ParkingTransaction`) |

No Firebase, MongoDB, paid APIs, or internet connection is required for core use.

## System architecture

```
Browser (templates + static/css + static/js)
        │
        ▼
Flask routes in app.py
        │
        ├── ParkingManager (parking.py)  — allocate, search, checkout, dashboard
        ├── pricing.py                   — single source of fee rules
        ├── models.py                    — domain objects
        └── database.py                  — parameterized SQLite access
```

## Database structure

### PARKING_SLOTS

| Field | Type | Notes |
| --- | --- | --- |
| id | INTEGER PK | Auto-increment |
| slot_id | TEXT UNIQUE | `T-01` … `F-05` |
| zone | TEXT | Two-Wheeler Zone / Four-Wheeler Zone |
| vehicle_type | TEXT | Two-Wheeler / Four-Wheeler |
| status | TEXT | Available / Occupied |
| vehicle_number | TEXT | Null when vacant |
| entry_time | INTEGER | Hour 0–23 |
| owner_category | TEXT | Staff / Student / Visitor |

### PARKING_TRANSACTIONS

| Field | Type | Notes |
| --- | --- | --- |
| id | INTEGER PK | Receipt id |
| vehicle_number | TEXT | Normalized uppercase |
| vehicle_type | TEXT | |
| owner_category | TEXT | |
| slot_id | TEXT | |
| entry_time | INTEGER | |
| exit_time | INTEGER | Null while ACTIVE |
| duration | INTEGER | Exit hour − entry hour |
| fee | INTEGER | Rupees |
| parking_date | TEXT | ISO date of check-in |
| status | TEXT | ACTIVE / COMPLETED |

Tables and the 15 vacant slots are created automatically on first launch. Existing occupancy is never wiped on restart.

## Installation

From the `cpvts` folder:

```bash
python -m venv .venv
```

Windows:

```bash
.venv\Scripts\activate
pip install -r requirements.txt
```

macOS / Linux:

```bash
source .venv/bin/activate
pip install -r requirements.txt
```

## How to run

```bash
python app.py
```

Open [http://127.0.0.1:5000](http://127.0.0.1:5000)

Optional self-test suite:

```bash
python -m unittest tests.test_cpvts
```

## Demo credentials

None. There is no login. The app is a local operations console.

## Sample workflow (hackathon demo)

1. Open the dashboard. Total slots = 15, occupied = 0, available = 15. All `T` and `F` bays are Available.
2. Vehicle Entry: `KA-22-XY-9876`, Two-Wheeler, Student, entry hour `9`. Assigned slot is `T-01` if it is free (first available).
3. Dashboard: occupied = 1, available = 14, two-wheeler occupied = 1, vehicles today = 1.
4. Vehicle Search for `KA-22-XY-9876` shows current slot, entry time, category, type, OCCUPIED.
5. Vehicle Exit with the same number and exit hour `13`. Duration = 4 hours. Student two-wheeler fee = ₹20.
6. Receipt shows the fee breakdown and **Print Receipt**.
7. Slot returns to Available. Occupied = 0, available = 15, fees collected = ₹20.

To force assignment of `T-02` in a live demo, park any other two-wheeler first so `T-01` is taken.

## Fee calculation logic

Duration uses **user-entered hours only** (not the system clock):

`duration = exit_hour - entry_hour`

Exit hour cannot be earlier than entry hour.

| Category | Two-Wheeler | Four-Wheeler |
| --- | --- | --- |
| Staff | ₹0 | ₹0 |
| Student | First 2 hours free, then ₹10/hour | First 2 hours free, then ₹20/hour |
| Visitor | ₹20 × duration | ₹40 × duration |

Sample: Student two-wheeler, 09:00–13:00 → 4 hours → first 2 free + 2 × ₹10 = **₹20**.

## Validation rules

- Vehicle number required, trimmed, uppercased
- Duplicate active vehicle rejected: `Vehicle already parked.`
- Vehicle type and owner category required
- Entry/exit hour integers 0–23
- Exit earlier than entry rejected
- Zone full messages for two-wheelers and four-wheelers
- Unknown or vacant spot: `Vehicle/Spot not found or already vacant.`
- Invalid spot IDs rejected
- Search of a vehicle that is not parked: `Vehicle is not currently parked.`
- Database and unexpected errors return a friendly message (no stack traces in the UI)

## Future scope

- Overnight parking (exit hour wrapping past midnight)
- Barrier / RFID hardware integration
- CSV export of daily collections
- Optional staff PIN for voiding a receipt

## Project layout

```
cpvts/
├── app.py
├── database.py
├── models.py
├── parking.py
├── pricing.py
├── requirements.txt
├── README.md
├── tests/
│   └── test_cpvts.py
├── templates/
├── static/
│   ├── css/style.css
│   └── js/script.js
└── database/
    └── parking.db   (created on first run)
```
