#!/usr/bin/env python3
"""
Create a BAWE-0252 student account in editorrah DB,
create matching classes, and link their existing V3 stylometry profiles.
"""
import asyncio
import os
import uuid
from datetime import datetime, timezone, timedelta

from dotenv import load_dotenv
load_dotenv()

from motor.motor_asyncio import AsyncIOMotorClient
import bcrypt


STUDENT_EMAIL = "bawe0252@editorrah.com"
STUDENT_PASSWORD = "Bawe@0252Test"
STUDENT_NAME = "BAWE Author 0252"
STUDENT_ID = "bawe-0252"

TEACHER_EMAIL = "teacher@editorrah.com"

COURSES = [
    {"class_id_tag": "BAWE-AH-TEST", "name": "Arts & Humanities", "subject": "Arts & Humanities", "description": "BAWE Arts & Humanities test course"},
    {"class_id_tag": "BAWE-SS-TEST", "name": "Social Sciences", "subject": "Social Sciences", "description": "BAWE Social Sciences test course"},
]


async def main():
    client = AsyncIOMotorClient(os.getenv("MONGO_URI"))
    db = client[os.getenv("DB_NAME", "editorrah_integrity")]

    # Find or pick a teacher
    teacher = await db.users.find_one({"role": "teacher"})
    if not teacher:
        print("No teacher found in DB. Create a teacher account first.")
        return
    teacher_id = teacher["user_id"]
    teacher_name = teacher["name"]
    print(f"Using teacher: {teacher_name} ({teacher['email']})")

    # Check if student already exists
    existing = await db.users.find_one({"email": STUDENT_EMAIL})
    if existing:
        print(f"Student already exists: {STUDENT_EMAIL} (user_id: {existing['user_id']})")
        student_user_id = existing["user_id"]
    else:
        # Create student account
        password_hash = bcrypt.hashpw(STUDENT_PASSWORD.encode(), bcrypt.gensalt()).decode()
        student_user_id = STUDENT_ID  # Use the stylometry student_id as user_id for direct mapping

        user_doc = {
            "user_id": student_user_id,
            "email": STUDENT_EMAIL,
            "password_hash": password_hash,
            "name": STUDENT_NAME,
            "university": "BAWE Corpus University",
            "role": "student",
            "profile_image": None,
            "email_verified": True,
            "stylometry_enrolled": True,
            "stylometry_version": "v3",
            "stylometry_courses_enrolled": len(COURSES),
            "stylometry_last_updated": datetime.now(timezone.utc),
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }
        await db.users.insert_one(user_doc)
        print(f"Created student: {STUDENT_EMAIL} / {STUDENT_PASSWORD}")
        print(f"  user_id: {student_user_id}")

    # Create classes and memberships
    for course in COURSES:
        class_tag = course["class_id_tag"]

        # Check if class already exists with this tag
        existing_class = await db.classes.find_one({"stylometry_class_tag": class_tag})
        if existing_class:
            class_id = existing_class["class_id"]
            print(f"Class already exists: {course['name']} (class_id: {class_id})")
        else:
            class_id = str(uuid.uuid4())
            # Generate class code
            import secrets, string
            chars = string.ascii_uppercase + string.digits
            chars = chars.replace('O','').replace('0','').replace('I','').replace('1','').replace('L','')
            class_code = ''.join(secrets.choice(chars) for _ in range(6))

            class_doc = {
                "class_id": class_id,
                "name": course["name"],
                "section": "BAWE Test",
                "subject": course["subject"],
                "description": course["description"],
                "color": "#1a73e8",
                "class_code": class_code,
                "teacher_id": teacher_id,
                "teacher_name": teacher_name,
                "settings": {},
                "stylometry_class_tag": class_tag,
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
                "archived": False,
            }
            await db.classes.insert_one(class_doc)
            print(f"Created class: {course['name']} (code: {class_code}, class_id: {class_id})")

        # Add teacher membership
        existing_teacher_member = await db.class_members.find_one({"class_id": class_id, "user_id": teacher_id})
        if not existing_teacher_member:
            await db.class_members.insert_one({
                "class_id": class_id,
                "user_id": teacher_id,
                "role": "teacher",
                "joined_at": datetime.now(timezone.utc),
            })

        # Add student membership with V3 enrollment already done
        existing_member = await db.class_members.find_one({"class_id": class_id, "user_id": student_user_id})
        if existing_member:
            # Update with V3 enrollment
            await db.class_members.update_one(
                {"class_id": class_id, "user_id": student_user_id},
                {"$set": {
                    "stylometry_enrolled": True,
                    "stylometry_profile_strength": "strong",
                    "stylometry_samples_count": 9,
                    "stylometry_enrolled_at": datetime.now(timezone.utc),
                }},
            )
            print(f"  Updated membership for {class_tag} with V3 enrollment")
        else:
            await db.class_members.insert_one({
                "class_id": class_id,
                "user_id": student_user_id,
                "user_name": STUDENT_NAME,
                "user_email": STUDENT_EMAIL,
                "role": "student",
                "joined_at": datetime.now(timezone.utc),
                "stylometry_enrolled": True,
                "stylometry_profile_strength": "strong",
                "stylometry_samples_count": 9,
                "stylometry_enrolled_at": datetime.now(timezone.utc),
            })
            print(f"  Added student to {class_tag} with V3 enrollment (strong profile)")

    print(f"\n{'='*50}")
    print(f"LOGIN CREDENTIALS:")
    print(f"  Email:    {STUDENT_EMAIL}")
    print(f"  Password: {STUDENT_PASSWORD}")
    print(f"  Role:     student")
    print(f"  V3 Stylometry: enrolled in {len(COURSES)} courses (strong profiles)")
    print(f"  Student ID maps to: {STUDENT_ID} (matches forensicstylo API)")
    print(f"{'='*50}")

    client.close()


if __name__ == "__main__":
    asyncio.run(main())
