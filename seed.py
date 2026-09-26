"""
Optional convenience script: populates the database with a couple of sample
diagnostic centres and tests so you have something to book against right
after starting the server.

Usage:
    python seed.py
"""
from app.database import Base, engine, SessionLocal
from app import models

Base.metadata.create_all(bind=engine)

SAMPLE_DATA = [
    {
        "name": "City Diagnostics Centre",
        "location": "Kolkata",
        "tests": [
            {"name": "Complete Blood Count (CBC)", "price": 399.0},
            {"name": "Lipid Profile", "price": 799.0},
            {"name": "Thyroid Panel (TSH, T3, T4)", "price": 899.0},
        ],
    },
    {
        "name": "MetroLife Labs",
        "location": "Mumbai",
        "tests": [
            {"name": "Chest X-Ray", "price": 599.0},
            {"name": "COVID-19 RT-PCR", "price": 699.0},
        ],
    },
]


def seed():
    db = SessionLocal()
    try:
        if db.query(models.DiagnosticCentre).count() > 0:
            print("Database already has centres; skipping seed.")
            return

        for centre_data in SAMPLE_DATA:
            centre = models.DiagnosticCentre(name=centre_data["name"], location=centre_data["location"])
            db.add(centre)
            db.flush()  # get centre.id before creating tests

            for test_data in centre_data["tests"]:
                db.add(models.DiagnosticTest(centre_id=centre.id, **test_data))

        db.commit()
        print("Seeded sample diagnostic centres and tests.")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
