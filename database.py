import os

from pathlib import Path
from typing import Any

import pandas as pd
import psycopg2
import streamlit as st

from dotenv import load_dotenv


# ============================================================
# KEENELAND SEPTEMBER 2026
# ============================================================

HORSE_TABLE_NAME = "public.keeneland_september_2026"


# ============================================================
# PROJECT / DATABASE HELPERS
# ============================================================

def get_project_root() -> Path:
    """
    Return the root directory of the Streamlit project.
    """
    return Path(__file__).resolve().parent


def get_database_url() -> str:
    """
    Use Streamlit secrets in production and .env during
    local development.
    """

    try:
        database_url = st.secrets.get("DATABASE_URL")
    except Exception:
        database_url = None

    if database_url:
        return database_url

    project_root = get_project_root()

    load_dotenv(
        project_root / ".env"
    )

    database_url = os.getenv(
        "DATABASE_URL"
    )

    if not database_url:
        raise ValueError(
            "DATABASE_URL was not found in "
            "Streamlit secrets or .env."
        )

    return database_url


@st.cache_resource
def get_connection():
    """
    Create and cache the PostgreSQL connection.
    """

    return psycopg2.connect(
        get_database_url()
    )


# ============================================================
# NORMALIZATION HELPERS
# ============================================================

def normalize_json_list(
    value: Any,
) -> list:
    """
    Ensure JSONB list fields are returned as Python lists.
    """

    if isinstance(value, list):
        return value

    if value is None:
        return []

    return []


def normalize_text_column(
    dataframe: pd.DataFrame,
    column: str,
) -> None:
    """
    Normalize a text column in-place.

    If the column does not exist, create it as an
    empty-string column for downstream compatibility.
    """

    if column not in dataframe.columns:
        dataframe[column] = ""
        return

    dataframe[column] = (
        dataframe[column]
        .fillna("")
        .astype(str)
        .str.strip()
    )


def normalize_bool_column(
    dataframe: pd.DataFrame,
    column: str,
    default: bool = False,
) -> None:
    """
    Normalize a boolean column in-place.
    """

    if column not in dataframe.columns:
        dataframe[column] = default
        return

    dataframe[column] = (
        dataframe[column]
        .fillna(default)
        .astype(bool)
    )


def first_url(
    value: Any,
) -> str:
    """
    Return the first usable URL from a list.
    """

    if not isinstance(value, list):
        return ""

    for item in value:
        if item:
            text = str(item).strip()

            if text:
                return text

    return ""


# ============================================================
# HORSE DATA
# ============================================================

@st.cache_data(ttl=300)
def load_horses() -> pd.DataFrame:
    """
    Load the complete 2026 Keeneland September catalog.

    The database combines:

    - Auction Edge pedigree / analytical data
    - Keeneland live catalog information
    - Keeneland photography
    - Keeneland videos
    - consignor and barn data
    - supplements
    - out status
    - pedigree PDFs
    - future live sale results

    Compatibility columns are also generated for the
    existing Streamlit components.
    """

    query = f"""
        SELECT
            *
        FROM {HORSE_TABLE_NAME}
        ORDER BY
            sale_day,
            hip_number;
    """

    connection = get_connection()

    try:
        horses = pd.read_sql_query(
            query,
            connection,
        )

    except Exception:

        # Reconnect once if Streamlit's cached connection
        # has gone stale.

        get_connection.clear()

        connection = get_connection()

        horses = pd.read_sql_query(
            query,
            connection,
        )

    # ========================================================
    # CORE IDENTIFIERS
    # ========================================================

    identifier_columns = [
        "hip_number",
        "book_number",
        "sale_day",
    ]

    for column in identifier_columns:

        if column in horses.columns:

            horses[column] = pd.to_numeric(
                horses[column],
                errors="coerce",
            ).astype("Int64")

    # --------------------------------------------------------
    # Dates
    # --------------------------------------------------------

    if "sale_date" in horses.columns:

        horses["sale_date"] = pd.to_datetime(
            horses["sale_date"],
            errors="coerce",
        )

    if "foaling_date" in horses.columns:

        horses["foaling_date"] = pd.to_datetime(
            horses["foaling_date"],
            errors="coerce",
        )

    if "keeneland_last_synced_at" in horses.columns:

        horses["keeneland_last_synced_at"] = pd.to_datetime(
            horses["keeneland_last_synced_at"],
            errors="coerce",
            utc=True,
        )

    # ========================================================
    # TEXT FIELDS
    # ========================================================

    text_columns = [

        # ----------------------------------------------------
        # Core pedigree
        # ----------------------------------------------------

        "catalog_label",
        "sex",
        "sire",
        "dam",
        "broodmare_sire",
        "breeder",

        # ----------------------------------------------------
        # Auction Edge
        # ----------------------------------------------------

        "true_nicks_rating",
        "previous_sale_history",
        "dosage_profile",
        "weanling_2025_stats",
        "yearling_2025_stats",
        "two_year_old_2026_stats",
        "first_dam_summary",
        "first_dam_record",
        "nicking_summary",
        "raw_record",
        "source_pdf",

        # ----------------------------------------------------
        # Keeneland identifiers
        # ----------------------------------------------------

        "keeneland_node_id",
        "keeneland_entry_detail_id",

        # ----------------------------------------------------
        # Keeneland consignor / horse details
        # ----------------------------------------------------

        "consignor",
        "consignor_name",
        "consignor_email",
        "consignor_website",
        "barn",
        "color",
        "foaling_area",

        # ----------------------------------------------------
        # Keeneland URLs
        # ----------------------------------------------------

        "keeneland_pedigree_url",
        "pedigree_pdf_url",
        "updates_url",
        "main_image_url",
        "processed_image_url",

        # ----------------------------------------------------
        # Sale results
        # ----------------------------------------------------

        "buyer_name",
    ]

    for column in text_columns:

        normalize_text_column(
            horses,
            column,
        )

    # ========================================================
    # NUMERIC FIELDS
    # ========================================================

    numeric_columns = [
        "first_foals_year",
        "stud_fee_2026",
        "stud_fee_2024",
        "dosage_index",
        "center_of_distribution",
        "sale_price",
    ]

    for column in numeric_columns:

        if column in horses.columns:

            horses[column] = pd.to_numeric(
                horses[column],
                errors="coerce",
            )

    # ========================================================
    # BOOLEAN FIELDS
    # ========================================================

    boolean_columns = [
        "is_supplement",
        "is_out",
        "breeders_cup_eligible",
        "rna_indicator",
    ]

    for column in boolean_columns:

        normalize_bool_column(
            horses,
            column,
            default=False,
        )

    # ========================================================
    # JSONB FIELDS
    # ========================================================

    json_list_columns = [
        "first_dam_produce",
        "photo_urls",
        "video_urls",
    ]

    for column in json_list_columns:

        if column in horses.columns:

            horses[column] = (
                horses[column]
                .apply(
                    normalize_json_list
                )
            )

        else:

            horses[column] = [
                []
                for _ in range(
                    len(horses)
                )
            ]

    # ========================================================
    # MEDIA COMPATIBILITY LAYER
    # ========================================================
    #
    # Existing card/profile components expect:
    #
    # photo_url
    # photo_urls
    # photo_count
    # has_photo
    #
    # video_url
    # video_urls
    # has_video
    #
    # pdf_url
    # has_pdf
    #
    # These are now derived directly from the real Keeneland
    # columns rather than placeholders.
    # ========================================================

    # --------------------------------------------------------
    # PRIMARY PHOTO
    # --------------------------------------------------------

    horses["photo_url"] = (
        horses["main_image_url"]
        .fillna("")
        .astype(str)
        .str.strip()
    )

    # If Keeneland main_image_url is missing, fall back to
    # processed_image_url.

    missing_main_photo = (
        horses["photo_url"]
        .eq("")
    )

    horses.loc[
        missing_main_photo,
        "photo_url",
    ] = (
        horses.loc[
            missing_main_photo,
            "processed_image_url",
        ]
        .fillna("")
        .astype(str)
        .str.strip()
    )

    # Final fallback to photo_urls.

    missing_photo = (
        horses["photo_url"]
        .eq("")
    )

    horses.loc[
        missing_photo,
        "photo_url",
    ] = (
        horses.loc[
            missing_photo,
            "photo_urls",
        ]
        .apply(
            first_url
        )
    )

    # --------------------------------------------------------
    # PHOTO COUNT
    # --------------------------------------------------------

    horses["photo_count"] = (
        horses["photo_urls"]
        .apply(
            lambda value: (
                len(value)
                if isinstance(value, list)
                else 0
            )
        )
    )

    # Keeneland currently publishes its primary images in
    # main_image_url / processed_image_url even when
    # photo_urls is empty.

    primary_photo_exists = (
        horses["photo_url"]
        .ne("")
    )

    no_photo_count = (
        horses["photo_count"]
        .eq(0)
    )

    horses.loc[
        primary_photo_exists & no_photo_count,
        "photo_count",
    ] = 1

    # --------------------------------------------------------
    # HAS PHOTO
    # --------------------------------------------------------

    horses["has_photo"] = (
        horses["photo_url"]
        .ne("")
    )

    # --------------------------------------------------------
    # PRIMARY VIDEO
    # --------------------------------------------------------

    horses["video_url"] = (
        horses["video_urls"]
        .apply(
            first_url
        )
    )

    horses["has_video"] = (
        horses["video_url"]
        .ne("")
    )

    # --------------------------------------------------------
    # PEDIGREE PDF
    # --------------------------------------------------------

    horses["pdf_url"] = (
        horses["pedigree_pdf_url"]
        .fillna("")
        .astype(str)
        .str.strip()
    )

    missing_pdf = (
        horses["pdf_url"]
        .eq("")
    )

    horses.loc[
        missing_pdf,
        "pdf_url",
    ] = (
        horses.loc[
            missing_pdf,
            "keeneland_pedigree_url",
        ]
        .fillna("")
        .astype(str)
        .str.strip()
    )

    horses["has_pdf"] = (
        horses["pdf_url"]
        .ne("")
    )

    # ========================================================
    # KEENELAND SALE DETAILS
    # ========================================================

    # Existing components expect consignor_id.
    # Keeneland uses entry_detail_id instead of the structure
    # used in the previous sale app.

    horses["consignor_id"] = (
        horses[
            "keeneland_entry_detail_id"
        ]
    )

    horses["has_sale_details"] = (
        horses["consignor_name"].ne("")
        | horses["consignor"].ne("")
        | horses["barn"].ne("")
    )

    # ========================================================
    # SALE RESULT COMPATIBILITY LAYER
    # ========================================================

    # Existing application components reference "out"
    # rather than "is_out".

    horses["out"] = (
        horses["is_out"]
    )

    # Existing application components reference "purchaser"
    # rather than "buyer_name".

    horses["purchaser"] = (
        horses["buyer_name"]
    )

    # --------------------------------------------------------
    # Sale status
    # --------------------------------------------------------

    def determine_sale_status(
        row: pd.Series,
    ) -> str:
        """
        Generate the legacy sale_status value expected by
        the existing Streamlit components.
        """

        if bool(
            row["is_out"]
        ):
            return "OUT"

        if bool(
            row["rna_indicator"]
        ):
            return "RNA"

        sale_price = row[
            "sale_price"
        ]

        if pd.notna(
            sale_price
        ):

            try:

                if float(
                    sale_price
                ) > 0:

                    return "SOLD"

            except (
                TypeError,
                ValueError,
            ):
                pass

        return "PENDING"

    horses["sale_status"] = (
        horses.apply(
            determine_sale_status,
            axis=1,
        )
    )

    # --------------------------------------------------------
    # Result metadata placeholders
    # --------------------------------------------------------

    horses["out_date"] = ""

    if "keeneland_last_synced_at" in horses.columns:

        horses["result_last_updated"] = (
            horses[
                "keeneland_last_synced_at"
            ]
        )

    else:

        horses[
            "result_last_updated"
        ] = pd.NaT

    # --------------------------------------------------------
    # WPT purchase tracking
    # --------------------------------------------------------

    horses["wpt_purchase"] = False

    # ========================================================
    # AI SUMMARY COMPATIBILITY
    # ========================================================
    #
    # AI summaries are not connected yet.
    #
    # These fields remain so the existing horse profile can
    # continue operating without KeyErrors.
    # ========================================================

    horses["executive_summary"] = ""

    horses["key_highlights"] = [
        []
        for _ in range(
            len(horses)
        )
    ]

    horses["watch_items"] = [
        []
        for _ in range(
            len(horses)
        )
    ]

    horses[
        "ai_prompt_version"
    ] = ""

    horses[
        "ai_model_name"
    ] = ""

    horses[
        "ai_generated_at"
    ] = pd.NaT

    horses[
        "ai_updated_at"
    ] = pd.NaT

    horses[
        "has_ai_summary"
    ] = False

    # ========================================================
    # FINAL ORDERING
    # ========================================================

    horses = (
        horses
        .sort_values(
            [
                "sale_day",
                "hip_number",
            ]
        )
        .reset_index(
            drop=True
        )
    )

    return horses


# ============================================================
# SIMPLE DATABASE HEALTH CHECK
# ============================================================

def get_catalog_stats() -> dict:
    """
    Return basic Keeneland catalog statistics.

    Useful for testing the database connection before
    rendering the full Streamlit application.
    """

    query = f"""
        SELECT
            COUNT(*) AS horse_count,

            COUNT(
                DISTINCT hip_number
            ) AS unique_hips,

            MIN(
                hip_number
            ) AS min_hip,

            MAX(
                hip_number
            ) AS max_hip,

            COUNT(
                DISTINCT book_number
            ) AS book_count,

            COUNT(
                DISTINCT sale_day
            ) AS sale_day_count,

            COUNT(*) FILTER (
                WHERE
                    COALESCE(
                        main_image_url,
                        ''
                    ) <> ''
            ) AS photo_count,

            COUNT(*) FILTER (
                WHERE
                    jsonb_array_length(
                        video_urls
                    ) > 0
            ) AS video_count,

            COUNT(*) FILTER (
                WHERE
                    is_supplement = TRUE
            ) AS supplement_count,

            COUNT(*) FILTER (
                WHERE
                    is_out = TRUE
            ) AS out_count,

            COUNT(*) FILTER (
                WHERE
                    COALESCE(
                        consignor_name,
                        ''
                    ) <> ''
            ) AS consignor_count

        FROM {HORSE_TABLE_NAME};
    """

    connection = get_connection()

    try:

        stats = pd.read_sql_query(
            query,
            connection,
        )

    except Exception:

        get_connection.clear()

        connection = get_connection()

        stats = pd.read_sql_query(
            query,
            connection,
        )

    if stats.empty:
        return {}

    return (
        stats
        .iloc[0]
        .to_dict()
    )