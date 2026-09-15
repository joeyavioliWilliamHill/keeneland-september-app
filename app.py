from pathlib import Path

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from streamlit_cookies_controller import CookieController

from components.activity import (
    log_catalog_view,
    log_horse_view,
    log_session_start,
    start_or_touch_session,
)
from components.auth import require_login, render_user_menu
from components.filters import (
    apply_filters,
    render_filters,
)
from components.horse_cards import render_horse_grid
from components.horse_profile import render_horse_profile
from components.usage_dashboard import (
    is_usage_admin,
    render_usage_dashboard,
)
from database import load_horses


# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="WPT Keeneland September",
    page_icon="★",
    layout="wide",
    initial_sidebar_state="expanded",
)


cookie_controller = CookieController()


# ============================================================
# HELPERS
# ============================================================

def load_css() -> None:
    """
    Load the West Point application styling.
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



CATALOG_FILTER_BACKUP_KEY = "_catalog_filter_state"
CATALOG_VIEW_BACKUP_KEY = "_catalog_view_state"


def save_catalog_state() -> None:
    """
    Persist catalog filters outside Streamlit widget state.

    Streamlit removes widget state when those widgets are not rendered
    (for example while viewing a horse profile). Keeping a separate copy
    lets us restore the exact filtered catalog when the user comes back.
    """
    filter_state = {
        key: value
        for key, value in st.session_state.items()
        if key.startswith("filter_")
    }

    if filter_state:
        st.session_state[
            CATALOG_FILTER_BACKUP_KEY
        ] = filter_state

    view_state = {}

    for key in (
        "catalog_page",
        "catalog_page_size",
        "catalog_page_size_selector",
    ):
        if key in st.session_state:
            view_state[key] = st.session_state[key]

    if view_state:
        st.session_state[
            CATALOG_VIEW_BACKUP_KEY
        ] = view_state


def restore_catalog_state() -> None:
    """
    Restore saved catalog filters and pagination before widgets render.
    """
    filter_state = st.session_state.get(
        CATALOG_FILTER_BACKUP_KEY,
        {},
    )

    for key, value in filter_state.items():
        if key not in st.session_state:
            st.session_state[key] = value

    view_state = st.session_state.get(
        CATALOG_VIEW_BACKUP_KEY,
        {},
    )

    for key, value in view_state.items():
        if key not in st.session_state:
            st.session_state[key] = value


def scroll_profile_to_top(
    selected_hip: int,
) -> None:
    """
    Scroll to the top when a new horse profile opens.

    Runs only once per hip so normal reruns inside the same
    profile do not keep snapping the user upward.
    """
    selected_hip = int(selected_hip)

    if (
        st.session_state.get(
            "last_profile_scroll_hip"
        )
        == selected_hip
    ):
        return

    st.session_state[
        "last_profile_scroll_hip"
    ] = selected_hip

    components.html(
        """
        <script>
        (function () {
            const doc = window.parent.document;

            const candidates = [
                doc.querySelector('[data-testid="stAppViewContainer"]'),
                doc.querySelector('[data-testid="stMain"]'),
                doc.querySelector('section.main'),
                doc.scrollingElement,
                doc.documentElement,
                doc.body
            ].filter(Boolean);

            candidates.forEach((el) => {
                try {
                    if (typeof el.scrollTo === "function") {
                        el.scrollTo({top: 0, left: 0, behavior: "instant"});
                    } else {
                        el.scrollTop = 0;
                    }
                } catch (e) {
                    try { el.scrollTop = 0; } catch (_) {}
                }
            });

            try {
                window.parent.scrollTo(0, 0);
            } catch (e) {}
        })();
        </script>
        """,
        height=0,
        width=0,
    )


def go_to_horse(
    hip_number: int,
) -> None:
    """
    Navigate directly to a horse profile while preserving
    the current catalog filters and pagination.
    """
    save_catalog_state()

    st.session_state[
        "selected_hip"
    ] = int(hip_number)

    st.session_state[
        "page"
    ] = "profile"

    st.rerun()


def go_to_catalog() -> None:
    """
    Return to the catalog without clearing filters or
    the user's current catalog page.
    """
    st.session_state[
        "page"
    ] = "catalog"

    st.session_state.pop(
        "last_profile_scroll_hip",
        None,
    )

    st.rerun()



KEENELAND_LIVE_URL = (
    "https://www.keeneland.com/sales/2026/12/"
    "september-yearling-sale/watch-live/"
)


def go_to_live() -> None:
    """Open the live-sale page while preserving catalog state."""
    if st.session_state.get("page") == "catalog":
        save_catalog_state()

    st.session_state["page"] = "live"
    st.rerun()


def render_live_navigation() -> None:
    """Render the public Watch Live navigation control."""
    st.sidebar.markdown("---")

    if st.session_state["page"] == "live":
        if st.sidebar.button(
            "← Back to Catalog",
            key="live_back_to_catalog",
            use_container_width=True,
        ):
            go_to_catalog()
    else:
        if st.sidebar.button(
            "📺 Watch Live",
            key="open_watch_live",
            use_container_width=True,
        ):
            go_to_live()


def render_live_sale() -> None:
    """Render Keeneland's official live-sale page with a fallback link."""
    try:
        start_or_touch_session(
            page="live",
            hip_number=None,
        )
    except Exception:
        pass

    st.title("📺 Keeneland Live")
    st.markdown("## 2026 September Yearling Sale")
    st.caption(
        "Watch the Keeneland September sale from the official "
        "Keeneland live-sale page."
    )

    st.link_button(
        "Open Keeneland Live ↗",
        KEENELAND_LIVE_URL,
        use_container_width=False,
    )

    st.markdown(
        """
        <div style="
            margin:0.35rem 0 0.8rem 0;
            color:#64748B;
            font-size:0.88rem;
        ">
            If the embedded stream does not load on your device,
            use the button above to open Keeneland directly.
        </div>
        """,
        unsafe_allow_html=True,
    )

    components.iframe(
        KEENELAND_LIVE_URL,
        height=850,
        scrolling=True,
    )

def format_sale_date(
    value,
    include_year: bool = False,
) -> str:
    """
    Format a Keeneland sale date for display.
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

        if include_year:
            return timestamp.strftime(
                "%a, %b %-d, %Y"
            )

        return timestamp.strftime(
            "%a, %b %-d"
        )

    except Exception:
        return str(value)


def get_profile_navigation_horses(
    horses: pd.DataFrame,
    selected_hip: int,
) -> tuple[pd.DataFrame, bool]:
    """
    Rebuild the horse universe used for profile navigation.

    When a user enters a horse from filtered catalog results,
    Previous / Next / Jump to Horse stay inside that same
    filtered result set.

    Returns:
        (navigation_horses, using_filtered_context)
    """
    stored_hips = st.session_state.get(
        "catalog_filtered_hips"
    )

    if stored_hips:
        try:
            ordered_hips = [
                int(hip)
                for hip in stored_hips
            ]
        except (
            TypeError,
            ValueError,
        ):
            ordered_hips = []

        if (
            ordered_hips
            and int(selected_hip) in ordered_hips
        ):
            order_map = {
                hip: index
                for index, hip
                in enumerate(ordered_hips)
            }

            navigation_horses = (
                horses[
                    horses["hip_number"]
                    .isin(ordered_hips)
                ]
                .copy()
            )

            navigation_horses[
                "_catalog_order"
            ] = (
                navigation_horses[
                    "hip_number"
                ]
                .astype(int)
                .map(order_map)
            )

            navigation_horses = (
                navigation_horses
                .sort_values(
                    "_catalog_order"
                )
                .drop(
                    columns=[
                        "_catalog_order"
                    ]
                )
                .reset_index(
                    drop=True
                )
            )

            return (
                navigation_horses,
                len(ordered_hips) < len(horses),
            )

    return (
        horses
        .sort_values(
            "hip_number"
        )
        .reset_index(
            drop=True
        ),
        False,
    )


def render_profile_navigation(
    horses: pd.DataFrame,
    selected_hip: int,
    using_filtered_context: bool,
    total_catalog_horses: int,
) -> None:
    """
    Render a compact single-row profile navigation bar.
    """
    available_columns = [
        column
        for column in [
            "hip_number",
            "sire",
            "dam",
            "book_number",
            "sale_day",
            "sale_date",
        ]
        if column in horses.columns
    ]

    ordered_horses = (
        horses[available_columns]
        .dropna(subset=["hip_number"])
        .reset_index(drop=True)
    )

    hip_numbers = (
        ordered_horses["hip_number"]
        .astype(int)
        .tolist()
    )

    if selected_hip not in hip_numbers:
        return

    current_index = hip_numbers.index(selected_hip)

    # Warm Keeneland/WPT navigation band.
    st.markdown(
        """
        <style>
        div[data-testid="stVerticalBlockBorderWrapper"]:has(
            #wpt-profile-nav-marker
        ) {
            background: #F3E8C8;
            border: 1px solid #C8A96B;
            border-radius: 14px;
            padding: 0.65rem 0.8rem 0.45rem 0.8rem;
            margin-bottom: 0.75rem;
        }

        div[data-testid="stVerticalBlockBorderWrapper"]:has(
            #wpt-profile-nav-marker
        ) button {
            border-color: #15392F;
            font-weight: 750;
        }

        div[data-testid="stVerticalBlockBorderWrapper"]:has(
            #wpt-profile-nav-marker
        ) [data-testid="stCaptionContainer"] {
            color: #5F5130;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    with st.container(
        border=True,
        key="profile_sticky_nav",
    ):
        st.markdown(
            '<span id="wpt-profile-nav-marker"></span>',
            unsafe_allow_html=True,
        )

        back_column, slider_column = st.columns(
            [1.05, 4.95],
            gap="large",
            vertical_alignment="center",
        )

        with back_column:
            if st.button(
                "← Back to Catalog",
                key="profile_back_to_catalog",
                use_container_width=True,
            ):
                go_to_catalog()

        with slider_column:
            if using_filtered_context:
                context_text = (
                    f"Browse horses · {len(ordered_horses):,} filtered "
                    f"· Hip {current_index + 1:,} of {len(ordered_horses):,}"
                )
            else:
                context_text = (
                    f"Browse horses · full catalog "
                    f"· {total_catalog_horses:,} horses"
                )

            st.caption(context_text)

            slider_hip = st.select_slider(
                "Browse horses",
                options=hip_numbers,
                value=selected_hip,
                format_func=lambda hip: f"Hip {hip}",
                key=f"profile_hip_slider_{selected_hip}",
                label_visibility="collapsed",
            )

            if int(slider_hip) != int(selected_hip):
                go_to_horse(int(slider_hip))


# ============================================================
# APP INITIALIZATION
# ============================================================

load_css()

# Email gate + 30-day remembered browser cookie.
require_login(cookie_controller)

if "page" not in st.session_state:
    st.session_state[
        "page"
    ] = "catalog"

# Analytics must never prevent the catalog from loading.
try:
    log_session_start()
except Exception:
    pass

# Public live-sale navigation.
render_live_navigation()

# Private usage analytics navigation.
if is_usage_admin():
    st.sidebar.markdown("---")

    if st.session_state["page"] == "usage":
        if st.sidebar.button(
            "← Back to Catalog",
            key="usage_back_to_catalog",
            use_container_width=True,
        ):
            st.session_state["page"] = "catalog"
            st.rerun()
    else:
        if st.sidebar.button(
            "📊 Usage Analytics",
            key="open_usage_analytics",
            use_container_width=True,
        ):
            st.session_state["page"] = "usage"
            st.rerun()

# Admin-only analytics page does not need to load the horse catalog.
if st.session_state["page"] == "usage":
    render_user_menu(
        cookie_controller
    )
    render_usage_dashboard()
    st.stop()

# Watch Live also does not need to load the horse catalog.
if st.session_state["page"] == "live":
    render_user_menu(
        cookie_controller
    )
    render_live_sale()
    st.stop()


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
        go_to_catalog()

    selected_hip = int(
        selected_hip
    )

    try:
        log_horse_view(selected_hip)
        start_or_touch_session(
            page="profile",
            hip_number=selected_hip,
        )
    except Exception:
        pass

    scroll_profile_to_top(
        selected_hip
    )

    selected_horse = horses[
        horses["hip_number"]
        == selected_hip
    ]

    if selected_horse.empty:
        st.error(
            "The selected horse could not "
            "be found in the Keeneland catalog."
        )

        if st.button(
            "Return to Catalog"
        ):
            go_to_catalog()

        st.stop()

    (
        navigation_horses,
        using_filtered_context,
    ) = get_profile_navigation_horses(
        horses=horses,
        selected_hip=selected_hip,
    )

    render_profile_navigation(
        horses=navigation_horses,
        selected_hip=selected_hip,
        using_filtered_context=(
            using_filtered_context
        ),
        total_catalog_horses=len(
            horses
        ),
    )

    render_horse_profile(
        selected_horse.iloc[0]
    )


# ============================================================
# CATALOG
# ============================================================

else:
    try:
        log_catalog_view()
        start_or_touch_session(
            page="catalog",
            hip_number=None,
        )
    except Exception:
        pass

    # --------------------------------------------------------
    # Sidebar filters
    # --------------------------------------------------------

    # Restore the exact filter/widget state that was active before
    # the user opened a horse profile.
    restore_catalog_state()

    filters = render_filters(
        horses
    )

    # Keep an independent copy because Streamlit removes widget
    # state while those widgets are not rendered on the profile page.
    save_catalog_state()

    filtered_horses = (
        apply_filters(
            horses,
            filters,
        )
    )

    # Store the exact current result universe so profile
    # navigation can stay inside it.
    st.session_state[
        "catalog_filtered_hips"
    ] = (
        filtered_horses[
            "hip_number"
        ]
        .dropna()
        .astype(int)
        .tolist()
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

    render_user_menu(
        cookie_controller
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
        "sale information, photography, and video."
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
