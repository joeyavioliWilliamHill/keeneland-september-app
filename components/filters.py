from typing import Any

import pandas as pd
import streamlit as st


# ============================================================
# FILTER STATE
# ============================================================

FILTER_STATE_KEYS = [
    "filter_search",
    "filter_books",
    "filter_sale_days",
    "filter_hip_range",
    "filter_photo_only",
    "filter_wpt_shortlist",
    "filter_sexes",
    "filter_sires",
    "filter_broodmare_sires",
    "filter_breeders",
    "filter_true_nicks",
    "filter_first_foals_years",
    "filter_stud_fee_range",
    "filter_dosage_range",
]


# ============================================================
# KEENELAND SALE STRUCTURE
# ============================================================

SALE_DAY_LABELS = {
    1: "Day 1 · Sep 14 · Hips 1–181",
    2: "Day 2 · Sep 15 · Hips 191–373",
    3: "Day 3 · Sep 16 · Hips 381–757",
    4: "Day 4 · Sep 17 · Hips 758–1136",
    5: "Day 5 · Sep 19 · Hips 1137–1552",
    6: "Day 6 · Sep 20 · Hips 1553–1975",
    7: "Day 7 · Sep 21 · Hips 1976–2392",
    8: "Day 8 · Sep 22 · Hips 2393–2815",
    9: "Day 9 · Sep 23 · Hips 2816–3242",
    10: "Day 10 · Sep 24 · Hips 3243–3673",
    11: "Day 11 · Sep 25 · Hips 3674–4169",
    12: "Day 12 · Sep 26 · Hips 4170–4650",
}


BOOK_LABELS = {
    1: "Book 1 · Sep 14–15",
    2: "Book 2 · Sep 16–17",
    3: "Book 3 · Sep 19–20",
    4: "Book 4 · Sep 21–22",
    5: "Book 5 · Sep 23–24",
    6: "Book 6 · Sep 25–26",
}


# ============================================================
# WPT SHORTLIST
# ============================================================

WPT_SHORTLIST_HIPS = {
    1, 25, 26, 28, 36, 39, 47, 49, 52, 64,
    68, 83, 88, 94, 98, 102, 104, 106, 111, 115,
    116, 118, 122, 129, 140, 148, 149, 151, 154, 156,
    160, 162, 176, 178, 180, 181, 184,
}


# ============================================================
# HELPERS
# ============================================================

def sorted_options(series: pd.Series) -> list[Any]:
    """
    Return unique, non-null values in stable sorted order.
    """
    values = (
        series
        .dropna()
        .unique()
        .tolist()
    )

    try:
        return sorted(values)

    except TypeError:
        return sorted(
            values,
            key=lambda value: str(value),
        )


def safe_numeric_range(
    series: pd.Series,
    default_min: float = 0.0,
    default_max: float = 1.0,
) -> tuple[float, float]:
    """
    Return a safe numeric minimum and maximum for a slider.
    """
    numeric_values = pd.to_numeric(
        series,
        errors="coerce",
    ).dropna()

    if numeric_values.empty:
        return default_min, default_max

    minimum = float(numeric_values.min())
    maximum = float(numeric_values.max())

    if minimum == maximum:
        maximum = minimum + 1.0

    return minimum, maximum


def sidebar_section(title: str) -> None:
    """
    Render a branded sidebar section label.
    """
    st.sidebar.markdown(
        f"""
        {title}
        """,
        unsafe_allow_html=True,
    )


def render_sidebar_brand() -> None:
    """
    Render Keeneland catalog branding.
    """
    st.sidebar.markdown(
        """
        West Point Thoroughbreds

        Keeneland September Yearlings

        2026 Keeneland September Yearling Sale
        """,
        unsafe_allow_html=True,
    )


def reset_filters() -> None:
    """
    Reset only filter-related session state.

    This avoids clearing selected horses, page routing,
    authentication, and unrelated application state.
    """
    for key in FILTER_STATE_KEYS:
        st.session_state.pop(
            key,
            None,
        )

    st.session_state["catalog_page"] = 1


def format_book(book_number: Any) -> str:
    """
    Format a Keeneland book number for display.
    """
    try:
        book_number = int(book_number)
    except (TypeError, ValueError):
        return str(book_number)

    return BOOK_LABELS.get(
        book_number,
        f"Book {book_number}",
    )


def format_sale_day(sale_day: Any) -> str:
    """
    Format a Keeneland sale day for display.
    """
    try:
        sale_day = int(sale_day)
    except (TypeError, ValueError):
        return str(sale_day)

    return SALE_DAY_LABELS.get(
        sale_day,
        f"Day {sale_day}",
    )


# ============================================================
# RENDER FILTERS
# ============================================================

def render_filters(
    horses: pd.DataFrame,
) -> dict:
    """
    Render Keeneland sidebar controls and return
    the selected filters.
    """
    render_sidebar_brand()

    # --------------------------------------------------------
    # Search
    # --------------------------------------------------------

    sidebar_section("Search")

    search_text = st.sidebar.text_input(
        "Search catalog",
        placeholder=(
            "Hip, sire, dam, broodmare sire, breeder..."
        ),
        key="filter_search",
    )

    # --------------------------------------------------------
    # WPT Shortlist
    # --------------------------------------------------------

    sidebar_section("West Point")

    wpt_shortlist_only = st.sidebar.toggle(
        f"WPT Shortlist · {len(WPT_SHORTLIST_HIPS)} horses",
        value=False,
        key="filter_wpt_shortlist",
        help="Show only the current West Point shortlist.",
    )

    # --------------------------------------------------------
    # Keeneland Sale Structure
    # --------------------------------------------------------

    sidebar_section("Keeneland Sale")

    book_options = sorted_options(
        horses["book_number"]
    )

    books = st.sidebar.multiselect(
        "Book",
        options=book_options,
        format_func=format_book,
        key="filter_books",
    )

    sale_day_options = sorted_options(
        horses["sale_day"]
    )

    sale_days = st.sidebar.multiselect(
        "Sale day",
        options=sale_day_options,
        format_func=format_sale_day,
        key="filter_sale_days",
    )

    hip_values = pd.to_numeric(
        horses["hip_number"],
        errors="coerce",
    ).dropna()

    hip_min = int(
        hip_values.min()
    )

    hip_max = int(
        hip_values.max()
    )

    hip_range = st.sidebar.slider(
        "Hip number range",
        min_value=hip_min,
        max_value=hip_max,
        value=(
            hip_min,
            hip_max,
        ),
        key="filter_hip_range",
    )

    # --------------------------------------------------------
    # Media
    # --------------------------------------------------------

    sidebar_section("Media")

    photo_only = st.sidebar.toggle(
        "Show horses with photos only",
        value=False,
        key="filter_photo_only",
        help=(
            "This will become useful once Keeneland "
            "photography is connected."
        ),
    )

    # --------------------------------------------------------
    # Pedigree
    # --------------------------------------------------------

    sidebar_section("Pedigree")

    sexes = st.sidebar.multiselect(
        "Sex",
        options=sorted_options(
            horses["sex"]
        ),
        key="filter_sexes",
    )

    sires = st.sidebar.multiselect(
        "Sire",
        options=sorted_options(
            horses["sire"]
        ),
        key="filter_sires",
    )

    broodmare_sires = st.sidebar.multiselect(
        "Broodmare sire",
        options=sorted_options(
            horses["broodmare_sire"]
        ),
        key="filter_broodmare_sires",
    )

    breeders = st.sidebar.multiselect(
        "Breeder",
        options=sorted_options(
            horses["breeder"]
        ),
        key="filter_breeders",
    )

    true_nicks = st.sidebar.multiselect(
        "TrueNicks rating",
        options=sorted_options(
            horses["true_nicks_rating"]
        ),
        key="filter_true_nicks",
    )

    first_foals_year_options = sorted(
        pd.to_numeric(
            horses["first_foals_year"],
            errors="coerce",
        )
        .dropna()
        .astype(int)
        .unique()
        .tolist(),
        reverse=True,
    )

    first_foals_years = st.sidebar.multiselect(
        "First foals year",
        options=first_foals_year_options,
        key="filter_first_foals_years",
    )

    # --------------------------------------------------------
    # Commercial
    # --------------------------------------------------------

    sidebar_section("Commercial")

    stud_fee_min, stud_fee_max = (
        safe_numeric_range(
            horses["stud_fee_2026"]
        )
    )

    stud_fee_step = 5000

    if (
        stud_fee_max - stud_fee_min
        < stud_fee_step
    ):
        stud_fee_step = 1000

    stud_fee_range = st.sidebar.slider(
        "2026 stud fee",
        min_value=int(stud_fee_min),
        max_value=int(stud_fee_max),
        value=(
            int(stud_fee_min),
            int(stud_fee_max),
        ),
        step=stud_fee_step,
        format="$%d",
        key="filter_stud_fee_range",
    )

    # --------------------------------------------------------
    # Dosage
    # --------------------------------------------------------

    sidebar_section("Dosage")

    dosage_min, dosage_max = (
        safe_numeric_range(
            horses["dosage_index"]
        )
    )

    dosage_range = st.sidebar.slider(
        "Dosage index",
        min_value=float(dosage_min),
        max_value=float(dosage_max),
        value=(
            float(dosage_min),
            float(dosage_max),
        ),
        step=0.05,
        key="filter_dosage_range",
    )

    # --------------------------------------------------------
    # Reset
    # --------------------------------------------------------

    st.sidebar.markdown(
        "<br>",
        unsafe_allow_html=True,
    )

    if st.sidebar.button(
        "Reset all filters",
        use_container_width=True,
        key="reset_catalog_filters",
    ):
        reset_filters()
        st.rerun()

    return {
        "search_text": (
            search_text.strip()
        ),
        "books": books,
        "sale_days": sale_days,
        "hip_range": hip_range,
        "photo_only": photo_only,
        "wpt_shortlist_only": wpt_shortlist_only,
        "sexes": sexes,
        "sires": sires,
        "broodmare_sires": (
            broodmare_sires
        ),
        "breeders": breeders,
        "true_nicks": true_nicks,
        "first_foals_years": (
            first_foals_years
        ),
        "stud_fee_range": (
            stud_fee_range
        ),
        "dosage_range": (
            dosage_range
        ),
    }


# ============================================================
# APPLY FILTERS
# ============================================================

def apply_filters(
    horses: pd.DataFrame,
    filters: dict,
) -> pd.DataFrame:
    """
    Apply all Keeneland sidebar filters to the catalog.
    """
    filtered = horses.copy()

    # --------------------------------------------------------
    # Search
    # --------------------------------------------------------

    search_text = (
        filters
        .get(
            "search_text",
            "",
        )
        .lower()
    )

    if search_text:
        searchable_columns = [
            "hip_number",
            "catalog_label",
            "sire",
            "dam",
            "broodmare_sire",
            "breeder",
            "first_dam_summary",
            "first_dam_record",
            "nicking_summary",
        ]

        search_mask = pd.Series(
            False,
            index=filtered.index,
        )

        for column in searchable_columns:
            if column not in filtered.columns:
                continue

            search_mask = (
                search_mask
                | (
                    filtered[column]
                    .fillna("")
                    .astype(str)
                    .str.lower()
                    .str.contains(
                        search_text,
                        regex=False,
                    )
                )
            )

        filtered = filtered[
            search_mask
        ]

    # --------------------------------------------------------
    # WPT Shortlist
    # --------------------------------------------------------

    if filters.get(
        "wpt_shortlist_only",
        False,
    ):
        hip_numbers = pd.to_numeric(
            filtered["hip_number"],
            errors="coerce",
        )
        filtered = filtered[
            hip_numbers.isin(WPT_SHORTLIST_HIPS)
        ]

    # --------------------------------------------------------
    # Book
    # --------------------------------------------------------

    selected_books = filters.get(
        "books",
        [],
    )

    if selected_books:
        filtered = filtered[
            filtered["book_number"].isin(
                selected_books
            )
        ]

    # --------------------------------------------------------
    # Sale Day
    # --------------------------------------------------------

    selected_sale_days = filters.get(
        "sale_days",
        [],
    )

    if selected_sale_days:
        filtered = filtered[
            filtered["sale_day"].isin(
                selected_sale_days
            )
        ]

    # --------------------------------------------------------
    # Hip Range
    # --------------------------------------------------------

    hip_low, hip_high = filters[
        "hip_range"
    ]

    hip_numbers = pd.to_numeric(
        filtered["hip_number"],
        errors="coerce",
    )

    filtered = filtered[
        hip_numbers.between(
            hip_low,
            hip_high,
        )
    ]

    # --------------------------------------------------------
    # Photos
    # --------------------------------------------------------

    if filters.get(
        "photo_only",
        False,
    ):
        if "has_photo" in filtered.columns:
            filtered = filtered[
                filtered[
                    "has_photo"
                ].fillna(False)
            ]

        elif "photo_url" in filtered.columns:
            photo_urls = (
                filtered["photo_url"]
                .fillna("")
                .astype(str)
                .str.strip()
            )

            filtered = filtered[
                photo_urls.ne("")
            ]

    # --------------------------------------------------------
    # Categorical pedigree filters
    # --------------------------------------------------------

    categorical_filters = {
        "sex": filters.get(
            "sexes",
            [],
        ),
        "sire": filters.get(
            "sires",
            [],
        ),
        "broodmare_sire": filters.get(
            "broodmare_sires",
            [],
        ),
        "breeder": filters.get(
            "breeders",
            [],
        ),
        "true_nicks_rating": filters.get(
            "true_nicks",
            [],
        ),
        "first_foals_year": filters.get(
            "first_foals_years",
            [],
        ),
    }

    for (
        column,
        selected_values,
    ) in categorical_filters.items():

        if (
            selected_values
            and column in filtered.columns
        ):
            filtered = filtered[
                filtered[column].isin(
                    selected_values
                )
            ]

    # --------------------------------------------------------
    # Stud Fee
    # --------------------------------------------------------

    (
        stud_fee_low,
        stud_fee_high,
    ) = filters["stud_fee_range"]

    stud_fee = pd.to_numeric(
        filtered["stud_fee_2026"],
        errors="coerce",
    )

    # Keep missing stud fees rather than accidentally
    # excluding legitimate catalog horses.
    filtered = filtered[
        stud_fee.isna()
        | stud_fee.between(
            stud_fee_low,
            stud_fee_high,
        )
    ]

    # --------------------------------------------------------
    # Dosage Index
    # --------------------------------------------------------

    (
        dosage_low,
        dosage_high,
    ) = filters["dosage_range"]

    dosage = pd.to_numeric(
        filtered["dosage_index"],
        errors="coerce",
    )

    filtered = filtered[
        dosage.isna()
        | dosage.between(
            dosage_low,
            dosage_high,
        )
    ]

    # --------------------------------------------------------
    # Final order
    # --------------------------------------------------------

    return (
        filtered
        .sort_values(
            [
                "sale_day",
                "hip_number",
            ],
            na_position="last",
        )
        .reset_index(drop=True)
    )