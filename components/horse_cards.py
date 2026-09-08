import html
import math
from typing import Any

import pandas as pd
import streamlit as st


# ============================================================
# DISPLAY HELPERS
# ============================================================

def display_value(
    value: Any,
    fallback: str = "Not available",
) -> str:
    if value is None:
        return fallback

    try:
        if pd.isna(value):
            return fallback
    except (TypeError, ValueError):
        pass

    text = str(value).strip()

    return text if text else fallback


def format_currency(
    value: Any,
) -> str:
    if value is None:
        return "N/A"

    try:
        if pd.isna(value):
            return "N/A"
    except (TypeError, ValueError):
        pass

    try:
        return f"${float(value):,.0f}"
    except (TypeError, ValueError):
        return "N/A"


def format_sex(
    value: Any,
) -> str:
    labels = {
        "c": "Colt",
        "f": "Filly",
        "g": "Gelding",
        "h": "Horse",
        "m": "Mare",
        "r": "Ridgling",
    }

    text = display_value(
        value,
        "—",
    ).lower()

    return labels.get(
        text,
        text.title(),
    )


def format_integer(
    value: Any,
    fallback: str = "—",
) -> str:
    if value is None:
        return fallback

    try:
        if pd.isna(value):
            return fallback
    except (TypeError, ValueError):
        pass

    try:
        return str(int(value))
    except (TypeError, ValueError):
        return display_value(
            value,
            fallback,
        )


def format_sale_date(
    value: Any,
    fallback: str = "—",
) -> str:
    """
    Format the horse's Keeneland sale date for compact card display.
    """
    if value is None:
        return fallback

    try:
        if pd.isna(value):
            return fallback
    except (TypeError, ValueError):
        pass

    try:
        timestamp = pd.Timestamp(value)

        return timestamp.strftime(
            "%a, %b %-d"
        )
    except Exception:
        return display_value(
            value,
            fallback,
        )


def has_photo(
    photo_url: Any,
) -> bool:
    if photo_url is None:
        return False

    try:
        if pd.isna(photo_url):
            return False
    except (TypeError, ValueError):
        pass

    return bool(
        str(photo_url).strip()
    )


# ============================================================
# HTML HELPERS
# ============================================================

def html_tag(
    tag: str,
    content: str = "",
    class_name: str | None = None,
    **attributes: str,
) -> str:
    parts = []

    if class_name:
        parts.append(
            f'class="'
            f'{html.escape(class_name, quote=True)}'
            f'"'
        )

    for key, value in attributes.items():
        attribute_name = key.replace(
            "_",
            "-",
        )

        parts.append(
            f'{attribute_name}="'
            f'{html.escape(str(value), quote=True)}'
            f'"'
        )

    attribute_text = (
        f" {' '.join(parts)}"
        if parts
        else ""
    )

    return (
        f"<{tag}{attribute_text}>"
        f"{content}"
        f"</{tag}>"
    )


def render_html(
    content: str,
) -> None:
    st.markdown(
        content,
        unsafe_allow_html=True,
    )


# ============================================================
# HORSE IMAGE
# ============================================================

def build_image_html(
    hip_number: int,
    photo_url: Any,
    image_height: int,
) -> str:
    if has_photo(photo_url):
        safe_url = html.escape(
            str(photo_url).strip(),
            quote=True,
        )

        image = (
            f'<img src="{safe_url}" '
            f'alt="Hip {hip_number}" '
            f'class="wpt-horse-image">'
        )

        return (
            f'<div class="wpt-horse-image-wrap" '
            f'style="height:{image_height}px;">'
            f"{image}"
            f"</div>"
        )

    placeholder = (
        html_tag(
            "div",
            "★",
            "wpt-placeholder-icon",
        )
        + html_tag(
            "div",
            f"HIP {hip_number}",
            "wpt-placeholder-hip",
        )
    )

    return (
        f'<div class="wpt-horse-image-wrap '
        f'wpt-photo-placeholder" '
        f'style="height:{image_height}px;">'
        f'{html_tag(
            "div",
            placeholder,
            "wpt-placeholder-content",
        )}'
        f"</div>"
    )


def render_horse_image(
    hip_number: int,
    photo_url: Any = None,
    image_height: int = 300,
) -> None:
    render_html(
        build_image_html(
            hip_number=hip_number,
            photo_url=photo_url,
            image_height=image_height,
        )
    )


# ============================================================
# BADGES
# ============================================================

def build_badges_html(
    horse: pd.Series,
) -> str:
    """
    Build optional status badges.

    Most Keeneland horses will have no badges during the
    pre-sale MVP. This is intentionally future-ready for
    photography and sale results.
    """
    badges: list[tuple[str, str]] = []

    # --------------------------------------------------------
    # WPT Purchase
    # --------------------------------------------------------

    if bool(
        horse.get(
            "wpt_purchase",
            False,
        )
    ):
        badges.append(
            (
                "🏆 WPT PURCHASE",
                "wpt",
            )
        )

    # --------------------------------------------------------
    # Sale Result
    # --------------------------------------------------------

    sale_status = display_value(
        horse.get(
            "sale_status"
        ),
        "PENDING",
    ).upper()

    sale_price = horse.get(
        "sale_price"
    )

    if sale_status == "SOLD":
        badges.append(
            (
                (
                    "SOLD · "
                    f"{format_currency(sale_price)}"
                ),
                "sold",
            )
        )

    elif sale_status == "NOT SOLD":
        badges.append(
            (
                (
                    "NOT SOLD · "
                    f"{format_currency(sale_price)}"
                ),
                "not-sold",
            )
        )

    elif sale_status == "OUT":
        badges.append(
            (
                "OUT",
                "out",
            )
        )

    # --------------------------------------------------------
    # Photo
    # --------------------------------------------------------

    if has_photo(
        horse.get(
            "photo_url"
        )
    ):
        photo_count = horse.get(
            "photo_count",
            0,
        )

        try:
            photo_count = int(
                photo_count
            )
        except (TypeError, ValueError):
            photo_count = 0

        photo_label = (
            f"📷 {photo_count} Photos"
            if photo_count > 1
            else "📷 Photo"
        )

        badges.append(
            (
                photo_label,
                "photo",
            )
        )

    if not badges:
        return ""

    badge_html = []

    for label, badge_type in badges:

        if badge_type == "wpt":
            style = (
                "background:#000000;"
                "color:#F3BD18;"
                "border:1px solid #000000;"
            )

        elif badge_type == "sold":
            style = (
                "background:#EEF7F2;"
                "color:#15392F;"
                "border:1px solid #B9D7C7;"
            )

        elif badge_type == "not-sold":
            style = (
                "background:#FFF7E8;"
                "color:#8A5A00;"
                "border:1px solid #E7C98A;"
            )

        elif badge_type == "out":
            style = (
                "background:#F3F4F6;"
                "color:#6B7280;"
                "border:1px solid #D1D5DB;"
            )

        else:
            style = (
                "background:#F7F7F8;"
                "color:#475569;"
                "border:1px solid #E5E7EB;"
            )

        badge_html.append(
            (
                '<span class="wpt-card-badge" '
                f'style="{style}">'
                f'{html.escape(label)}'
                '</span>'
            )
        )

    return html_tag(
        "div",
        "".join(
            badge_html
        ),
        "wpt-card-badges",
    )


# ============================================================
# CARD HEADING
# ============================================================

def build_heading_html(
    horse: pd.Series,
    hip_number: int,
) -> str:
    book_number = format_integer(
        horse.get(
            "book_number"
        )
    )

    sale_day = format_integer(
        horse.get(
            "sale_day"
        )
    )

    sale_date = html.escape(
        format_sale_date(
            horse.get(
                "sale_date"
            )
        )
    )

    sire = html.escape(
        display_value(
            horse.get(
                "sire"
            )
        )
    )

    dam = html.escape(
        display_value(
            horse.get(
                "dam"
            )
        )
    )

    broodmare_sire = html.escape(
        display_value(
            horse.get(
                "broodmare_sire"
            ),
            "—",
        )
    )

    eyebrow = html_tag(
        "div",
        (
            f"HIP {hip_number}"
            f'<span class="wpt-card-dot">•</span>'
            f"BOOK {book_number}"
            f'<span class="wpt-card-dot">•</span>'
            f"DAY {sale_day}"
            f'<span class="wpt-card-dot">•</span>'
            f"{sale_date}"
        ),
        "wpt-card-eyebrow",
    )

    sire_html = html_tag(
        "div",
        sire,
        "wpt-card-sire",
    )

    dam_html = html_tag(
        "div",
        f"× {dam}",
        "wpt-card-dam",
    )

    meta = html_tag(
        "div",
        (
            "Broodmare Sire: "
            f"{broodmare_sire}"
        ),
        "wpt-card-meta",
    )

    return html_tag(
        "div",
        (
            eyebrow
            + sire_html
            + dam_html
            + meta
        ),
        "wpt-card-heading",
    )


# ============================================================
# CARD STATS
# ============================================================

def build_stat_html(
    label: str,
    value: str,
) -> str:
    label_html = (
        '<div class="wpt-card-stat-label" '
        'style="white-space: nowrap; '
        'font-size: 0.72rem; '
        'letter-spacing: 0.02em;">'
        f'{html.escape(label)}'
        '</div>'
    )

    value_html = html_tag(
        "div",
        html.escape(value),
        "wpt-card-stat-value",
    )

    return html_tag(
        "div",
        label_html + value_html,
        "wpt-card-stat",
    )


# ============================================================
# HORSE CARD
# ============================================================

def render_horse_card(
    horse: pd.Series,
) -> None:
    hip_number = int(
        horse["hip_number"]
    )

    with st.container(
        border=True
    ):
        render_horse_image(
            hip_number=hip_number,
            photo_url=horse.get(
                "photo_url"
            ),
            image_height=285,
        )

        badges_html = build_badges_html(
            horse
        )

        if badges_html:
            render_html(
                badges_html
            )

        render_html(
            build_heading_html(
                horse=horse,
                hip_number=hip_number,
            )
        )

        metric_left, metric_right = (
            st.columns(
                [1, 1]
            )
        )

        with metric_left:
            render_html(
                build_stat_html(
                    "Sex",
                    format_sex(
                        horse.get(
                            "sex"
                        )
                    ).upper(),
                )
            )

        with metric_right:
            render_html(
                build_stat_html(
                    "Barn",
                    display_value(
                        horse.get(
                            "barn"
                        ),
                        "—",
                    ),
                )
            )

        if st.button(
            "View Profile",
            key=(
                f"view_horse_"
                f"{hip_number}"
            ),
            use_container_width=True,
            type="primary",
        ):
            st.session_state[
                "selected_hip"
            ] = hip_number

            st.session_state[
                "page"
            ] = "profile"

            st.rerun()


# ============================================================
# HORSE GRID
# ============================================================

def render_horse_grid(
    horses: pd.DataFrame,
    cards_per_page: int = 12,
) -> None:
    if horses.empty:
        st.warning(
            "No horses matched the current filters."
        )
        return

    total_pages = max(
        1,
        math.ceil(
            len(horses)
            / cards_per_page
        ),
    )

    page_number = (
        st.session_state.setdefault(
            "catalog_page",
            1,
        )
    )

    if page_number > total_pages:
        page_number = 1

        st.session_state[
            "catalog_page"
        ] = 1

    start_index = (
        page_number - 1
    ) * cards_per_page

    end_index = (
        start_index
        + cards_per_page
    )

    page_horses = horses.iloc[
        start_index:end_index
    ]

    # --------------------------------------------------------
    # Catalog grid
    # --------------------------------------------------------

    for row_start in range(
        0,
        len(page_horses),
        3,
    ):
        columns = st.columns(
            3,
            gap="large",
        )

        row_horses = page_horses.iloc[
            row_start:row_start + 3
        ]

        for column, (_, horse) in zip(
            columns,
            row_horses.iterrows(),
        ):
            with column:
                render_horse_card(
                    horse
                )

    # --------------------------------------------------------
    # Pagination
    # --------------------------------------------------------

    st.divider()

    (
        previous_column,
        page_column,
        next_column,
    ) = st.columns(
        [1, 2, 1]
    )

    with previous_column:
        if st.button(
            "← Previous",
            disabled=(
                page_number <= 1
            ),
            use_container_width=True,
            key="catalog_previous",
        ):
            st.session_state[
                "catalog_page"
            ] -= 1

            st.rerun()

    with page_column:
        render_html(
            html_tag(
                "div",
                (
                    f"Page "
                    f"<strong>{page_number}</strong> "
                    f"of "
                    f"<strong>{total_pages}</strong>"
                    f"<br>"
                    f"<span style='font-size:0.82rem;"
                    f"color:#6B7280;'>"
                    f"{len(horses):,} horses"
                    f"</span>"
                ),
                "wpt-pagination-label",
            )
        )

    with next_column:
        if st.button(
            "Next →",
            disabled=(
                page_number
                >= total_pages
            ),
            use_container_width=True,
            key="catalog_next",
        ):
            st.session_state[
                "catalog_page"
            ] += 1

            st.rerun()