"""Create data/dealership.sqlite3 with a small synthetic dealership dataset."""
import os
import random
import sqlite3
import sys
from datetime import date, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from kisanmitra import config  # noqa: E402

MACHINES = [
    # model, category, hp, price_inr, stock, fuel_lph, notes
    ("JD 5050D", "tractor", 50, 850000, 4, 4.2, "2WD utility tractor, 8F+4R gears"),
    ("JD 5105", "tractor", 40, 720000, 2, 3.6, "2WD, popular for rotavator work"),
    ("JD 5310 4WD", "tractor", 55, 1180000, 1, 4.8, "4WD, suited to wet paddy fields"),
    ("JD 3028EN", "tractor", 28, 610000, 3, 2.4, "Narrow orchard tractor"),
    ("JD W70 Harvester", "harvester", 76, 2650000, 1, 9.5, "Self-propelled combine harvester"),
    ("Rotavator RT-150", "implement", 0, 78000, 6, 0.0, "1.5 m rotavator, needs 45+ hp"),
    ("MB Plough 2B", "implement", 0, 42000, 5, 0.0, "2-bottom mould board plough"),
    ("Seed Drill SD-11", "implement", 0, 65000, 2, 0.0, "11-tyne seed cum fertiliser drill"),
    ("Baler RB-120", "implement", 0, 890000, 0, 0.0, "Round baler, out of stock"),
]
PARTS = [
    ("AL-172772", "Engine oil filter", "JD 5050D", 640, 18),
    ("RE-509672", "Fuel filter", "JD 5050D", 1180, 6),
    ("AL-150288", "Air filter element", "JD 5105", 1450, 0),
    ("RE-45864", "Hydraulic filter", "JD 5310 4WD", 2260, 4),
    ("TY-6382", "Front tyre 6.00-16", "JD 5105", 5400, 8),
]
ISSUES = ["250-hour service", "hydraulic lift slow", "clutch adjustment", "overheating",
          "starter motor replacement", "500-hour service", "oil leak from rear axle"]
CUSTOMERS = ["Ramesh Sahu", "Devendra Patel", "Sunita Verma", "Gopal Yadav", "Mahesh Chandrakar"]
VILLAGES = ["Dhamtari", "Rajnandgaon", "Durg", "Bemetara", "Mahasamund"]


def main():
    os.makedirs(os.path.dirname(config.DB_PATH), exist_ok=True)
    if os.path.exists(config.DB_PATH):
        os.remove(config.DB_PATH)
    con = sqlite3.connect(config.DB_PATH)
    c = con.cursor()
    c.execute("""CREATE TABLE machines (model TEXT PRIMARY KEY, category TEXT, hp INTEGER,
                 price_inr INTEGER, stock INTEGER, fuel_lph REAL, notes TEXT)""")
    c.execute("""CREATE TABLE parts (part_no TEXT PRIMARY KEY, name TEXT, model TEXT,
                 price_inr INTEGER, stock INTEGER)""")
    c.execute("""CREATE TABLE service_records (id INTEGER PRIMARY KEY, customer TEXT, village TEXT,
                 model TEXT, service_date TEXT, hours INTEGER, issue TEXT, cost_inr INTEGER)""")
    c.executemany("INSERT INTO machines VALUES (?,?,?,?,?,?,?)", MACHINES)
    c.executemany("INSERT INTO parts VALUES (?,?,?,?,?)", PARTS)

    random.seed(7)
    rows = []
    tractors = [m[0] for m in MACHINES if m[1] == "tractor"]
    for i in range(1, 41):
        cust = random.choice(CUSTOMERS)
        rows.append((i, cust, random.choice(VILLAGES), random.choice(tractors),
                     (date(2026, 9, 1) - timedelta(days=random.randint(5, 700))).isoformat(),
                     random.choice([250, 500, 750, 1000, 1250]), random.choice(ISSUES),
                     random.randint(1200, 18000)))
    c.executemany("INSERT INTO service_records VALUES (?,?,?,?,?,?,?,?)", rows)
    con.commit()
    print(f"Seeded {config.DB_PATH}: {len(MACHINES)} machines, {len(PARTS)} parts, {len(rows)} service records")
    con.close()


if __name__ == "__main__":
    main()
