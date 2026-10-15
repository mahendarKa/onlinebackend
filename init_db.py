"""
Initialize the database: create all tables, apply light column migrations
for tables created before later schema changes, and seed default accounts.

Usage:
    python init_db.py

Override the seeded credentials via environment variables:
    ADMIN_EMAIL, ADMIN_PASSWORD, ADMIN_NAME
    SUPERADMIN_EMAIL, SUPERADMIN_PASSWORD, SUPERADMIN_NAME
"""
import os

from sqlalchemy import inspect, text

from app.config.database import Base, engine, SessionLocal
from app import models  # noqa: F401  (registers all models on Base.metadata)
from app.models.user import User
from app.utils.security import hash_password


ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@example.com")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")
ADMIN_NAME = os.getenv("ADMIN_NAME", "Administrator")

SUPERADMIN_EMAIL = os.getenv("SUPERADMIN_EMAIL", "superadmin@example.com")
SUPERADMIN_PASSWORD = os.getenv("SUPERADMIN_PASSWORD", "superadmin123")
SUPERADMIN_NAME = os.getenv("SUPERADMIN_NAME", "Super Admin")


# Columns added to models after the tables may already exist.
# create_all() never ALTERs existing tables, so we patch them here.
COLUMN_MIGRATIONS = {
    "student_answers": {
        "selected_option_ids": "JSON",
        "match_answers": "JSON",
    },
    "question_options": {
        "image_url": "VARCHAR(1000)",
    },
    "question_calculated": {
        "datasets": "JSON",
    },
    "exams": {
        "passing_percentage": "NUMERIC(5,2) NULL",
    },
    "users": {
        "mobile_number": "VARCHAR(20)",
        "profile_pic": "VARCHAR(500)",
        "first_name": "VARCHAR(100)",
        "last_name": "VARCHAR(100)",
    },
}

# Columns removed from models — drop them if the table still has them.
DROP_COLUMN_MIGRATIONS = {
    "users": ["name"],
}

# Tables that gained TimestampMixin after already existing in the DB.
# Missing created_at / updated_at columns are added as DATETIME NULL.
_TIMESTAMP_TABLES = [
    "exams",
    "exam_questions",
    "exam_batches",
    "exam_attempts",
    "student_answers",
    "exam_results",
    "exam_feedback",
    "batch_students",
    "batch_teachers",
    "audit_logs",
    "notifications",
    "paragraph_passages",
    "paragraph_questions",
    "coding_questions",
    "coding_test_cases",
    "question_calculated",
    "question_description",
    "question_essay",
    "question_gapselect",
    "question_images",
    "question_match",
    "question_multianswer",
    "question_numerical",
    "question_options",
    "question_ordering",
    "question_paragraph",
    "question_shortanswer",
    "question_truefalse",
]

for _table in _TIMESTAMP_TABLES:
    _cols = COLUMN_MIGRATIONS.setdefault(_table, {})
    _cols.setdefault("created_at", "DATETIME NULL")
    _cols.setdefault("updated_at", "DATETIME NULL")


def apply_column_migrations():
    inspector = inspect(engine)
    with engine.begin() as conn:
        for table, columns in COLUMN_MIGRATIONS.items():
            if table not in inspector.get_table_names():
                continue
            existing = {
                c["name"] for c in inspector.get_columns(table)
            }
            for column, ddl in columns.items():
                if column not in existing:
                    conn.execute(
                        text(
                            f"ALTER TABLE {table} "
                            f"ADD COLUMN {column} {ddl}"
                        )
                    )
                    print(f"  + {table}.{column}")

        # The first inspector may have cached pre-ALTER column lists —
        # use a fresh one for everything below.
        inspector = inspect(engine)

        # Backfill first_name / last_name from the legacy 'name' column
        # BEFORE it is dropped by DROP_COLUMN_MIGRATIONS below.
        cols = (
            {c["name"] for c in inspector.get_columns("users")}
            if "users" in inspector.get_table_names() else set()
        )
        if {"name", "first_name", "last_name"} <= cols:
            conn.execute(
                text(
                    "UPDATE users SET "
                    "first_name = SUBSTRING_INDEX(name, ' ', 1), "
                    "last_name = NULLIF("
                    "TRIM(SUBSTRING(name, "
                    "LENGTH(SUBSTRING_INDEX(name, ' ', 1)) + 1)),"
                    " '') "
                    "WHERE first_name IS NULL"
                )
            )

        # Backfill pass percentage from the legacy absolute passing_marks
        # once total_marks is known, preserving each exam's old cutoff.
        exam_cols = (
            {c["name"] for c in inspector.get_columns("exams")}
            if "exams" in inspector.get_table_names() else set()
        )
        if {"passing_percentage", "passing_marks", "total_marks"} <= exam_cols:
            conn.execute(
                text(
                    "UPDATE exams SET "
                    "passing_percentage = ROUND("
                    "passing_marks / total_marks * 100, 2) "
                    "WHERE passing_percentage IS NULL "
                    "AND total_marks > 0"
                )
            )

        for table, columns in DROP_COLUMN_MIGRATIONS.items():
            if table not in inspector.get_table_names():
                continue
            existing = {
                c["name"] for c in inspector.get_columns(table)
            }
            for column in columns:
                if column in existing:
                    conn.execute(
                        text(
                            f"ALTER TABLE {table} "
                            f"DROP COLUMN {column}"
                        )
                    )
                    print(f"  - {table}.{column}")


def seed_user(db, name, email, password, role):
    existing = db.query(User).filter(User.email == email).first()
    if existing:
        if existing.role != role:
            existing.role = role
            db.commit()
            print(f"Promoted {email} to role '{role}'.")
        else:
            print(f"{role} already exists: {email}")
        return

    first, _, last = name.partition(" ")
    db.add(
        User(
            first_name=first,
            last_name=last.strip() or None,
            email=email,
            password=hash_password(password),
            role=role,
            is_active=True,
        )
    )
    db.commit()
    print(f"Seeded {role}: {email} / {password}")


def main():
    print("Creating tables...")
    Base.metadata.create_all(bind=engine)
    print("Tables created.")

    print("Applying column migrations...")
    apply_column_migrations()
    print("Migrations done.")

    db = SessionLocal()
    try:
        seed_user(db, ADMIN_NAME, ADMIN_EMAIL, ADMIN_PASSWORD, "admin")
        seed_user(
            db,
            SUPERADMIN_NAME,
            SUPERADMIN_EMAIL,
            SUPERADMIN_PASSWORD,
            "superadmin",
        )
    finally:
        db.close()


if __name__ == "__main__":
    main()
