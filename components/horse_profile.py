import html
import json
import re
from typing import Any

import pandas as pd
import streamlit as st

import streamlit.components.v1 as components

from components.horse_cards import (
    display_value,
    format_currency,
    format_sex,
    render_horse_image
)


def section_header(title: str, icon: str = "") -> None:
    st.markdown(f"### {icon} {title}")
    st.divider()


def info_row(label: str, value: str) -> None:
    label_column, value_column = st.columns([1, 2])

    with label_column:
        st.caption(label)

    with value_column:
        st.write(value)


def normalize_record_list(value: Any) -> list[str]:
    if value is None:
        return []

    try:
        if pd.isna(value):
            return []
    except (TypeError, ValueError):
        pass

    if isinstance(value, list):
        return [str(record).strip() for record in value if str(record).strip()]

    if isinstance(value, str):
        stripped = value.strip()

        if not stripped:
            return []

        try:
            parsed = json.loads(stripped)

            if isinstance(parsed, list):
                return [
                    str(record).strip()
                    for record in parsed
                    if str(record).strip()
                ]
        except json.JSONDecodeError:
            return [stripped]

    return []


def render_plain_text(
    text: Any,
    empty_message: str = "No information available.",
    font_size: str = "1rem",
    line_height: str = "1.7",
) -> None:
    cleaned_text = display_value(text, "—")

    if cleaned_text == "—":
        st.caption(empty_message)
        return

    safe_text = html.escape(cleaned_text)

    st.markdown(
        f"""
        <div style="
            font-size: {font_size};
            line-height: {line_height};
            color: #30343f;
            overflow-wrap: anywhere;
        ">
            {safe_text}
        </div>
        """,
        unsafe_allow_html=True,
    )


def split_bullet_segments(text: str) -> list[str]:
    if not text:
        return []

    parts = re.split(r"\s*[•]\s*", text)
    return [part.strip() for part in parts if part and part.strip()]


def extract_money(value: str | None) -> str | None:
    if not value:
        return None

    match = re.search(r"\$\s*[\d,]+", value)
    return match.group(0).replace(" ", "") if match else None


def parse_sale_history_entry(value: str) -> dict[str, str | None]:
    """Parse one catalog sale-history segment into readable fields."""
    text = str(value).strip()

    sale_match = re.search(
        r"\b(?P<sale>\d{2}[A-Z]{3,10})\b",
        text,
        flags=re.IGNORECASE,
    )

    price_match = re.search(
        r"(?P<rna>\()?\$(?P<price>[\d,]+)\)?",
        text,
    )

    consignor_match = re.search(
        r"Consignor:\s*(?P<consignor>[^;]+)",
        text,
        flags=re.IGNORECASE,
    )

    buyer_match = re.search(
        r"Buyer:\s*(?P<buyer>[^;]+)",
        text,
        flags=re.IGNORECASE,
    )

    for_match = re.search(
        r"—For:\s*(?P<for_party>.+)$",
        text,
        flags=re.IGNORECASE,
    )

    sale_code = sale_match.group("sale") if sale_match else None
    sale_year = None
    sale_name = None

    if sale_code:
        year_prefix = sale_code[:2]
        code_suffix = sale_code[2:].upper()
        sale_year = f"20{year_prefix}"

        sale_names = {
            "KEENOV": "Keeneland November",
            "KEESEP": "Keeneland September",
            "KEEJAN": "Keeneland January",
            "FTKOCT": "Fasig-Tipton October",
            "FTKNOV": "Fasig-Tipton November",
            "FTKHRA": "Fasig-Tipton Horses of Racing Age",
            "FTNMIX": "Fasig-Tipton Midlantic Mixed",
            "FTSAUG": "Fasig-Tipton Saratoga",
            "SARAUG": "Saratoga August",
            "OBSAPR": "OBS April",
            "OBSOPN": "OBS June / Open",
            "OBSMAR": "OBS March",
            "EASMAY": "Fasig-Tipton Midlantic May",
            "FTDFEB": "Fasig-Tipton Digital February",
            "CLAIM": "Claim",
        }

        sale_name = sale_names.get(code_suffix, sale_code)

    price = f"${price_match.group('price')}" if price_match else None

    is_rna = bool(
        price_match and price_match.group("rna")
    ) or bool(
        re.search(
            r"\(RNA\)",
            text,
            flags=re.IGNORECASE,
        )
    )

    return {
        "sale_code": sale_code,
        "sale_name": sale_name,
        "sale_year": sale_year,
        "price": price,
        "rna": "RNA" if is_rna else None,
        "consignor": (
            consignor_match.group("consignor").strip()
            if consignor_match
            else None
        ),
        "buyer": (
            buyer_match.group("buyer").strip()
            if buyer_match
            else None
        ),
        "for_party": (
            for_match.group("for_party").strip()
            if for_match
            else None
        ),
        "raw": text,
    }


def parse_first_dam_record(record: str) -> dict[str, Any]:
    record = record.strip()

    segments = split_bullet_segments(record)
    primary_segment = segments[0] if segments else record
    extra_sale_segments = segments[1:] if len(segments) > 1 else []

    name_match = re.match(r"^([^,]+)", primary_segment)
    starts_match = re.search(r"(\d+)\s+sts?", primary_segment, flags=re.IGNORECASE)
    wins_match = re.search(r"(\d+)\s+wins?", primary_segment, flags=re.IGNORECASE)

    earnings_match = None
    if starts_match or wins_match:
        earnings_match = re.search(r"\$([\d,]+)", primary_segment)

    cpi_match = re.search(
        r"\[([\d.]+)\s*CPI\]",
        primary_segment,
        flags=re.IGNORECASE,
    )

    equibase_match = re.search(
        r"\(\s*E\s+(\d+)\s*\)",
        primary_segment,
        flags=re.IGNORECASE,
    )

    thorograph_match = re.search(
        r"ThoroGraph\s+"
        r"2yo:\s*(.*?)\s+"
        r"3yo:\s*(.*?)\s+"
        r"4yo:\s*(.*?)\s+"
        r"5yo\+:\s*(.*?)(?=\s+\d{2}[A-Z]{3,10}\b|\s*$)",
        primary_segment,
        flags=re.IGNORECASE,
    )

    status = None
    if re.search(r"\bUnraced\b", primary_segment, flags=re.IGNORECASE):
        status = "Unraced"
    elif starts_match:
        status = "Raced"

    first_sale_match = re.search(
        r"\b\d{2}[A-Z]{3,10}\b",
        primary_segment,
        flags=re.IGNORECASE,
    )

    performance_segment = (
        primary_segment[:first_sale_match.start()].strip()
        if first_sale_match
        else primary_segment
    )

    inline_sale_segment = (
        primary_segment[first_sale_match.start():].strip()
        if first_sale_match
        else None
    )

    sale_segments = []
    if inline_sale_segment:
        sale_segments.append(inline_sale_segment)
    sale_segments.extend(extra_sale_segments)

    sale_history = [
        parse_sale_history_entry(segment)
        for segment in sale_segments
        if str(segment).strip()
    ]

    performance_text = performance_segment
    if name_match:
        performance_text = performance_text[name_match.end():].lstrip(" ,")

    performance_text = re.sub(
        r"^\d+\s+sts?,?\s*",
        "",
        performance_text,
        flags=re.IGNORECASE,
    )
    performance_text = re.sub(
        r"^\d+\s+wins?(?:\s*\([^)]+\))?,?\s*",
        "",
        performance_text,
        flags=re.IGNORECASE,
    )
    performance_text = re.sub(
        r"^\$[\d,]+\s*",
        "",
        performance_text,
    )
    performance_text = re.sub(
        r"^\[[\d.]+\s*CPI\]\s*",
        "",
        performance_text,
        flags=re.IGNORECASE,
    )
    performance_text = performance_text.strip(" ,;-")

    return {
        "name": name_match.group(1).strip() if name_match else "First Dam",
        "status": status,
        "starts": starts_match.group(1) if starts_match else None,
        "wins": wins_match.group(1) if wins_match else None,
        "earnings": f"${earnings_match.group(1)}" if earnings_match else None,
        "cpi": cpi_match.group(1) if cpi_match else None,
        "equibase": equibase_match.group(1) if equibase_match else None,
        "thorograph": {
            "2yo": thorograph_match.group(1).strip() if thorograph_match else None,
            "3yo": thorograph_match.group(2).strip() if thorograph_match else None,
            "4yo": thorograph_match.group(3).strip() if thorograph_match else None,
            "5yo+": thorograph_match.group(4).strip() if thorograph_match else None,
        },
        "performance_text": performance_text or None,
        "sale_history": sale_history,
    }


def render_metric_card(label: str, value: str | None) -> None:
    display = value or "—"

    st.markdown(
        f"""
        <div style="
            border: 1px solid #E5E7EB;
            border-radius: 10px;
            padding: 0.8rem 0.9rem;
            background: #FAFAFB;
            min-height: 86px;
        ">
            <div style="
                color: #6B7280;
                font-size: 0.78rem;
                letter-spacing: 0.04em;
                text-transform: uppercase;
                margin-bottom: 0.3rem;
            ">
                {html.escape(label)}
            </div>
            <div style="
                color: #1F2937;
                font-size: 1.05rem;
                font-weight: 700;
            ">
                {html.escape(display)}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_first_dam_record(record: Any) -> None:
    cleaned_record = display_value(record, "—")

    if cleaned_record == "—":
        st.caption("No first-dam race record is available.")
        return

    parsed = parse_first_dam_record(cleaned_record)

    st.markdown(f"#### {parsed['name']}")

    metric_columns = st.columns(4)

    with metric_columns[0]:
        render_metric_card("Status", parsed["status"])

    with metric_columns[1]:
        render_metric_card("Starts", parsed["starts"])

    with metric_columns[2]:
        render_metric_card("Wins", parsed["wins"])

    with metric_columns[3]:
        render_metric_card("Earnings", parsed["earnings"])

    secondary_metrics = []

    if parsed["cpi"]:
        secondary_metrics.append(f"CPI {parsed['cpi']}")

    if parsed["equibase"]:
        secondary_metrics.append(f"Equibase {parsed['equibase']}")

    if secondary_metrics:
        st.caption(" · ".join(secondary_metrics))

    thorograph = parsed["thorograph"]

    if any(
        value not in (None, "", "-")
        for value in thorograph.values()
    ):
        st.markdown("##### ThoroGraph")

        tg_columns = st.columns(4)

        for column, label, key in zip(
            tg_columns,
            ["2YO", "3YO", "4YO", "5YO+"],
            ["2yo", "3yo", "4yo", "5yo+"],
        ):
            value = thorograph.get(key)
            display = "—" if value in (None, "", "-") else value

            with column:
                render_metric_card(label, display)

    performance_text = parsed.get("performance_text")

    if performance_text:
        clean_performance = re.sub(
            r"ThoroGraph\s+.*$",
            "",
            performance_text,
            flags=re.IGNORECASE,
        ).strip(" ,;-")

        if clean_performance:
            st.markdown("##### Racing Performance")
            render_plain_text(
                clean_performance,
                font_size="0.95rem",
                line_height="1.55",
            )

    sale_history = parsed.get("sale_history", [])

    if sale_history:
        st.markdown("##### Sale / Ownership History")

        for sale in sale_history:
            sale_name = (
                sale.get("sale_name")
                or sale.get("sale_code")
                or "Sale"
            )

            sale_year = sale.get("sale_year")

            heading_parts = [
                value
                for value in [sale_year, sale_name]
                if value
            ]

            heading = " · ".join(heading_parts) if heading_parts else "Sale"

            price_text = sale.get("price") or "Price not listed"

            if sale.get("rna"):
                price_text = f"{price_text} · RNA"

            safe_heading = html.escape(heading)
            safe_price = html.escape(price_text)

            details = []

            if sale.get("consignor"):
                details.append(
                    "Consignor: "
                    + html.escape(sale["consignor"])
                )

            if sale.get("buyer"):
                details.append(
                    "Buyer: "
                    + html.escape(sale["buyer"])
                )

            if sale.get("for_party"):
                details.append(
                    "For: "
                    + html.escape(sale["for_party"])
                )

            details_html = "".join(
                (
                    '<div style="font-size:0.86rem;color:#64748B;'
                    'margin-top:0.18rem;">'
                    f'{detail}</div>'
                )
                for detail in details
            )

            st.markdown(
                f"""
                <div style="
                    border:1px solid #E7E1D5;
                    border-left:4px solid #C8A96B;
                    border-radius:10px;
                    background:#FCFBF8;
                    padding:0.75rem 0.9rem;
                    margin:0.45rem 0;
                ">
                    <div style="
                        display:flex;
                        justify-content:space-between;
                        gap:1rem;
                        align-items:flex-start;
                    ">
                        <div style="
                            color:#1F2937;
                            font-size:0.94rem;
                            font-weight:700;
                            line-height:1.35;
                        ">
                            {safe_heading}
                        </div>
                        <div style="
                            color:#15392F;
                            font-size:0.94rem;
                            font-weight:800;
                            white-space:nowrap;
                        ">
                            {safe_price}
                        </div>
                    </div>
                    {details_html}
                </div>
                """,
                unsafe_allow_html=True,
            )


def parse_produce_record(record: str) -> dict[str, Any]:
    """
    Parse one first-dam produce record while preserving named offspring.
    """
    record = str(record).strip()

    year_match = re.match(
        r"^(?P<year>\d{2})-(?P<body>.+)$",
        record,
        flags=re.IGNORECASE,
    )

    year = None
    body = record

    if year_match:
        year = f"20{year_match.group('year')}"
        body = year_match.group("body").strip()

        body = re.sub(
            r"^\d{2}-(?=(?:c|f|g|h|m|r|b|dkb/br\.?|ch\.?),)",
            "",
            body,
            flags=re.IGNORECASE,
        )

    sex_pattern = r"(?:c|f|g|h|m|r|b|dkb/br\.?|ch\.?)"

    named_match = re.match(
        rf"^(?P<name>.+?),\s*"
        rf"(?P<sex>{sex_pattern}),?\s*"
        rf"by\s+(?P<sire>[^,]+)",
        body,
        flags=re.IGNORECASE,
    )

    unnamed_match = re.match(
        rf"^(?P<sex>{sex_pattern}),?\s*"
        rf"by\s+(?P<sire>[^,]+)",
        body,
        flags=re.IGNORECASE,
    )

    name = None
    sex = None
    sire = None

    if named_match:
        candidate_name = named_match.group("name").strip(" ,.-")

        if not re.fullmatch(
            sex_pattern,
            candidate_name,
            flags=re.IGNORECASE,
        ):
            name = candidate_name

        sex = named_match.group("sex").strip()
        sire = named_match.group("sire").strip()

    elif unnamed_match:
        sex = unnamed_match.group("sex").strip()
        sire = unnamed_match.group("sire").strip()

    starts_match = re.search(
        r"\b(\d+)\s+sts?\b",
        record,
        flags=re.IGNORECASE,
    )

    wins_match = re.search(
        r"\b(\d+)\s+wins?\b",
        record,
        flags=re.IGNORECASE,
    )

    earnings_match = None

    if starts_match or wins_match:
        race_record_text = re.split(
            r"\s+\d{2}[A-Z]{3,}\b",
            record,
            maxsplit=1,
            flags=re.IGNORECASE,
        )[0]

        earnings_match = re.search(
            r"\$([\d,]+)",
            race_record_text,
        )

    cpi_match = re.search(
        r"\[([\d.]+)\s*CPI\]",
        record,
        flags=re.IGNORECASE,
    )

    equibase_match = re.search(
        r"\(\s*E\s+(\d+)\s*\)",
        record,
        flags=re.IGNORECASE,
    )

    thorograph_match = re.search(
        r"ThoroGraph\s+"
        r"2yo:\s*(.*?)\s+"
        r"3yo:\s*(.*?)\s+"
        r"4yo:\s*(.*?)\s+"
        r"5yo\+:\s*(.*?)(?=\s+\d{2}[A-Z]{3,}|\s*$)",
        record,
        flags=re.IGNORECASE,
    )

    sale_match = re.search(
        r"\b(\d{2}[A-Z]{3,})\s+\$([\d,]+)",
        record,
        flags=re.IGNORECASE,
    )

    consignor_match = re.search(
        r"Consignor:\s*([^;]+)",
        record,
        flags=re.IGNORECASE,
    )

    buyer_match = re.search(
        r"Buyer:\s*([^;]+)",
        record,
        flags=re.IGNORECASE,
    )

    pedigree_match = re.search(
        r"\{([^}]+)\}\s*$",
        record,
    )

    status = None

    if re.search(r"\bUnraced\b", record, flags=re.IGNORECASE):
        status = "Unraced"
    elif starts_match:
        status = "Raced"

    performance_text = None

    if cpi_match:
        after_cpi = record[cpi_match.end():]
        performance_end = len(after_cpi)

        thorograph_index = re.search(
            r"\bThoroGraph\b",
            after_cpi,
            flags=re.IGNORECASE,
        )

        if thorograph_index:
            performance_end = thorograph_index.start()

        performance_text = (
            after_cpi[:performance_end]
            .strip(" ,;-")
            or None
        )

    return {
        "year": year,
        "name": name,
        "sex": sex,
        "sire": sire,
        "status": status,
        "starts": starts_match.group(1) if starts_match else None,
        "wins": wins_match.group(1) if wins_match else None,
        "earnings": f"${earnings_match.group(1)}" if earnings_match else None,
        "cpi": cpi_match.group(1) if cpi_match else None,
        "equibase": equibase_match.group(1) if equibase_match else None,
        "performance": performance_text,
        "thorograph": {
            "2yo": thorograph_match.group(1).strip() if thorograph_match else None,
            "3yo": thorograph_match.group(2).strip() if thorograph_match else None,
            "4yo": thorograph_match.group(3).strip() if thorograph_match else None,
            "5yo+": thorograph_match.group(4).strip() if thorograph_match else None,
        },
        "sale_code": sale_match.group(1) if sale_match else None,
        "sale_price": f"${sale_match.group(2)}" if sale_match else None,
        "consignor": consignor_match.group(1).strip() if consignor_match else None,
        "buyer": buyer_match.group(1).strip() if buyer_match else None,
        "pedigree_note": pedigree_match.group(1).strip() if pedigree_match else None,
        "raw": record,
    }


def summarize_produce_history(records: list[str]) -> dict[str, Any]:
    """
    Summarize the mare's listed produce history.

    Returns:
    - foals: number of listed produce records
    - runners: records showing at least one start / raced status
    - winners: records showing at least one win
    - best_level: highest racing level identified from the catalog text
    """
    foals = len(records)
    runners = 0
    winners = 0
    best_rank = -1
    best_level = "No winner listed"

    level_patterns = [
        (
            8,
            "Grade 1 Winner",
            r"\b(?:G1|GRADE\s*1|GR\.?\s*(?:1|I))\b",
        ),
        (
            7,
            "Grade 2 Winner",
            r"\b(?:G2|GRADE\s*2|GR\.?\s*(?:2|II))\b",
        ),
        (
            6,
            "Grade 3 Winner",
            r"\b(?:G3|GRADE\s*3|GR\.?\s*(?:3|III))\b",
        ),
        (
            5,
            "Graded Stakes Winner",
            r"\bGSW\b",
        ),
        (
            4,
            "Listed Stakes Winner",
            r"\b(?:LISTED\s+(?:STAKES\s+)?WINNER|LSTW)\b",
        ),
        (
            3,
            "Stakes Winner",
            r"\b(?:SW|STAKES\s+WINNER)\b",
        ),
        (
            2,
            "Winner",
            r"\b(?:[1-9]\d*\s+wins?|winner)\b",
        ),
        (
            1,
            "Runner",
            r"\b(?:[1-9]\d*\s+sts?|raced)\b",
        ),
        (
            0,
            "Unraced",
            r"\bunraced\b",
        ),
    ]

    for record in records:
        cleaned = str(record).strip()
        parsed = parse_produce_record(cleaned)

        starts_match = re.search(
            r"\b([1-9]\d*)\s+sts?\b",
            cleaned,
            flags=re.IGNORECASE,
        )

        wins_match = re.search(
            r"\b([1-9]\d*)\s+wins?\b",
            cleaned,
            flags=re.IGNORECASE,
        )

        if parsed.get("status") == "Raced" or starts_match:
            runners += 1

        if wins_match:
            winners += 1

        for rank, label, pattern in level_patterns:
            if re.search(pattern, cleaned, flags=re.IGNORECASE):
                if rank > best_rank:
                    best_rank = rank
                    best_level = label
                break

    return {
        "foals": foals,
        "runners": runners,
        "winners": winners,
        "best_level": best_level,
    }


def render_produce_summary(records: list[str]) -> None:
    """
    Render a compact Produce History summary beside the section title.
    """
    summary = summarize_produce_history(records)

    summary_text = (
        f"{summary['foals']} foals"
        f" · {summary['runners']} runners"
        f" · {summary['winners']} winners"
        f" · Best: {summary['best_level']}"
    )

    st.markdown(
        f"""
        <div style="
            text-align: right;
            color: #475569;
            font-size: 0.95rem;
            font-weight: 600;
            line-height: 1.45;
            padding-top: 0.35rem;
        ">
            {html.escape(summary_text)}
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_produce_card(
    record: str,
    record_number: int,
) -> None:
    parsed = parse_produce_record(record)

    with st.container(border=True):

        top_left, top_right = st.columns(
            [3, 1]
        )

        with top_left:
            title_parts = []

            if parsed["year"]:
                title_parts.append(
                    parsed["year"]
                )

            if parsed["name"]:
                title_parts.append(
                    parsed["name"]
                )

            if parsed["year"] and not parsed["name"]:
                title_parts.append("Unnamed foal")

            title = (
                " · ".join(title_parts)
                if title_parts
                else "Unnamed foal"
            )

            st.markdown(
                f"#### {title}"
            )

            subtitle_parts = []

            if parsed["sex"]:
                subtitle_parts.append(
                    parsed["sex"].upper()
                )

            if parsed["sire"]:
                subtitle_parts.append(
                    f"by {parsed['sire']}"
                )

            if subtitle_parts:
                st.caption(
                    " · ".join(
                        subtitle_parts
                    )
                )

        with top_right:
            if parsed["status"]:
                st.markdown(
                    f"""
                    <div style="
                        display:inline-block;
                        float:right;
                        background:#EEF2F7;
                        color:#334155;
                        border-radius:999px;
                        padding:0.25rem 0.7rem;
                        font-size:0.8rem;
                        font-weight:700;
                    ">
                        {html.escape(parsed["status"])}
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

        metric_values = [
            ("Starts", parsed["starts"]),
            ("Wins", parsed["wins"]),
            ("Earnings", parsed["earnings"]),
            ("CPI", parsed["cpi"]),
        ]

        if any(
            value
            for _, value in metric_values
        ):
            metric_columns = st.columns(4)

            for column, (
                label,
                value,
            ) in zip(
                metric_columns,
                metric_values,
            ):
                with column:
                    render_metric_card(
                        label,
                        value,
                    )

        if (
            parsed["performance"]
            or parsed["equibase"]
        ):
            st.markdown(
                "##### Racing Performance"
            )

            performance_parts = []

            if parsed["performance"]:
                performance_parts.append(
                    parsed["performance"]
                )

            if parsed["equibase"]:
                performance_parts.append(
                    f"Equibase {parsed['equibase']}"
                )

            render_plain_text(
                " · ".join(
                    performance_parts
                ),
                font_size="0.95rem",
                line_height="1.55",
            )

        thorograph = parsed["thorograph"]

        if any(
            value not in (
                None,
                "",
                "-",
            )
            for value in thorograph.values()
        ):
            st.markdown(
                "##### ThoroGraph"
            )

            tg_columns = st.columns(4)

            tg_labels = [
                "2YO",
                "3YO",
                "4YO",
                "5YO+",
            ]

            tg_keys = [
                "2yo",
                "3yo",
                "4yo",
                "5yo+",
            ]

            for column, label, key in zip(
                tg_columns,
                tg_labels,
                tg_keys,
            ):
                value = thorograph.get(
                    key
                )

                display = (
                    "—"
                    if value in (
                        None,
                        "",
                        "-",
                    )
                    else value
                )

                with column:
                    render_metric_card(
                        label,
                        display,
                    )

        if (
            parsed["sale_code"]
            or parsed["sale_price"]
            or parsed["consignor"]
            or parsed["buyer"]
        ):
            st.markdown(
                "##### Sale History"
            )

            sale_parts = []

            if parsed["sale_code"]:
                sale_parts.append(
                    parsed["sale_code"]
                )

            if parsed["sale_price"]:
                sale_parts.append(
                    parsed["sale_price"]
                )

            if sale_parts:
                st.markdown(
                    f"**{' · '.join(sale_parts)}**"
                )

            if parsed["consignor"]:
                st.caption(
                    f"Consignor: {parsed['consignor']}"
                )

            if parsed["buyer"]:
                st.caption(
                    f"Buyer: {parsed['buyer']}"
                )

        if parsed["pedigree_note"]:
            st.caption(
                f"Sire / pedigree note: "
                f"{parsed['pedigree_note']}"
            )


def parse_nicking_metrics(text: str) -> dict[str, str | None]:
    winner_match = re.search(r"wnrs?\s*\((\d+)%\)", text, flags=re.IGNORECASE)
    two_year_old_match = re.search(
        r"2yo\s+wnrs?\s*\((\d+)%\)",
        text,
        flags=re.IGNORECASE,
    )
    stakes_match = re.search(r"\bSW\s*\((\d+)%\)", text, flags=re.IGNORECASE)
    graded_match = re.search(r"\bGSW\s*\((\d+)%\)", text, flags=re.IGNORECASE)

    return {
        "winner_rate": f"{winner_match.group(1)}%" if winner_match else None,
        "two_year_old_rate": (
            f"{two_year_old_match.group(1)}%"
            if two_year_old_match
            else None
        ),
        "stakes_rate": f"{stakes_match.group(1)}%" if stakes_match else None,
        "graded_rate": f"{graded_match.group(1)}%" if graded_match else None,
    }


def render_nicking_section(horse: pd.Series) -> None:
    st.markdown("### Nicking Analysis")

    nicking_text = display_value(horse.get("nicking_summary"), "—")

    if nicking_text == "—":
        with st.container(border=True):
            st.caption("No nicking analysis was provided for this horse.")
        return

    metrics = parse_nicking_metrics(nicking_text)
    metric_columns = st.columns(4)

    with metric_columns[0]:
        render_metric_card("Winners", metrics["winner_rate"])

    with metric_columns[1]:
        render_metric_card("2YO Winners", metrics["two_year_old_rate"])

    with metric_columns[2]:
        render_metric_card("Stakes Winners", metrics["stakes_rate"])

    with metric_columns[3]:
        render_metric_card("Graded Winners", metrics["graded_rate"])

    with st.container(border=True):
        st.caption("FULL NICKING RECORD")
        render_plain_text(nicking_text)


def render_first_dam_section(horse: pd.Series) -> None:
    st.markdown("### First Dam")

    with st.container(border=True):
        st.caption("DAM RECORD")
        render_first_dam_record(horse.get("first_dam_record"))

    produce_records = normalize_record_list(
        horse.get("first_dam_produce")
    )

    if not produce_records:
        st.markdown("### Produce History")

        with st.container(border=True):
            st.caption(
                "No prior produce is listed for this mare in the catalog."
            )
        return

    produce_title_column, produce_summary_column = st.columns(
        [1, 2.2],
        gap="medium",
    )

    with produce_title_column:
        st.markdown("### Produce History")

    with produce_summary_column:
        render_produce_summary(produce_records)

    for record_number, record in enumerate(
        produce_records,
        start=1,
    ):
        render_produce_card(record, record_number)

def clean_ai_list(value: Any) -> list[str]:
    """
    Return AI JSONB values as a clean list of strings.
    """
    if isinstance(value, list):
        return [
            str(item).strip()
            for item in value
            if str(item).strip()
        ]

    if isinstance(value, str):
        stripped = value.strip()

        if not stripped:
            return []

        try:
            parsed = json.loads(stripped)

            if isinstance(parsed, list):
                return [
                    str(item).strip()
                    for item in parsed
                    if str(item).strip()
                ]
        except json.JSONDecodeError:
            return []

    return []


def render_ai_bullet_list(
    items: list[str],
    empty_message: str,
) -> None:
    """
    Render AI bullets without allowing catalog notation to become Markdown.
    """
    if not items:
        st.caption(empty_message)
        return

    for item in items:
        safe_item = html.escape(item)

        st.markdown(
            (
                '<div class="wpt-ai-bullet">'
                '<span class="wpt-ai-bullet-mark">•</span>'
                f'<span>{safe_item}</span>'
                '</div>'
            ),
            unsafe_allow_html=True,
        )


def render_ai_summary_panel(horse: pd.Series) -> None:
    """
    Render the stored West Point AI summary.

    Horses still being processed simply do not show this panel yet.
    """
    executive_summary = display_value(
        horse.get("executive_summary"),
        "—",
    )

    if executive_summary == "—":
        return

    key_highlights = clean_ai_list(
        horse.get("key_highlights")
    )

    watch_items = clean_ai_list(
        horse.get("watch_items")
    )

    st.markdown(
        """
        <div class="wpt-ai-heading">
            <div class="wpt-ai-eyebrow">
                WEST POINT INTELLIGENCE
            </div>
            <div class="wpt-ai-title">
                ✨ WPT Insight
            </div>
            <div class="wpt-ai-subtitle">
                A concise interpretation of the supplied catalog information
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.container(border=True):
        st.markdown("#### Executive Summary")

        render_plain_text(
            executive_summary,
            font_size="1.05rem",
            line_height="1.75",
        )

        st.divider()

        highlight_column, watch_column = st.columns(
            [1.15, 1],
            gap="large",
        )

        with highlight_column:
            st.markdown("#### Key Highlights")

            render_ai_bullet_list(
                key_highlights[:4],
                "No key highlights are available.",
            )

        with watch_column:
            st.markdown("#### What to Keep in Mind")

            render_ai_bullet_list(
                watch_items[:3],
                "No additional watch items were identified.",
            )

    st.caption(
        "Generated from the supplied Keeneland September catalog data. "
        "This summary does not predict racing performance or sale value."
    )

def render_photo_gallery(
    hip_number: int,
    photo_urls: list[str],
) -> None:
    """
    Render a simple previous/next photo gallery for a horse.
    """
    clean_urls = [
        str(url).strip()
        for url in photo_urls
        if str(url).strip()
    ]

    if not clean_urls:
        render_horse_image(
            hip_number=hip_number,
            photo_url=None,
        )
        return

    gallery_key = f"photo_index_{hip_number}"

    if gallery_key not in st.session_state:
        st.session_state[gallery_key] = 0

    current_index = st.session_state[gallery_key]

    if current_index >= len(clean_urls):
        current_index = 0
        st.session_state[gallery_key] = 0

    render_horse_image(
        hip_number=hip_number,
        photo_url=clean_urls[current_index],
    )

    if len(clean_urls) == 1:
        st.caption("1 photo available")
        return

    previous_column, count_column, next_column = st.columns(
        [1, 2, 1]
    )

    with previous_column:
        if st.button(
            "← Previous",
            key=f"photo_previous_{hip_number}",
            use_container_width=True,
        ):
            st.session_state[gallery_key] = (
                current_index - 1
            ) % len(clean_urls)
            st.rerun()

    with count_column:
        st.markdown(
            (
                "<div style='text-align:center;"
                "padding-top:0.65rem;'>"
                f"Photo <strong>{current_index + 1}</strong> "
                f"of <strong>{len(clean_urls)}</strong>"
                "</div>"
            ),
            unsafe_allow_html=True,
        )

    with next_column:
        if st.button(
            "Next →",
            key=f"photo_next_{hip_number}",
            use_container_width=True,
        ):
            st.session_state[gallery_key] = (
                current_index + 1
            ) % len(clean_urls)
            st.rerun()

def render_sales_video(
    hip_number: int,
    video_url: Any,
) -> None:
    """
    Render the sales video when available.
    """
    if video_url is None:
        return

    try:
        if pd.isna(video_url):
            return
    except (TypeError, ValueError):
        pass

    video_url = str(video_url).strip()

    if not video_url:
        return

    # Extract Vimeo video ID from URLs such as:
    # https://vimeo.com/1213418917
    vimeo_match = re.search(
        r"vimeo\.com/(\d+)",
        video_url,
    )

    if not vimeo_match:
        st.caption("Sales video is currently unavailable.")
        return

    video_id = vimeo_match.group(1)

    st.markdown("### 🎥 Sales Video")

    components.iframe(
        f"https://player.vimeo.com/video/{video_id}",
        height=420,
        scrolling=False,
    )


def render_catalog_pdf_link(pdf_url: Any) -> None:
    """
    Render a prominent link to the horse's Keeneland catalog PDF.

    The PDF opens in a new browser tab so the Streamlit app remains open
    on the current horse profile and the user's active session is preserved.
    """
    if pdf_url is None:
        return

    try:
        if pd.isna(pdf_url):
            return
    except (TypeError, ValueError):
        pass

    pdf_url = str(pdf_url).strip()

    if not pdf_url:
        return

    safe_url = html.escape(
        pdf_url,
        quote=True,
    )

    st.markdown(
     f"""
        <a href="{safe_url}" target="_blank" rel="noopener noreferrer"
        style="
         display:flex;
        align-items:center;
        justify-content:center;
        width:100%;
        box-sizing:border-box;
        margin-top:0.85rem;
        padding:0.82rem 1rem;
        background-color:#15392F;
        color:white;
        text-decoration:none;
        border-radius:8px;
        font-size:0.95rem;
        font-weight:700;
        letter-spacing:0.01em;
        ">
        <span style="color:white; text-decoration:none;">
        📄 &nbsp; View Keeneland Catalog PDF &nbsp; ↗
        </span>
        </a>
        """,        
        unsafe_allow_html=True,
    )


def render_sale_result_panel(horse: pd.Series) -> None:
    """
    Render the current Keeneland sale result prominently
    near the top of the horse profile.

    Pending horses intentionally show nothing.
    """
    sale_status = display_value(
        horse.get("sale_status"),
        "PENDING",
    ).upper()

    sale_price = horse.get("sale_price")
    purchaser = display_value(
        horse.get("purchaser"),
        "",
    )

    wpt_purchase = bool(
        horse.get(
            "wpt_purchase",
            False,
        )
    )

    if sale_status == "PENDING":
        return

    if wpt_purchase:
        st.markdown(
            """
            <div style="
                display:inline-block;
                margin-top:0.4rem;
                margin-bottom:0.75rem;
                background:#15392F;
                color:#FFFFFF;
                border-radius:999px;
                padding:0.48rem 0.9rem;
                font-size:0.82rem;
                font-weight:800;
                letter-spacing:0.07em;
                text-transform:uppercase;
            ">
                🏆 WPT PURCHASE
            </div>
            """,
            unsafe_allow_html=True,
        )

    if sale_status == "SOLD":
        price_text = format_currency(
            sale_price
        )

        st.markdown(
            f"""
            <div style="
                border:1px solid #B9D7C7;
                background:#EEF7F2;
                border-radius:10px;
                padding:0.85rem 1rem;
                margin-bottom:0.8rem;
            ">
                <div style="
                    color:#15392F;
                    font-size:0.78rem;
                    font-weight:800;
                    letter-spacing:0.06em;
                    text-transform:uppercase;
                    margin-bottom:0.25rem;
                ">
                    Sale Result
                </div>
                <div style="
                    color:#15392F;
                    font-size:1.3rem;
                    font-weight:800;
                    margin-bottom:0.25rem;
                ">
                    SOLD · {html.escape(price_text)}
                </div>
                {
                    f'<div style="color:#475569; font-size:0.92rem;">'
                    f'Purchaser: {html.escape(purchaser)}</div>'
                    if purchaser
                    else ""
                }
            </div>
            """,
            unsafe_allow_html=True,
        )

        return

    if sale_status == "NOT SOLD":
        price_text = format_currency(
            sale_price
        )

        st.markdown(
            f"""
            <div style="
                border:1px solid #E7C98A;
                background:#FFF7E8;
                border-radius:10px;
                padding:0.85rem 1rem;
                margin-bottom:0.8rem;
            ">
                <div style="
                    color:#8A5A00;
                    font-size:0.78rem;
                    font-weight:800;
                    letter-spacing:0.06em;
                    text-transform:uppercase;
                    margin-bottom:0.25rem;
                ">
                    Sale Result
                </div>
                <div style="
                    color:#8A5A00;
                    font-size:1.3rem;
                    font-weight:800;
                ">
                    NOT SOLD · {html.escape(price_text)}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        return

    if sale_status == "OUT":
        # OUT is displayed as a full takeover in the photo area.
        return



def render_out_takeover(
    hip_number: int,
) -> None:
    """
    Replace the normal horse photo area with a prominent OUT treatment.
    """
    st.markdown(
        f"""
        <div style="
            height:420px;
            border-radius:14px;
            background:#F3F4F6;
            border:1px solid #D1D5DB;
            display:flex;
            align-items:center;
            justify-content:center;
            text-align:center;
            box-sizing:border-box;
        ">
            <div>
                <div style="
                    font-size:0.9rem;
                    font-weight:800;
                    letter-spacing:0.14em;
                    text-transform:uppercase;
                    color:#6B7280;
                    margin-bottom:0.65rem;
                ">
                    HIP {hip_number}
                </div>
                <div style="
                    font-size:4.25rem;
                    line-height:1;
                    font-weight:900;
                    letter-spacing:0.04em;
                    color:#374151;
                ">
                    OUT
                </div>
                <div style="
                    margin-top:0.9rem;
                    color:#6B7280;
                    font-size:0.95rem;
                    font-weight:600;
                ">
                    Withdrawn from the sale
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_horse_profile(horse: pd.Series) -> None:
    hip_number = int(horse["hip_number"])

    if st.button("← Back to catalog"):
        st.session_state["page"] = "catalog"
        st.rerun()

    st.divider()

    image_column, summary_column = st.columns(
        [1.2, 1],
        gap="large",
    )

    with image_column:
        sale_status = display_value(
            horse.get("sale_status"),
            "PENDING",
        ).upper()

        if sale_status == "OUT":
            render_out_takeover(
                hip_number=hip_number,
            )
        else:
            render_photo_gallery(
                hip_number=hip_number,
                photo_urls=horse.get("photo_urls", []),
            )

            render_sales_video(
                hip_number=hip_number,
                video_url=horse.get("video_url"),
            )

            photo_count = horse.get("photo_count", 0)

            try:
                photo_count = int(photo_count)
            except (TypeError, ValueError):
                photo_count = 0

            if photo_count > 1:
                st.caption(
                    f"{photo_count} photos available for Hip {hip_number}"
                )

    with summary_column:
        sale_day = display_value(
            horse.get("sale_day"),
            "—",
        )

        book_number = display_value(
            horse.get("book_number"),
            "—",
        )

        sale_date_value = horse.get("sale_date")
        try:
            sale_date = pd.to_datetime(sale_date_value).strftime("%b %d, %Y")
        except (TypeError, ValueError):
            sale_date = "—"

        sex_label = format_sex(
            horse.get("sex")
        )

        sire = html.escape(
            display_value(horse.get("sire"))
        )

        dam = html.escape(
            display_value(horse.get("dam"))
        )

        st.markdown(
            (
                '<div class="wpt-profile-eyebrow">'
                'KEENELAND SEPTEMBER'
                '<span class="wpt-profile-dot">•</span>'
                f'BOOK {html.escape(book_number)}'
                '<span class="wpt-profile-dot">•</span>'
                f'DAY {html.escape(sale_day)}'
                '</div>'
            ),
            unsafe_allow_html=True,
        )

        st.markdown(
            f'<div class="wpt-profile-hip">HIP {hip_number}</div>',
            unsafe_allow_html=True,
        )

        st.markdown(
            (
                '<div class="wpt-profile-pedigree">'
                f'<span class="wpt-profile-sire">{sire}</span>'
                '<span class="wpt-profile-cross">×</span>'
                f'<span class="wpt-profile-dam">{dam}</span>'
                '</div>'
            ),
            unsafe_allow_html=True,
        )

        render_sale_result_panel(
            horse
        )

        st.markdown(
            (
                '<div style="margin-top:0.9rem; margin-bottom:0.6rem;">'
                '<span style="'
                'display:inline-block;'
                'background:#15392F;'
                'color:#FFFFFF;'
                'border-radius:999px;'
                'padding:0.5rem 0.95rem;'
                'font-size:0.92rem;'
                'font-weight:800;'
                'letter-spacing:0.08em;'
                'text-transform:uppercase;'
                '">'
                f'{html.escape(sex_label)}'
                '</span>'
                '</div>'
            ),
            unsafe_allow_html=True,
        )

        st.markdown(
            (
                '<div class="wpt-profile-tags">'
                f'<span class="wpt-profile-tag">Book {html.escape(book_number)}</span>'
                f'<span class="wpt-profile-tag">Sale Day {html.escape(sale_day)}</span>'
                f'<span class="wpt-profile-tag">{html.escape(sale_date)}</span>'
                '</div>'
            ),
            unsafe_allow_html=True,
        )

        st.markdown(
            '<div class="wpt-profile-rule"></div>',
            unsafe_allow_html=True,
        )

        # Current Keeneland sale details
        sale_detail_1, sale_detail_2 = st.columns(
            [1, 1],
            gap="medium",
        )

        with sale_detail_1:
            render_metric_card(
                "Book",
                book_number,
            )

        with sale_detail_2:
            render_metric_card(
                "Sale Date",
                sale_date,
            )

        render_catalog_pdf_link(
            horse.get("pdf_url")
        )

        metric_1, metric_2 = st.columns(2)

        with metric_1:
            render_metric_card(
                "TrueNicks",
                display_value(
                    horse.get("true_nicks_rating"),
                    "—",
                ),
            )

        with metric_2:
            render_metric_card(
                "Broodmare Sire",
                display_value(
                    horse.get("broodmare_sire"),
                    "—",
                ),
            )

        render_metric_card(
            "Dosage Index",
            display_value(
                horse.get("dosage_index"),
                "—",
            ),
        )

    st.divider()

    render_ai_summary_panel(horse)

    if horse.get("has_ai_summary", False):
        st.divider()

    overview_tab, pedigree_tab, commercial_tab = st.tabs(
        [
            "📖 Overview",
            "🧬 Pedigree",
            "💰 Commercial",
        ]
    )

    with overview_tab:
        first_dam_column, nicking_column = st.columns(
            [1.45, 1],
            gap="large",
        )

        with first_dam_column:
            render_first_dam_section(horse)

        with nicking_column:
            render_nicking_section(horse)

    with pedigree_tab:
        left_column, right_column = st.columns(
            2,
            gap="large",
        )

        with left_column:
            section_header("Pedigree", "🧬")
            info_row("Sire", display_value(horse["sire"]))
            info_row("Dam", display_value(horse["dam"]))
            info_row(
                "Broodmare Sire",
                display_value(
                    horse["broodmare_sire"]
                ),
            )

        with right_column:
            section_header("Breeding", "📋")
            info_row("Breeder", display_value(horse["breeder"]))
            info_row(
                "First Foals",
                display_value(
                    horse["first_foals_year"]
                ),
            )
            info_row(
                "Dosage Profile",
                display_value(
                    horse["dosage_profile"]
                ),
            )
            info_row(
                "Center of Distribution",
                display_value(
                    horse["center_of_distribution"]
                ),
            )

    with commercial_tab:
        st.markdown("### Commercial Snapshot")

        snapshot_1, snapshot_2, snapshot_3 = st.columns(3)

        with snapshot_1:
            render_metric_card(
                "Previous Sale",
                extract_money(
                    display_value(
                        horse.get("previous_sale_history"),
                        "",
                    )
                )
                or "—",
            )

        with snapshot_2:
            render_metric_card(
                "2026 Stud Fee",
                format_currency(
                    horse.get("stud_fee_2026")
                ),
            )

        with snapshot_3:
            render_metric_card(
                "TrueNicks",
                display_value(
                    horse.get("true_nicks_rating"),
                    "—",
                ),
            )

        st.markdown("### Sale History")

        with st.container(border=True):
            previous_sale_history = display_value(
                horse.get("previous_sale_history"),
                "—",
            )

            if previous_sale_history == "—":
                st.caption(
                    "No previous sale history is available."
                )
            else:
                render_plain_text(
                    previous_sale_history,
                    font_size="0.98rem",
                    line_height="1.65",
                )

        st.markdown("### Sire Market Performance")

        market_column_1, market_column_2, market_column_3 = st.columns(
            3,
            gap="large",
        )

        with market_column_1:
            with st.container(border=True):
                st.markdown("#### 2025 Weanlings")

                render_plain_text(
                    horse.get("weanling_2025_stats"),
                    empty_message=(
                        "No weanling market statistics are available."
                    ),
                    font_size="0.92rem",
                    line_height="1.55",
                )

        with market_column_2:
            with st.container(border=True):
                st.markdown("#### 2025 Yearlings")

                render_plain_text(
                    horse.get("yearling_2025_stats"),
                    empty_message=(
                        "No yearling market statistics are available."
                    ),
                    font_size="0.92rem",
                    line_height="1.55",
                )

        with market_column_3:
            with st.container(border=True):
                st.markdown("#### 2026 Two-Year-Olds")

                render_plain_text(
                    horse.get("two_year_old_2026_stats"),
                    empty_message=(
                        "No two-year-old market statistics are available."
                    ),
                    font_size="0.92rem",
                    line_height="1.55",
                )

        st.markdown("### Stud Fee Trend")

        fee_column_1, fee_column_2 = st.columns(2)

        with fee_column_1:
            render_metric_card(
                "2024 Stud Fee",
                format_currency(
                    horse.get("stud_fee_2024")
                ),
            )

        with fee_column_2:
            render_metric_card(
                "2026 Stud Fee",
                format_currency(
                    horse.get("stud_fee_2026")
                ),
            )