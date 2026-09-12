import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import psycopg2
import requests
from dotenv import load_dotenv
from psycopg2.extras import Json, execute_values


# =========================================================
# CONFIGURATION
# =========================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = PROJECT_ROOT / ".env"
DATA_DIR = PROJECT_ROOT / "data"

KEENELAND_URL = (
    "https://catalog-backend.keeneland.com/"
    "sites/default/files/json_hde/sale_data_132.json"
)

RAW_OUTPUT_PATH = DATA_DIR / "keeneland_sale_data_132.json"

TABLE_NAME = "public.keeneland_september_2026"

# Smaller database batches are intentionally used here.
# Supabase connections can occasionally drop during large,
# long-running SSL transactions.
BATCH_SIZE = 100
MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 2


# Official 2026 Keeneland September session dates.
# September 18 is a dark day.
SESSION_DATES = {
    1: "2026-09-14",
    2: "2026-09-15",
    3: "2026-09-16",
    4: "2026-09-17",
    5: "2026-09-19",
    6: "2026-09-20",
    7: "2026-09-21",
    8: "2026-09-22",
    9: "2026-09-23",
    10: "2026-09-24",
    11: "2026-09-25",
    12: "2026-09-26",
}


# =========================================================
# BASIC CLEANING
# =========================================================

def clean_text(value):
    if value is None:
        return None

    value = str(value).strip()

    if not value:
        return None

    return value


def clean_int(value):
    value = clean_text(value)

    if value is None:
        return None

    try:
        return int(value.replace(",", ""))
    except (TypeError, ValueError):
        return None


def clean_numeric(value):
    value = clean_text(value)

    if value is None:
        return None

    value = (
        value
        .replace("$", "")
        .replace(",", "")
        .strip()
    )

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def yes_no_to_bool(value):
    value = clean_text(value)

    if value is None:
        return False

    return value.upper() in {
        "Y",
        "YES",
        "1",
        "TRUE",
    }


def parse_date(value):
    value = clean_text(value)

    if value is None:
        return None

    for fmt in (
        "%m/%d/%Y",
        "%Y-%m-%d",
    ):
        try:
            return datetime.strptime(
                value,
                fmt,
            ).date()
        except ValueError:
            continue

    return None


def get_sale_date(session):
    date_string = SESSION_DATES.get(session)

    if not date_string:
        return None

    return datetime.strptime(
        date_string,
        "%Y-%m-%d",
    ).date()


def ensure_list(value):
    if value is None:
        return []

    if isinstance(value, list):
        return [
            item
            for item in value
            if item
        ]

    if isinstance(value, str):
        value = value.strip()

        if value:
            return [value]

    return []


# =========================================================
# MEDIA
# =========================================================

def build_photo_urls(record):
    urls = []

    # Keeneland is currently populating these two fields.
    for field_name in (
        "field_main_image",
        "field_processed_image",
    ):
        url = clean_text(
            record.get(field_name)
        )

        if url and url not in urls:
            urls.append(url)

    # Keep support for field_image in case Keeneland
    # begins populating it later.
    field_images = ensure_list(
        record.get("field_image")
    )

    for item in field_images:

        if isinstance(item, str):
            url = clean_text(item)

        elif isinstance(item, dict):
            url = clean_text(
                item.get("url")
                or item.get("uri")
                or item.get("src")
            )

        else:
            url = None

        if url and url not in urls:
            urls.append(url)

    return urls


def build_video_urls(record):
    urls = []

    for item in ensure_list(
        record.get("field_other_videos")
    ):
        if isinstance(item, str):
            url = clean_text(item)

        elif isinstance(item, dict):
            url = clean_text(
                item.get("url")
                or item.get("uri")
                or item.get("src")
            )

        else:
            url = None

        if url and url not in urls:
            urls.append(url)

    return urls


# =========================================================
# KEENELAND DOWNLOAD
# =========================================================

def fetch_keeneland_data():
    print("Downloading Keeneland catalog...")
    print(KEENELAND_URL)

    response = requests.get(
        KEENELAND_URL,
        timeout=60,
        headers={
            "User-Agent": (
                "Mozilla/5.0 "
                "WPT Keeneland September Catalog Sync"
            )
        },
    )

    response.raise_for_status()

    data = response.json()

    if not isinstance(data, dict):
        raise ValueError(
            "Expected Keeneland response to be a dict, "
            f"got {type(data).__name__}"
        )

    DATA_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    with RAW_OUTPUT_PATH.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            data,
            file,
            indent=2,
            ensure_ascii=False,
        )

    print(
        f"Downloaded {len(data):,} "
        "Keeneland records."
    )

    print(
        f"Saved raw JSON to: "
        f"{RAW_OUTPUT_PATH}"
    )

    return data


# =========================================================
# TRANSFORM
# =========================================================

def transform_record(record):
    hip_number = clean_int(
        record.get("field_hip_number")
    )

    if hip_number is None:
        return None

    book_number = clean_int(
        record.get("field_book")
    )

    session = clean_int(
        record.get("field_session")
    )

    sale_date = get_sale_date(session)

    if book_number is None:
        raise ValueError(
            f"Hip {hip_number} has no valid book number."
        )

    if session is None:
        raise ValueError(
            f"Hip {hip_number} has no valid session."
        )

    if sale_date is None:
        raise ValueError(
            f"Hip {hip_number} has unexpected "
            f"session {session}."
        )

    photo_urls = build_photo_urls(record)
    video_urls = build_video_urls(record)

    return {
        # Core required fields
        "hip_number": hip_number,
        "book_number": book_number,
        "sale_day": session,
        "sale_date": sale_date,

        # Basic catalog fields
        "catalog_label": clean_text(
            record.get("title")
        ),
        "sex": clean_text(
            record.get("field_sex")
        ),
        "sire": clean_text(
            record.get("field_sire")
        ),
        "dam": clean_text(
            record.get("field_dam")
        ),
        "broodmare_sire": clean_text(
            record.get(
                "field_broodmare_sire"
            )
        ),

        # Keeneland IDs
        "keeneland_node_id": clean_text(
            record.get("node_id")
        ),
        "keeneland_entry_detail_id": clean_text(
            record.get(
                "field_entry_detail_id"
            )
        ),

        # Consignor
        "consignor": clean_text(
            record.get("field_consignor")
        ),
        "consignor_name": clean_text(
            record.get(
                "field_consignor_name"
            )
        ),
        "consignor_email": clean_text(
            record.get(
                "field_consignor_email"
            )
        ),
        "consignor_website": clean_text(
            record.get(
                "field_consignor_website"
            )
        ),
        "barn": clean_text(
            record.get("field_barn_text")
        ),

        # Live status
        "is_supplement": yes_no_to_bool(
            record.get(
                "field_supplement_indicator"
            )
        ),
        "is_out": yes_no_to_bool(
            record.get("field_out")
        ),

        # Horse details
        "color": clean_text(
            record.get("field_color")
        ),
        "foaling_date": parse_date(
            record.get(
                "field_foaling_date"
            )
        ),
        "foaling_area": clean_text(
            record.get(
                "field_foaling_area"
            )
        ),
        "breeders_cup_eligible": (
            yes_no_to_bool(
                record.get(
                    "field_breeders_cup_eligible"
                )
            )
        ),

        # Keeneland links
        "keeneland_pedigree_url": clean_text(
            record.get(
                "field_keeneland_pedigree"
            )
        ),
        "pedigree_pdf_url": clean_text(
            record.get("field_pedigree")
        ),
        "updates_url": clean_text(
            record.get("field_updates")
        ),

        # Media
        "main_image_url": clean_text(
            record.get(
                "field_main_image"
            )
        ),
        "processed_image_url": clean_text(
            record.get(
                "field_processed_image"
            )
        ),
        "photo_urls": photo_urls,
        "video_urls": video_urls,

        # Sale result
        "sale_price": clean_numeric(
            record.get("field_sale_price")
            or record.get("field_price")
        ),
        "buyer_name": clean_text(
            record.get("field_buyer_name")
            or record.get("field_buyer")
        ),
        "rna_indicator": yes_no_to_bool(
            record.get(
                "field_rna_indicator"
            )
        ),

        # Sync metadata
        "keeneland_last_synced_at": (
            datetime.now(timezone.utc)
        ),
    }


def transform_catalog(raw_data):
    records = []

    for raw_record in raw_data.values():
        transformed = transform_record(
            raw_record
        )

        if transformed is not None:
            records.append(transformed)

    records.sort(
        key=lambda record: record["hip_number"]
    )

    return records


# =========================================================
# DATABASE CONNECTION
# =========================================================

def get_database_url():
    load_dotenv(ENV_PATH)

    database_url = os.getenv(
        "DATABASE_URL"
    )

    if not database_url:
        raise RuntimeError(
            "DATABASE_URL was not found in .env"
        )

    return database_url


def get_connection():
    return psycopg2.connect(
        get_database_url(),
        connect_timeout=20,
    )


def safe_close(conn):
    if conn is None:
        return

    try:
        conn.close()
    except Exception:
        pass


def safe_rollback(conn):
    if conn is None:
        return

    try:
        if not conn.closed:
            conn.rollback()
    except Exception:
        pass


# =========================================================
# UPSERT SQL
# =========================================================

COLUMNS = [
    "hip_number",
    "book_number",
    "sale_day",
    "sale_date",

    "catalog_label",
    "sex",
    "sire",
    "dam",
    "broodmare_sire",

    "keeneland_node_id",
    "keeneland_entry_detail_id",

    "consignor",
    "consignor_name",
    "consignor_email",
    "consignor_website",
    "barn",

    "is_supplement",
    "is_out",

    "color",
    "foaling_date",
    "foaling_area",
    "breeders_cup_eligible",

    "keeneland_pedigree_url",
    "pedigree_pdf_url",
    "updates_url",

    "main_image_url",
    "processed_image_url",
    "photo_urls",
    "video_urls",

    "sale_price",
    "buyer_name",
    "rna_indicator",

    "keeneland_last_synced_at",
]


def build_upsert_sql():
    insert_columns = ", ".join(
        COLUMNS
    )

    update_columns = [
        column
        for column in COLUMNS
        if column != "hip_number"
    ]

    update_clause = ",\n".join(
        (
            f"{column} = "
            f"EXCLUDED.{column}"
        )
        for column in update_columns
    )

    return f"""
        INSERT INTO {TABLE_NAME} (
            {insert_columns}
        )
        VALUES %s

        ON CONFLICT (hip_number)
        DO UPDATE SET
            {update_clause},
            updated_at = NOW()
    """


UPSERT_SQL = build_upsert_sql()


def record_to_tuple(record):
    row = []

    for column in COLUMNS:
        value = record.get(column)

        if column in {
            "photo_urls",
            "video_urls",
        }:
            value = Json(
                value or []
            )

        row.append(value)

    return tuple(row)


# =========================================================
# BATCH UPSERT
# =========================================================

def upsert_single_batch(
    batch,
    batch_number,
    total_batches,
):
    first_hip = batch[0]["hip_number"]
    last_hip = batch[-1]["hip_number"]

    for attempt in range(
        1,
        MAX_RETRIES + 1,
    ):
        conn = None

        try:
            conn = get_connection()

            values = [
                record_to_tuple(record)
                for record in batch
            ]

            with conn.cursor() as cur:
                execute_values(
                    cur,
                    UPSERT_SQL,
                    values,
                    page_size=len(values),
                )

            conn.commit()

            print(
                f"Batch {batch_number}/{total_batches} "
                f"complete "
                f"(Hips {first_hip}-{last_hip})"
            )

            return

        except (
            psycopg2.OperationalError,
            psycopg2.InterfaceError,
        ) as exc:

            safe_rollback(conn)

            print(
                f"Batch {batch_number}/{total_batches} "
                f"connection error "
                f"on attempt {attempt}/{MAX_RETRIES}: "
                f"{exc}"
            )

            if attempt >= MAX_RETRIES:
                raise

            time.sleep(
                RETRY_DELAY_SECONDS * attempt
            )

        except Exception:
            safe_rollback(conn)
            raise

        finally:
            safe_close(conn)


def upsert_catalog(records):
    total_records = len(records)

    total_batches = (
        total_records + BATCH_SIZE - 1
    ) // BATCH_SIZE

    print()
    print(
        f"Writing {total_records:,} records "
        f"in {total_batches} batches "
        f"of up to {BATCH_SIZE}..."
    )
    print()

    for batch_index in range(
        total_batches
    ):
        start = (
            batch_index * BATCH_SIZE
        )

        end = (
            start + BATCH_SIZE
        )

        batch = records[
            start:end
        ]

        upsert_single_batch(
            batch=batch,
            batch_number=(
                batch_index + 1
            ),
            total_batches=(
                total_batches
            ),
        )


# =========================================================
# VERIFICATION
# =========================================================

def verify_database():
    conn = None

    try:
        conn = get_connection()

        with conn.cursor() as cur:

            cur.execute(
                f"""
                SELECT
                    COUNT(*),

                    COUNT(*) FILTER (
                        WHERE is_supplement = TRUE
                    ),

                    COUNT(*) FILTER (
                        WHERE is_out = TRUE
                    ),

                    COUNT(*) FILTER (
                        WHERE main_image_url
                        IS NOT NULL
                    ),

                    COUNT(*) FILTER (
                        WHERE processed_image_url
                        IS NOT NULL
                    ),

                    COUNT(*) FILTER (
                        WHERE
                        jsonb_array_length(
                            video_urls
                        ) > 0
                    ),

                    COUNT(*) FILTER (
                        WHERE consignor_name
                        IS NOT NULL
                    )

                FROM {TABLE_NAME}
                """
            )

            stats = cur.fetchone()

            cur.execute(
                f"""
                SELECT
                    hip_number,
                    sire,
                    dam,
                    is_supplement,
                    book_number,
                    sale_day,
                    sale_date

                FROM {TABLE_NAME}

                WHERE hip_number IN (
                    182,
                    183,
                    184,
                    190,
                    374,
                    375,
                    376,
                    377
                )

                ORDER BY hip_number
                """
            )

            keeneland_only = (
                cur.fetchall()
            )

            cur.execute(
                f"""
                SELECT
                    hip_number,
                    main_image_url,
                    processed_image_url,
                    video_urls

                FROM {TABLE_NAME}

                WHERE hip_number = 3
                """
            )

            hip_3 = cur.fetchone()

        print()
        print("DATABASE VERIFICATION")
        print("---------------------")

        print(
            f"Total horses:       "
            f"{stats[0]:,}"
        )
        print(
            f"Supplements:        "
            f"{stats[1]:,}"
        )
        print(
            f"Outs:               "
            f"{stats[2]:,}"
        )
        print(
            f"Main images:        "
            f"{stats[3]:,}"
        )
        print(
            f"Processed images:   "
            f"{stats[4]:,}"
        )
        print(
            f"Videos:             "
            f"{stats[5]:,}"
        )
        print(
            f"With consignor:     "
            f"{stats[6]:,}"
        )

        print()
        print("KEENELAND-ONLY HIPS")
        print("-------------------")

        for row in keeneland_only:
            (
                hip,
                sire,
                dam,
                supplement,
                book,
                session,
                sale_date,
            ) = row

            print(
                f"Hip {hip}: "
                f"{sire} x {dam} | "
                f"Book {book} | "
                f"Session {session} | "
                f"{sale_date} | "
                f"Supplement={supplement}"
            )

        print()
        print("HIP 3 MEDIA CHECK")
        print("-----------------")

        if hip_3:
            print(
                f"Main image: "
                f"{hip_3[1]}"
            )
            print(
                f"Processed image: "
                f"{hip_3[2]}"
            )
            print(
                f"Videos: "
                f"{hip_3[3]}"
            )

    finally:
        safe_close(conn)


# =========================================================
# MAIN
# =========================================================

def main():
    raw_data = (
        fetch_keeneland_data()
    )

    records = (
        transform_catalog(
            raw_data
        )
    )

    print()
    print(
        f"Transformed "
        f"{len(records):,} records."
    )

    supplements = sum(
        record["is_supplement"]
        for record in records
    )

    outs = sum(
        record["is_out"]
        for record in records
    )

    photos = sum(
        bool(
            record["main_image_url"]
        )
        for record in records
    )

    videos = sum(
        bool(
            record["video_urls"]
        )
        for record in records
    )

    print(
        f"Supplements: "
        f"{supplements:,}"
    )
    print(
        f"Outs:        "
        f"{outs:,}"
    )
    print(
        f"Photos:      "
        f"{photos:,}"
    )
    print(
        f"Videos:      "
        f"{videos:,}"
    )

    # ---------------------------------------------------------
    # PHOTO DEBUGGING
    # ---------------------------------------------------------
    # Show exactly which hips Keeneland's JSON currently
    # provides image URLs for. This does not change any data;
    # it only prints diagnostics before the Postgres sync.
    hips_with_photos = []
    hips_without_photos = []

    print()
    print("PHOTO CHECK")
    print("-----------")

    for record in records:
        hip = record["hip_number"]
        main_image = record.get("main_image_url")
        processed_image = record.get("processed_image_url")
        photo_urls = record.get("photo_urls") or []

        if photo_urls:
            hips_with_photos.append(hip)
            print(
                f"PHOTO FOUND | Hip {hip} | "
                f"main={main_image} | "
                f"processed={processed_image} | "
                f"all={photo_urls}"
            )
        else:
            hips_without_photos.append(hip)
            print(f"NO PHOTO    | Hip {hip}")

    print()
    print("PHOTO SUMMARY")
    print("-------------")
    print(
        f"Horses with photos:    "
        f"{len(hips_with_photos):,}"
    )
    print(
        f"Horses without photos: "
        f"{len(hips_without_photos):,}"
    )

    print()
    print("HIP 2 SOURCE CHECK")
    print("------------------")

    hip_2 = next(
        (
            record
            for record in records
            if record["hip_number"] == 2
        ),
        None,
    )

    if hip_2:
        print(
            f"Main image:      "
            f"{hip_2.get('main_image_url')}"
        )
        print(
            f"Processed image: "
            f"{hip_2.get('processed_image_url')}"
        )
        print(
            f"Photo URLs:      "
            f"{hip_2.get('photo_urls')}"
        )
        print(
            f"Video URLs:      "
            f"{hip_2.get('video_urls')}"
        )
    else:
        print("Hip 2 was not present in the Keeneland feed.")

    print()
    print(
        "Starting Postgres sync..."
    )

    upsert_catalog(
        records
    )

    print()
    print(
        "All batches complete."
    )

    verify_database()

    print()
    print(
        "Keeneland catalog sync complete."
    )


if __name__ == "__main__":
    main()