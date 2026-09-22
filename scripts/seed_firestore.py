"""Seed Firestore database with initial habit tracking records."""
import datetime
from google.cloud import firestore

# CRITICAL: Hardcode project ID as string for Firestore client
PROJECT_ID = "qwiklabs-gcp-01-4891f3ba97eb"

def seed_database():
    db = firestore.Client(project=PROJECT_ID)
    collection = db.collection("habit_entries")

    today = datetime.date.today()
    day_1 = (today - datetime.timedelta(days=2)).isoformat()
    day_2 = (today - datetime.timedelta(days=1)).isoformat()
    day_3 = today.isoformat()

    seeded_items = [
        # Day 1 entries
        {
            "id": f"water_{day_1}",
            "habit_name": "water",
            "amount": 2.0,
            "target": 2.0,
            "unit": "L",
            "date": day_1,
            "status": "Completed",
            "category": "fitness",
            "notes": "Hydrated well throughout the day."
        },
        {
            "id": f"meditation_{day_1}",
            "habit_name": "meditation",
            "amount": 10.0,
            "target": 10.0,
            "unit": "mins",
            "date": day_1,
            "status": "Completed",
            "category": "mindfulness",
            "notes": "Morning mindfulness session."
        },

        # Day 2 entries
        {
            "id": f"water_{day_2}",
            "habit_name": "water",
            "amount": 2.0,
            "target": 2.0,
            "unit": "L",
            "date": day_2,
            "status": "Completed",
            "category": "fitness",
            "notes": "Drank water after workout."
        },
        {
            "id": f"meditation_{day_2}",
            "habit_name": "meditation",
            "amount": 10.0,
            "target": 10.0,
            "unit": "mins",
            "date": day_2,
            "status": "Completed",
            "category": "mindfulness",
            "notes": "Evening relaxation session."
        },
        {
            "id": f"reading_{day_2}",
            "habit_name": "reading",
            "amount": 20.0,
            "target": 20.0,
            "unit": "pages",
            "date": day_2,
            "status": "Completed",
            "category": "reading",
            "notes": "Read sci-fi chapter before bed."
        },

        # Day 3 (Today) initial setup
        {
            "id": f"water_{day_3}",
            "habit_name": "water",
            "amount": 2.0,
            "target": 2.0,
            "unit": "L",
            "date": day_3,
            "status": "Completed",
            "category": "fitness",
            "notes": "Met daily water target!"
        },
        {
            "id": f"meditation_{day_3}",
            "habit_name": "meditation",
            "amount": 10.0,
            "target": 10.0,
            "unit": "mins",
            "date": day_3,
            "status": "Completed",
            "category": "mindfulness",
            "notes": "10-minute mindfulness session completed."
        },
    ]

    print(f"Seeding Firestore collection 'habit_entries' in project '{PROJECT_ID}'...")
    for item in seeded_items:
        doc_id = item.pop("id")
        collection.document(doc_id).set(item)
        print(f"  - Document seeded: habit_entries/{doc_id}")

    print("✅ Firestore database seeding completed successfully!")

if __name__ == "__main__":
    seed_database()
