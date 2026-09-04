import argparse
import json
import os
from pathlib import Path
from typing import Any

import psycopg2
from dotenv import load_dotenv
from psycopg2.extras import Json, execute_values


TABLE_NAME = "public.keeneland_september_2026"
JSON_FILENAME = "keeneland_september_2026_horses_v0.json"


COLUMNS = [
    "hip_number",
    "book_number",
    "sale_day",
    "sale_date",
    "source_pdf",
    "catalog_label",
    "sex",
    "sire",
    "dam",
    "broodmare_sire",
    "breeder",
    "true_nicks_rating",
    "previous_sale_history",
    "first_foals_year",
    "stud_fee_2026",
    "stud_fee_2024",
    "dosage_profile",
    "dosage_index",
    "center_of_distribution",
    "weanling_2025_stats",
    "yearling_2025_stats",
    "two_year_old_2026_stats",
    "first_dam_summary",
    "first_dam_record",
    "first_dam_produce",
    "nicking_summary",
    "raw_record",
]


def load_json(json_path: Path) -> list[dict[str, Any]]:
    with json_path.open("r", encoding="utf-8") as file:
        horses = json.load(file)

    if not isinstance(horses, list):
        raise ValueError("Expected JSON root to be a list.")

    return horses


def validate_horses(
    horses: list[dict[str, Any]],
) -> None:
    if not horses:
        raise ValueError("JSON contains no horses.")

    hips = [int(horse["hip_number"]) for horse in horses]

    if len(hips) != len(set(hips)):
        raise ValueError("Duplicate hip numbers found in JSON.")

    print(f"JSON records: {len(horses):,}")
    print(f"Unique hips: {len(set(hips)):,}")
    print(f"Hip range: {min(hips):,} - {max(hips):,}")


def horse_to_row(
    horse: dict[str, Any],
) -> tuple[Any, ...]:
    values: list[Any] = []

    for column in COLUMNS:
        value = horse.get(column)

        if column == "first_dam_produce":
            value = Json(value or [])

        values.append(value)

    return tuple(values)


def preview_horses(
    horses: list[dict[str, Any]],
    count: int = 5,
) -> None:
    print()
    print("=" * 100)
    print("LOAD PREVIEW")
    print("=" * 100)

    for horse in horses[:count]:
        print(
            f"Hip {horse['hip_number']} | "
            f"Book {horse['book_number']} | "
            f"Day {horse['sale_day']} | "
            f"{horse['sire']} x {horse['dam']} | "
            f"{horse['sex']}"
        )

    print("=" * 100)


def insert_horses(
    connection,
    horses: list[dict[str, Any]],
    truncate: bool,
) -> None:
    rows = [
        horse_to_row(horse)
        for horse in horses
    ]

    column_sql = ", ".join(COLUMNS)

    insert_sql = f"""
        INSERT INTO {TABLE_NAME} (
            {column_sql}
        )
        VALUES %s
        ON CONFLICT (hip_number)
        DO UPDATE SET
            book_number = EXCLUDED.book_number,
            sale_day = EXCLUDED.sale_day,
            sale_date = EXCLUDED.sale_date,
            source_pdf = EXCLUDED.source_pdf,
            catalog_label = EXCLUDED.catalog_label,
            sex = EXCLUDED.sex,
            sire = EXCLUDED.sire,
            dam = EXCLUDED.dam,
            broodmare_sire = EXCLUDED.broodmare_sire,
            breeder = EXCLUDED.breeder,
            true_nicks_rating = EXCLUDED.true_nicks_rating,
            previous_sale_history = EXCLUDED.previous_sale_history,
            first_foals_year = EXCLUDED.first_foals_year,
            stud_fee_2026 = EXCLUDED.stud_fee_2026,
            stud_fee_2024 = EXCLUDED.stud_fee_2024,
            dosage_profile = EXCLUDED.dosage_profile,
            dosage_index = EXCLUDED.dosage_index,
            center_of_distribution = EXCLUDED.center_of_distribution,
            weanling_2025_stats = EXCLUDED.weanling_2025_stats,
            yearling_2025_stats = EXCLUDED.yearling_2025_stats,
            two_year_old_2026_stats = EXCLUDED.two_year_old_2026_stats,
            first_dam_summary = EXCLUDED.first_dam_summary,
            first_dam_record = EXCLUDED.first_dam_record,
            first_dam_produce = EXCLUDED.first_dam_produce,
            nicking_summary = EXCLUDED.nicking_summary,
            raw_record = EXCLUDED.raw_record,
            updated_at = NOW()
    """

    with connection.cursor() as cursor:
        if truncate:
            print()
            print(f"Truncating {TABLE_NAME}...")
            cursor.execute(
                f"TRUNCATE TABLE {TABLE_NAME};"
            )

        print(f"Loading {len(rows):,} horses...")

        execute_values(
            cursor,
            insert_sql,
            rows,
            page_size=500,
        )

    connection.commit()


def verify_load(connection) -> None:
    with connection.cursor() as cursor:
        cursor.execute(
            f"""
            SELECT
                COUNT(*) AS total,
                COUNT(DISTINCT hip_number) AS unique_hips,
                MIN(hip_number) AS min_hip,
                MAX(hip_number) AS max_hip
            FROM {TABLE_NAME};
            """
        )

        total, unique_hips, min_hip, max_hip = cursor.fetchone()

        print()
        print("=" * 100)
        print("DATABASE VERIFICATION")
        print("=" * 100)
        print(f"Rows: {total:,}")
        print(f"Unique hips: {unique_hips:,}")
        print(f"Hip range: {min_hip:,} - {max_hip:,}")
        print("=" * 100)


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Load the 2026 Keeneland September "
            "catalog into Supabase."
        )
    )

    parser.add_argument(
        "--truncate",
        action="store_true",
        help="Truncate the destination table before loading.",
    )

    parser.add_argument(
        "--preview-only",
        action="store_true",
        help="Validate and preview JSON without writing to Postgres.",
    )

    return parser.parse_args()


def main() -> None:
    args = parse_arguments()

    project_root = Path(__file__).resolve().parent.parent

    load_dotenv(project_root / ".env")

    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        raise ValueError(
            "DATABASE_URL is missing from .env"
        )

    json_path = (
        project_root
        / "data"
        / JSON_FILENAME
    )

    if not json_path.exists():
        raise FileNotFoundError(
            f"JSON not found: {json_path}"
        )

    horses = load_json(json_path)

    validate_horses(horses)
    preview_horses(horses)

    if args.preview_only:
        print()
        print("Preview only. Database was not modified.")
        return

    print()
    print("Connecting to Supabase Postgres...")

    connection = psycopg2.connect(database_url)

    try:
        print("Connected.")

        insert_horses(
            connection=connection,
            horses=horses,
            truncate=args.truncate,
        )

        verify_load(connection)

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()

    print()
    print("Keeneland catalog load complete.")


if __name__ == "__main__":
    main()