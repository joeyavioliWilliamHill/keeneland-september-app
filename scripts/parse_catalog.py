import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

import pymupdf


OUTPUT_FILENAME = "keeneland_september_2026_horses_v0.json"


# ---------------------------------------------------------------------------
# KEENELAND SEPTEMBER 2026 SALE STRUCTURE
# ---------------------------------------------------------------------------

BOOK_CONFIG = {
    1: {
        "filename": "AuctionEdge-2026-KEESEP-Book 1.pdf",
        "sessions": [
            {
                "sale_day": 1,
                "sale_date": "2026-09-14",
                "min_hip": 1,
                "max_hip": 181,
            },
            {
                "sale_day": 2,
                "sale_date": "2026-09-15",
                "min_hip": 191,
                "max_hip": 373,
            },
        ],
    },
    2: {
        "filename": "AuctionEdge-2026-KEESEP-Book 2.pdf",
        "sessions": [
            {
                "sale_day": 3,
                "sale_date": "2026-09-16",
                "min_hip": 381,
                "max_hip": 757,
            },
            {
                "sale_day": 4,
                "sale_date": "2026-09-17",
                "min_hip": 758,
                "max_hip": 1136,
            },
        ],
    },
    3: {
        "filename": "AuctionEdge-2026-KEESEP-Book 3.pdf",
        "sessions": [
            {
                "sale_day": 5,
                "sale_date": "2026-09-19",
                "min_hip": 1137,
                "max_hip": 1552,
            },
            {
                "sale_day": 6,
                "sale_date": "2026-09-20",
                "min_hip": 1553,
                "max_hip": 1975,
            },
        ],
    },
    4: {
        "filename": "AuctionEdge-2026-KEESEP-Book 4.pdf",
        "sessions": [
            {
                "sale_day": 7,
                "sale_date": "2026-09-21",
                "min_hip": 1976,
                "max_hip": 2392,
            },
            {
                "sale_day": 8,
                "sale_date": "2026-09-22",
                "min_hip": 2393,
                "max_hip": 2815,
            },
        ],
    },
    5: {
        "filename": "AuctionEdge-2026-KEESEP-Book 5.pdf",
        "sessions": [
            {
                "sale_day": 9,
                "sale_date": "2026-09-23",
                "min_hip": 2816,
                "max_hip": 3242,
            },
            {
                "sale_day": 10,
                "sale_date": "2026-09-24",
                "min_hip": 3243,
                "max_hip": 3673,
            },
        ],
    },
    6: {
        "filename": "AuctionEdge-2026-KEESEP-Book 6.pdf",
        "sessions": [
            {
                "sale_day": 11,
                "sale_date": "2026-09-25",
                "min_hip": 3674,
                "max_hip": 4169,
            },
            {
                "sale_day": 12,
                "sale_date": "2026-09-26",
                "min_hip": 4170,
                "max_hip": 4650,
            },
        ],
    },
}


# ---------------------------------------------------------------------------
# TEXT CLEANING
# ---------------------------------------------------------------------------

def normalize_text(value: str | None) -> str:
    if not value:
        return ""

    text = value.replace("\u00a0", " ")
    text = text.replace("\u200b", "")
    text = text.replace("\ufeff", "")
    text = text.replace("\u2028", "\n")
    text = text.replace("\u2029", "\n")

    # Reconnect words split across PDF lines.
    text = re.sub(r"([A-Za-z])-\n([a-z])", r"\1\2", text)

    # Remove long dot leaders.
    text = re.sub(r"(?:\.\s*){5,}", " ", text)

    # Remove Auction Edge branding.
    text = re.sub(
        r"A\s*U\s*C\s*T\s*I\s*O\s*N\s*"
        r"E\s*D\s*G\s*E\s*[■▪•]?",
        "",
        text,
        flags=re.IGNORECASE,
    )

    # Remove BloodHorse branding.
    text = re.sub(
        r"B\s*l\s*o\s*o\s*d\s*H\s*o\s*r\s*s\s*e"
        r"\s*\.\s*c\s*o\s*m",
        "",
        text,
        flags=re.IGNORECASE,
    )

    # Remove InDesign artifacts.
    text = re.sub(
        r"[A-Z0-9_-]+\.indd[^\n]*",
        "",
        text,
        flags=re.IGNORECASE,
    )

    lines: list[str] = []

    for raw_line in text.splitlines():
        line = re.sub(r"[ \t]+", " ", raw_line).strip()

        if line:
            lines.append(line)

    return "\n".join(lines)


def compact_text(value: str | None) -> str | None:
    if not value:
        return None

    text = normalize_text(value)
    text = re.sub(r"\s+", " ", text).strip()

    return text or None


def clean_numeric(value: str | None) -> float | int | None:
    if not value:
        return None

    cleaned = (
        value.replace("$", "")
        .replace(",", "")
        .replace("%", "")
        .strip()
    )

    try:
        number = float(cleaned)

        if number.is_integer():
            return int(number)

        return number

    except ValueError:
        return None


# ---------------------------------------------------------------------------
# PDF EXTRACTION
# ---------------------------------------------------------------------------

def extract_pdf_text(pdf_path: Path) -> str:
    document = pymupdf.open(pdf_path)
    pages: list[str] = []

    try:
        for page in document:
            pages.append(page.get_text("text"))

    finally:
        document.close()

    return normalize_text("\n".join(pages))


# ---------------------------------------------------------------------------
# HORSE BOUNDARY DETECTION
# ---------------------------------------------------------------------------

def horse_boundary_pattern() -> re.Pattern[str]:
    """
    Detect the beginning of an Auction Edge horse record.

    IMPORTANT:
    Keeneland has hips above 1000, so we allow 1-4 digits.
    """

    return re.compile(
        r"(?m)^"
        r"(?P<hip>\d{1,4})"
        r"\s*[•·]\s*"
        r"(?:[^,\n]{1,60},\s*)?"
        r"Yrlg\.",
        flags=re.IGNORECASE,
    )


def split_horse_blocks(full_text: str) -> list[tuple[int, str]]:
    matches = list(horse_boundary_pattern().finditer(full_text))
    blocks: list[tuple[int, str]] = []

    for index, match in enumerate(matches):
        start = match.start()

        if index + 1 < len(matches):
            end = matches[index + 1].start()
        else:
            end = len(full_text)

        blocks.append(
            (
                int(match.group("hip")),
                full_text[start:end].strip(),
            )
        )

    return blocks


# ---------------------------------------------------------------------------
# KEENELAND BOOK / SESSION HELPERS
# ---------------------------------------------------------------------------

def hip_is_valid_for_book(
    hip_number: int,
    book_number: int,
) -> bool:
    config = BOOK_CONFIG[book_number]

    for session in config["sessions"]:
        if session["min_hip"] <= hip_number <= session["max_hip"]:
            return True

    return False


def get_session_info(
    hip_number: int,
    book_number: int,
) -> dict[str, Any] | None:
    config = BOOK_CONFIG[book_number]

    for session in config["sessions"]:
        if session["min_hip"] <= hip_number <= session["max_hip"]:
            return session

    return None


# ---------------------------------------------------------------------------
# HEADER PARSING
# ---------------------------------------------------------------------------

def get_header_text(block: str) -> str:
    end = len(block)

    for pattern in [
        r"(?im)^First Foals\s*:",
        r"(?im)^1st Dam\s*$",
    ]:
        match = re.search(pattern, block)

        if match:
            end = min(end, match.start())

    return block[:end].strip()


def parse_horse_header(
    boundary_hip: int,
    block: str,
) -> dict[str, Any]:
    header_text = get_header_text(block)

    header_match = re.search(
        r"^\s*"
        r"(?P<hip>\d{1,4})"
        r"\s*[•·]\s*"
        r"(?:(?P<label>[^,\n]{1,60}),\s*)?"
        r"Yrlg\.\s*"
        r"(?P<sex>[^,\n]+?)"
        r"\s*,\s*"
        r"by\s+"
        r"(?P<sire>.+?)"
        r"\s*[—–]\s*"
        r"(?P<dam>.+?)"
        r"\s+by\s+"
        r"(?P<broodmare_sire>.+?)"
        r"\s*,\s*"
        r"Breeder\s+"
        r"(?P<breeder>.+?)"
        r"(?:\s+\([A-Z]{2,3}\))?"
        r"(?="
        r"\s*(?:"
        r"\[(?:A\+\+|A\+|A|B\+|B|C\+|C|D|F|NR)\]"
        r"|"
        r"\d{2}[A-Z]{3,10}\b"
        r"|"
        r"First Foals\s*:"
        r"|"
        r"Dosage\s*:"
        r"|"
        r"1st Dam"
        r"|"
        r"$"
        r")"
        r")",
        header_text,
        flags=re.IGNORECASE | re.DOTALL,
    )

    if not header_match:
        preview = compact_text(header_text) or ""

        raise ValueError(
            "Could not parse isolated horse header: "
            f"{preview[:300]}"
        )

    parsed_hip = int(header_match.group("hip"))

    if parsed_hip != boundary_hip:
        raise ValueError(
            f"Boundary Hip {boundary_hip} "
            f"does not match header Hip {parsed_hip}"
        )

    rating_match = re.search(
        r"\[(?P<rating>A\+\+|A\+|A|B\+|B|C\+|C|D|F|NR)\]",
        header_text,
        flags=re.IGNORECASE,
    )

    breeder = compact_text(header_match.group("breeder"))

    if breeder:
        breeder = re.sub(
            r"\s+\([A-Z]{2,3}\)\s*$",
            "",
            breeder,
            flags=re.IGNORECASE,
        ).strip()

    return {
        "hip_number": parsed_hip,
        "catalog_label": compact_text(
            header_match.group("label")
        ),
        "sex": compact_text(
            header_match.group("sex")
        ),
        "sire": compact_text(
            header_match.group("sire")
        ),
        "dam": compact_text(
            header_match.group("dam")
        ),
        "broodmare_sire": compact_text(
            header_match.group("broodmare_sire")
        ),
        "breeder": breeder,
        "true_nicks_rating": (
            compact_text(rating_match.group("rating"))
            if rating_match
            else None
        ),
    }


# ---------------------------------------------------------------------------
# GENERIC SECTION EXTRACTION
# ---------------------------------------------------------------------------

def extract_between(
    text: str,
    start_pattern: str,
    end_patterns: list[str],
) -> str | None:
    start_match = re.search(
        start_pattern,
        text,
        flags=re.IGNORECASE | re.MULTILINE,
    )

    if not start_match:
        return None

    section_start = start_match.end()
    section_end = len(text)

    for end_pattern in end_patterns:
        end_match = re.search(
            end_pattern,
            text[section_start:],
            flags=re.IGNORECASE | re.MULTILINE,
        )

        if end_match:
            section_end = min(
                section_end,
                section_start + end_match.start(),
            )

    result = text[section_start:section_end].strip()

    return result or None


# ---------------------------------------------------------------------------
# SUBJECT HORSE SALE HISTORY
# ---------------------------------------------------------------------------

def extract_subject_sale_history(
    header_section: str,
) -> str | None:
    rating_match = re.search(
        r"\[(?:A\+\+|A\+|A|B\+|B|C\+|C|D|F|NR)\]",
        header_section,
        flags=re.IGNORECASE,
    )

    first_foals_match = re.search(
        r"(?im)^First Foals\s*:",
        header_section,
    )

    if not rating_match:
        return None

    start = rating_match.end()

    if first_foals_match:
        end = first_foals_match.start()
    else:
        end = len(header_section)

    candidate = compact_text(
        header_section[start:end]
    )

    if not candidate:
        return None

    if not re.search(
        r"\b\d{2}[A-Z]{3,10}\b",
        candidate,
        flags=re.IGNORECASE,
    ):
        return None

    return candidate


# ---------------------------------------------------------------------------
# HEADER METRICS
# ---------------------------------------------------------------------------

def extract_header_fields(block: str) -> dict[str, Any]:
    first_dam_match = re.search(
        r"(?im)^1st Dam\s*$",
        block,
    )

    if first_dam_match:
        header_section = block[:first_dam_match.start()]
    else:
        header_section = block

    first_foals_match = re.search(
        r"First Foals:\s*(\d{4})",
        header_section,
        re.IGNORECASE,
    )

    stud_fee_2026_match = re.search(
        r"2026 Stud Fee:\s*\$([\d,]+)",
        header_section,
        re.IGNORECASE,
    )

    stud_fee_2024_match = re.search(
        r"2024 Stud Fee:\s*\$([\d,]+)",
        header_section,
        re.IGNORECASE,
    )

    dosage_match = re.search(
        r"Dosage:\s*(\([^)]+\))",
        header_section,
        re.IGNORECASE,
    )

    dosage_index_match = re.search(
        r"\bDI:\s*([-\d.]+)",
        header_section,
        re.IGNORECASE,
    )

    center_distribution_match = re.search(
        r"\bCD:\s*([-\d.]+)",
        header_section,
        re.IGNORECASE,
    )

    weanling_match = re.search(
        r"(?im)^2025 Wnlg\. Avg:\s*(.+)$",
        header_section,
    )

    yearling_match = re.search(
        r"(?im)^2025 Yrlg\. Avg:\s*(.+)$",
        header_section,
    )

    two_year_old_match = re.search(
        r"(?im)^2026 2yo\. Avg:\s*(.+)$",
        header_section,
    )

    return {
        "previous_sale_history": (
            extract_subject_sale_history(header_section)
        ),
        "first_foals_year": (
            int(first_foals_match.group(1))
            if first_foals_match
            else None
        ),
        "stud_fee_2026": (
            clean_numeric(stud_fee_2026_match.group(1))
            if stud_fee_2026_match
            else None
        ),
        "stud_fee_2024": (
            clean_numeric(stud_fee_2024_match.group(1))
            if stud_fee_2024_match
            else None
        ),
        "dosage_profile": (
            dosage_match.group(1)
            if dosage_match
            else None
        ),
        "dosage_index": (
            clean_numeric(dosage_index_match.group(1))
            if dosage_index_match
            else None
        ),
        "center_of_distribution": (
            clean_numeric(
                center_distribution_match.group(1)
            )
            if center_distribution_match
            else None
        ),
        "weanling_2025_stats": (
            compact_text(weanling_match.group(1))
            if weanling_match
            else None
        ),
        "yearling_2025_stats": (
            compact_text(yearling_match.group(1))
            if yearling_match
            else None
        ),
        "two_year_old_2026_stats": (
            compact_text(two_year_old_match.group(1))
            if two_year_old_match
            else None
        ),
    }


# ---------------------------------------------------------------------------
# FIRST DAM
# ---------------------------------------------------------------------------

def parse_first_dam_section(
    block: str,
) -> dict[str, Any]:
    first_dam_section = extract_between(
        block,
        start_pattern=r"(?im)^1st Dam\s*$",
        end_patterns=[
            r"(?im)^2nd Dam\s*$",
            r"(?im)^Nicking\s*:",
            r"(?im)^NOTES\s*$",
        ],
    )

    if not first_dam_section:
        return {
            "first_dam_summary": None,
            "first_dam_record": None,
            "first_dam_produce": [],
        }

    lines = [
        line.strip()
        for line in first_dam_section.splitlines()
        if line.strip()
    ]

    produce_pattern = re.compile(
        r"^\d{2}\s*[-–—]"
    )

    produce_start: int | None = None

    for index, line in enumerate(lines):
        if produce_pattern.match(line):
            produce_start = index
            break

    if produce_start is None:
        dam_record_lines = lines
        produce_lines: list[str] = []

    else:
        dam_record_lines = lines[:produce_start]
        produce_lines = lines[produce_start:]

    first_dam_record = compact_text(
        "\n".join(dam_record_lines)
    )

    produce_records: list[str] = []
    current_record: list[str] = []

    for line in produce_lines:
        if produce_pattern.match(line):
            if current_record:
                record = compact_text(
                    "\n".join(current_record)
                )

                if record:
                    produce_records.append(record)

            current_record = [line]

        else:
            current_record.append(line)

    if current_record:
        record = compact_text(
            "\n".join(current_record)
        )

        if record:
            produce_records.append(record)

    return {
        "first_dam_summary": compact_text(
            first_dam_section
        ),
        "first_dam_record": first_dam_record,
        "first_dam_produce": produce_records,
    }


# ---------------------------------------------------------------------------
# NICKING
# ---------------------------------------------------------------------------

def parse_nicking_section(block: str) -> str | None:
    nicking = extract_between(
        block,
        start_pattern=r"(?im)^Nicking\s*:\s*",
        end_patterns=[
            r"(?im)^NOTES\s*$",
            (
                r"(?im)^\d{1,4}\s*[•·]\s*"
                r"(?:[^,\n]{1,60},\s*)?"
                r"Yrlg\."
            ),
        ],
    )

    return compact_text(nicking)


# ---------------------------------------------------------------------------
# HORSE PARSER
# ---------------------------------------------------------------------------

def parse_horse(
    hip_number: int,
    block: str,
    book_number: int,
    source_pdf: str,
) -> dict[str, Any]:
    header = parse_horse_header(
        boundary_hip=hip_number,
        block=block,
    )

    session = get_session_info(
        hip_number=hip_number,
        book_number=book_number,
    )

    if session is None:
        raise ValueError(
            f"Hip {hip_number} does not belong "
            f"to Book {book_number}"
        )

    return {
        **header,

        "book_number": book_number,
        "sale_day": session["sale_day"],
        "sale_date": session["sale_date"],
        "source_pdf": source_pdf,

        **extract_header_fields(block),
        **parse_first_dam_section(block),

        "nicking_summary": parse_nicking_section(block),
        "raw_record": block,
    }


# ---------------------------------------------------------------------------
# VALIDATION
# ---------------------------------------------------------------------------

def validate_horses(
    horses: list[dict[str, Any]],
) -> list[str]:
    warnings: list[str] = []
    seen_hips: set[int] = set()

    for horse in horses:
        hip_number = int(horse["hip_number"])

        if hip_number in seen_hips:
            warnings.append(
                f"Duplicate Hip {hip_number}"
            )

        seen_hips.add(hip_number)

        for field in [
            "sex",
            "sire",
            "dam",
            "broodmare_sire",
            "breeder",
        ]:
            if not horse.get(field):
                warnings.append(
                    f"Hip {hip_number}: missing {field}"
                )

        if not horse.get("first_dam_summary"):
            warnings.append(
                f"Hip {hip_number}: "
                "missing first dam section"
            )

        if not horse.get("nicking_summary"):
            warnings.append(
                f"Hip {hip_number}: "
                "missing nicking section"
            )

    return warnings


# ---------------------------------------------------------------------------
# OUTPUT
# ---------------------------------------------------------------------------

def write_json(
    horses: list[dict[str, Any]],
    output_path: Path,
) -> None:
    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with output_path.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            horses,
            file,
            ensure_ascii=False,
            indent=2,
        )


# ---------------------------------------------------------------------------
# REPORTING
# ---------------------------------------------------------------------------

def print_book_summary(
    horses: list[dict[str, Any]],
) -> None:
    print()
    print("=" * 100)
    print("KEENELAND BOOK SUMMARY")
    print("=" * 100)

    counts = Counter(
        horse["book_number"]
        for horse in horses
    )

    for book_number in range(1, 7):
        book_horses = [
            horse
            for horse in horses
            if horse["book_number"] == book_number
        ]

        if book_horses:
            hips = [
                int(horse["hip_number"])
                for horse in book_horses
            ]

            print(
                f"Book {book_number}: "
                f"{counts[book_number]} horses | "
                f"Hip {min(hips)} - Hip {max(hips)}"
            )

        else:
            print(
                f"Book {book_number}: 0 horses"
            )

    print("-" * 100)
    print(f"TOTAL: {len(horses)} horses")
    print("=" * 100)


def print_session_summary(
    horses: list[dict[str, Any]],
) -> None:
    print()
    print("=" * 100)
    print("SALE SESSION SUMMARY")
    print("=" * 100)

    for sale_day in range(1, 13):
        day_horses = [
            horse
            for horse in horses
            if horse["sale_day"] == sale_day
        ]

        if not day_horses:
            print(
                f"Sale Day {sale_day}: 0 horses"
            )
            continue

        hips = [
            int(horse["hip_number"])
            for horse in day_horses
        ]

        sale_date = day_horses[0]["sale_date"]

        print(
            f"Sale Day {sale_day} | "
            f"{sale_date} | "
            f"{len(day_horses)} horses | "
            f"Hip {min(hips)} - Hip {max(hips)}"
        )

    print("=" * 100)


def print_preview(
    horses: list[dict[str, Any]],
    count: int,
) -> None:
    print()
    print("=" * 100)
    print("PARSED HORSE PREVIEW")
    print("=" * 100)

    for horse in horses[:count]:
        print()
        print("-" * 100)

        print(
            f"HIP: {horse['hip_number']} | "
            f"BOOK: {horse['book_number']} | "
            f"SALE DAY: {horse['sale_day']} | "
            f"DATE: {horse['sale_date']}"
        )

        print(f"SEX: {horse['sex']}")
        print(f"SIRE: {horse['sire']}")
        print(f"DAM: {horse['dam']}")
        print(
            f"BROODMARE SIRE: "
            f"{horse['broodmare_sire']}"
        )
        print(
            f"BREEDER: "
            f"{horse['breeder']}"
        )
        print(
            f"TRUE NICKS: "
            f"{horse['true_nicks_rating']}"
        )
        print(
            f"PREVIOUS SALE: "
            f"{horse['previous_sale_history']}"
        )
        print(
            f"FIRST DAM RECORD: "
            f"{horse['first_dam_record']}"
        )

        print(
            f"PRODUCE RECORDS: "
            f"{len(horse['first_dam_produce'])}"
        )

        for record in horse[
            "first_dam_produce"
        ][:3]:
            print(f"  - {record}")

        print(
            f"NICKING: "
            f"{horse['nicking_summary']}"
        )

    print()
    print("=" * 100)


# ---------------------------------------------------------------------------
# COMMAND LINE ARGUMENTS
# ---------------------------------------------------------------------------

def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Parse all six books of the 2026 "
            "Keeneland September Yearling Sale "
            "Auction Edge catalog."
        )
    )

    parser.add_argument(
        "--preview-count",
        type=int,
        default=10,
        help="Number of parsed horses to preview.",
    )

    parser.add_argument(
        "--book",
        type=int,
        choices=range(1, 7),
        default=None,
        help=(
            "Parse a single book for testing. "
            "Default parses all six books."
        ),
    )

    return parser.parse_args()


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

def main() -> None:
    args = parse_arguments()

    project_root = (
        Path(__file__).resolve().parent.parent
    )

    data_dir = project_root / "data"

    output_path = (
        data_dir / OUTPUT_FILENAME
    )

    if args.book:
        books_to_parse = [args.book]
    else:
        books_to_parse = list(
            sorted(BOOK_CONFIG.keys())
        )

    all_horses: list[dict[str, Any]] = []
    parse_failures: list[str] = []

    print()
    print("=" * 100)
    print(
        "2026 KEENELAND SEPTEMBER "
        "YEARLING SALE PARSER"
    )
    print("=" * 100)

    for book_number in books_to_parse:
        config = BOOK_CONFIG[book_number]

        pdf_path = (
            data_dir / config["filename"]
        )

        if not pdf_path.exists():
            raise FileNotFoundError(
                f"Book {book_number} PDF "
                f"not found: {pdf_path}"
            )

        print()
        print("-" * 100)
        print(
            f"BOOK {book_number}: "
            f"{config['filename']}"
        )
        print("-" * 100)

        print("Reading PDF...")

        full_text = extract_pdf_text(
            pdf_path
        )

        blocks = split_horse_blocks(
            full_text
        )

        print(
            f"Found {len(blocks)} "
            "possible horse boundaries."
        )

        valid_blocks = [
            (hip_number, block)
            for hip_number, block in blocks
            if hip_is_valid_for_book(
                hip_number=hip_number,
                book_number=book_number,
            )
        ]

        rejected_count = (
            len(blocks) - len(valid_blocks)
        )

        print(
            f"Accepted {len(valid_blocks)} "
            f"boundaries for Book {book_number}."
        )

        if rejected_count:
            print(
                f"Rejected {rejected_count} "
                "front-matter/out-of-range "
                "boundary match(es)."
            )

        book_horses: list[
            dict[str, Any]
        ] = []

        for hip_number, block in valid_blocks:
            try:
                horse = parse_horse(
                    hip_number=hip_number,
                    block=block,
                    book_number=book_number,
                    source_pdf=config[
                        "filename"
                    ],
                )

                book_horses.append(horse)

            except Exception as error:
                parse_failures.append(
                    f"Book {book_number} | "
                    f"Hip {hip_number}: "
                    f"{error}"
                )

        book_horses.sort(
            key=lambda horse: int(
                horse["hip_number"]
            )
        )

        all_horses.extend(book_horses)

        if book_horses:
            hips = [
                int(horse["hip_number"])
                for horse in book_horses
            ]

            print(
                f"Successfully parsed "
                f"{len(book_horses)} horses | "
                f"Hip {min(hips)} - "
                f"Hip {max(hips)}"
            )

        else:
            print(
                "WARNING: No horses "
                "successfully parsed."
            )

    # Sort consolidated catalog.
    all_horses.sort(
        key=lambda horse: int(
            horse["hip_number"]
        )
    )

    # -----------------------------------------------------------------------
    # PARSE FAILURES
    # -----------------------------------------------------------------------

    if parse_failures:
        print()
        print("=" * 100)
        print(
            f"PARSE FAILURES "
            f"({len(parse_failures)})"
        )
        print("=" * 100)

        for failure in parse_failures[:100]:
            print(f"- {failure}")

        if len(parse_failures) > 100:
            print(
                f"... plus "
                f"{len(parse_failures) - 100} "
                "additional failures."
            )

    else:
        print()
        print(
            "No horse-header parse failures."
        )

    # -----------------------------------------------------------------------
    # VALIDATION
    # -----------------------------------------------------------------------

    warnings = validate_horses(
        all_horses
    )

    if warnings:
        print()
        print("=" * 100)
        print(
            f"VALIDATION WARNINGS "
            f"({len(warnings)})"
        )
        print("=" * 100)

        for warning in warnings[:100]:
            print(f"- {warning}")

        if len(warnings) > 100:
            print(
                f"... plus "
                f"{len(warnings) - 100} "
                "additional warnings."
            )

    else:
        print()
        print(
            "No validation warnings."
        )

    # -----------------------------------------------------------------------
    # REPORTING
    # -----------------------------------------------------------------------

    print_book_summary(
        all_horses
    )

    print_session_summary(
        all_horses
    )

    print_preview(
        horses=all_horses,
        count=max(
            1,
            args.preview_count,
        ),
    )

    # -----------------------------------------------------------------------
    # WRITE JSON
    # -----------------------------------------------------------------------

    write_json(
        horses=all_horses,
        output_path=output_path,
    )

    print()
    print("=" * 100)
    print("COMPLETE")
    print("=" * 100)

    print(
        f"Parsed horses: "
        f"{len(all_horses)}"
    )

    print(
        f"Parse failures: "
        f"{len(parse_failures)}"
    )

    print(
        f"Validation warnings: "
        f"{len(warnings)}"
    )

    print(
        f"JSON written to:"
    )

    print(output_path)

    print("=" * 100)


if __name__ == "__main__":
    main()