from pathlib import Path

import pandas as pd
import streamlit as st

from components.filters import (
    apply_filters,
    render_filters,
)
from components.horse_cards import render_horse_grid
from components.horse_profile import render_horse_profile
from database import load_horses


# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="WPT Keeneland September",
    page_icon="🐎",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ============================================================
# HELPERS
# ============================================================

def load_css() -> None:
    """
    Load the existing West Point application styling.
    """
    css_file = (
        Path(__file__).parent
        / "styles.css"
    )

    if not css_file.exists():
        return

    with open(
        css_file,
        encoding="utf-8",
    ) as file:
        st.markdown(
            f"<style>{file.read()}</style>",
            unsafe_allow_html=True,
        )


def go_to_horse(
    hip_number: int,
) -> None:
    """
    Navigate directly to a horse profile.
    """
    st.session_state[
        "selected_hip"
    ] = int(hip_number)

    st.session_state[
        "page"
    ] = "profile"

    st.rerun()


def format_sale_date(
    value,
) -> str:
    """
    Format a sale date for catalog metrics.
    """
    if value is None:
        return "—"

    try:
        if pd.isna(value):
            return "—"
    except (TypeError, ValueError):
        pass

    try:
        timestamp = pd.Timestamp(value)

        return timestamp.strftime(
            "%b %-d"
        )

    except Exception:
        return str(value)


def render_profile_navigation(
    horses: pd.DataFrame,
    selected_hip: int,
) -> None:
    """
    Render previous / next navigation and the
    jump-to-horse selector.

    Navigation uses the complete Keeneland catalog,
    ordered by hip number.
    """
    ordered_horses = (
        horses[
            [
                "hip_number",
                "sire",
                "dam",
                "book_number",
                "sale_day",
            ]
        ]
        .dropna(
            subset=[
                "hip_number"
            ]
        )
        .sort_values(
            "hip_number"
        )
        .reset_index(
            drop=True
        )
    )

    hip_numbers = (
        ordered_horses[
            "hip_number"
        ]
        .astype(int)
        .tolist()
    )

    if selected_hip not in hip_numbers:
        return

    current_index = hip_numbers.index(
        selected_hip
    )

    previous_hip = (
        hip_numbers[
            current_index - 1
        ]
        if current_index > 0
        else None
    )

    next_hip = (
        hip_numbers[
            current_index + 1
        ]
        if (
            current_index
            < len(hip_numbers) - 1
        )
        else None
    )

    (
        previous_column,
        search_column,
        next_column,
    ) = st.columns(
        [1, 2.6, 1],
        gap="medium",
    )

    # --------------------------------------------------------
    # Previous horse
    # --------------------------------------------------------

    with previous_column:
        if previous_hip is not None:
            if st.button(
                f"← Hip {previous_hip}",
                key=(
                    "profile_previous_"
                    f"{selected_hip}"
                ),
                use_container_width=True,
            ):
                go_to_horse(
                    previous_hip
                )

        else:
            st.button(
                "← Previous",
                disabled=True,
                use_container_width=True,
                key=(
                    "profile_previous_disabled_"
                    f"{selected_hip}"
                ),
            )

    # --------------------------------------------------------
    # Jump to horse
    # --------------------------------------------------------

    with search_column:
        search_options = []

        for _, horse in (
            ordered_horses.iterrows()
        ):
            hip_number = int(
                horse["hip_number"]
            )

            sire = str(
                horse.get(
                    "sire",
                    "",
                )
                or ""
            ).strip()

            dam = str(
                horse.get(
                    "dam",
                    "",
                )
                or ""
            ).strip()

            book_number = horse.get(
                "book_number"
            )

            sale_day = horse.get(
                "sale_day"
            )

            label = (
                f"Hip {hip_number}"
            )

            if sire or dam:
                label += (
                    f" · {sire} × {dam}"
                )

            if pd.notna(book_number):
                label += (
                    f" · Book "
                    f"{int(book_number)}"
                )

            if pd.notna(sale_day):
                label += (
                    f" · Day "
                    f"{int(sale_day)}"
                )

            search_options.append(
                label
            )

        selected_label = (
            st.selectbox(
                "Jump to horse",
                options=search_options,
                index=current_index,
                key=(
                    "profile_jump_"
                    f"{selected_hip}"
                ),
                label_visibility=(
                    "collapsed"
                ),
            )
        )

        selected_search_hip = int(
            selected_label
            .split(
                "·",
                1,
            )[0]
            .replace(
                "Hip",
                "",
            )
            .strip()
        )

        if (
            selected_search_hip
            != selected_hip
        ):
            go_to_horse(
                selected_search_hip
            )

    # --------------------------------------------------------
    # Next horse
    # --------------------------------------------------------

    with next_column:
        if next_hip is not None:
            if st.button(
                f"Hip {next_hip} →",
                key=(
                    "profile_next_"
                    f"{selected_hip}"
                ),
                use_container_width=True,
            ):
                go_to_horse(
                    next_hip
                )

        else:
            st.button(
                "Next →",
                disabled=True,
                use_container_width=True,
                key=(
                    "profile_next_disabled_"
                    f"{selected_hip}"
                ),
            )


# ============================================================
# APP INITIALIZATION
# ============================================================

load_css()

if "page" not in st.session_state:
    st.session_state[
        "page"
    ] = "catalog"


# ============================================================
# LOAD KEENELAND CATALOG
# ============================================================

try:
    horses = load_horses()

except Exception as error:
    st.error(
        "The application could not connect "
        "to the Keeneland catalog database."
    )

    st.exception(
        error
    )

    st.stop()


# ============================================================
# HORSE PROFILE
# ============================================================

if (
    st.session_state["page"]
    == "profile"
):
    selected_hip = (
        st.session_state.get(
            "selected_hip"
        )
    )

    if selected_hip is None:
        st.session_state[
            "page"
        ] = "catalog"

        st.rerun()

    selected_horse = horses[
        horses["hip_number"]
        == int(selected_hip)
    ]

    if selected_horse.empty:
        st.error(
            "The selected horse could not "
            "be found in the Keeneland catalog."
        )

        if st.button(
            "Return to Catalog"
        ):
            st.session_state[
                "page"
            ] = "catalog"

            st.rerun()

        st.stop()

    render_profile_navigation(
        horses=horses,
        selected_hip=int(
            selected_hip
        ),
    )

    st.divider()

    render_horse_profile(
        selected_horse.iloc[0]
    )


# ============================================================
# CATALOG
# ============================================================

else:
    # --------------------------------------------------------
    # Sidebar filters
    # --------------------------------------------------------

    filters = render_filters(
        horses
    )

    filtered_horses = (
        apply_filters(
            horses,
            filters,
        )
    )

    st.sidebar.markdown(
        f"""
        <div class="wpt-sidebar-count">
            <strong>
                {len(filtered_horses):,}
            </strong><br>
            of {len(horses):,} horses shown
        </div>
        """,
        unsafe_allow_html=True,
    )

    # --------------------------------------------------------
    # Catalog header
    # --------------------------------------------------------

    st.title(
        "West Point Thoroughbreds"
    )

    st.markdown(
        "## Keeneland September "
        "Selected Yearlings"
    )

    st.caption(
        "2026 Keeneland September Yearling Sale · "
        "Pedigree, commercial analysis, "
        "nicking data, and prospect research."
    )

    # --------------------------------------------------------
    # Catalog metrics
    # --------------------------------------------------------

    (
        total_column,
        results_column,
        book_column,
        day_column,
    ) = st.columns(4)

    total_column.metric(
        "Sale Catalog",
        f"{len(horses):,}",
        help=(
            "Total yearlings in the "
            "2026 Keeneland September catalog."
        ),
    )

    results_column.metric(
        "Showing",
        f"{len(filtered_horses):,}",
        help=(
            "Horses matching the "
            "current filters."
        ),
    )

    available_books = (
        filtered_horses[
            "book_number"
        ]
        .dropna()
        .nunique()
    )

    book_column.metric(
        "Books",
        available_books,
    )

    available_days = (
        filtered_horses[
            "sale_day"
        ]
        .dropna()
        .nunique()
    )

    day_column.metric(
        "Sale Days",
        available_days,
    )

    # --------------------------------------------------------
    # Active catalog context
    # --------------------------------------------------------

    if not filtered_horses.empty:
        filtered_dates = (
            filtered_horses[
                "sale_date"
            ]
            .dropna()
            .sort_values()
        )

        if not filtered_dates.empty:
            first_date = (
                filtered_dates.iloc[0]
            )

            last_date = (
                filtered_dates.iloc[-1]
            )

            first_label = (
                format_sale_date(
                    first_date
                )
            )

            last_label = (
                format_sale_date(
                    last_date
                )
            )

            if first_label == last_label:
                date_text = first_label

            else:
                date_text = (
                    f"{first_label} – "
                    f"{last_label}"
                )

            st.caption(
                f"Sale dates shown: "
                f"{date_text}, 2026"
            )

    st.divider()

    # --------------------------------------------------------
    # Horse grid
    # --------------------------------------------------------

    render_horse_grid(
        filtered_horses
    )