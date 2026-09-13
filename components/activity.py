import time
import uuid

import psycopg2
import streamlit as st

from components.auth import get_secret


TOUCH_INTERVAL_SECONDS = 60


def get_database_url() -> str:
    database_url = get_secret("DATABASE_URL")

    if not database_url:
        raise ValueError(
            "DATABASE_URL is missing from Streamlit secrets or .env."
        )

    return database_url


def ensure_session_id() -> str:
    if "analytics_session_id" not in st.session_state:
        st.session_state["analytics_session_id"] = str(uuid.uuid4())

    return str(st.session_state["analytics_session_id"])


def current_identity() -> tuple[str, str, str]:
    return (
        str(st.session_state.get("user_id", "")),
        str(st.session_state.get("user_email", "")),
        str(st.session_state.get("browser_id", "")),
    )


def _execute(query: str, params: tuple) -> None:
    with psycopg2.connect(get_database_url()) as connection:
        with connection.cursor() as cursor:
            cursor.execute(query, params)


def start_or_touch_session(
    page: str,
    hip_number: int | None = None,
    force: bool = False,
) -> None:
    """
    Upsert the current Streamlit session.

    Writes are throttled to avoid hitting Postgres on every harmless rerun.
    A page/horse change always forces a touch.
    """
    session_id = ensure_session_id()
    user_id, email, browser_id = current_identity()

    if not user_id or not email or not browser_id:
        return

    now = time.time()
    last_touch = float(
        st.session_state.get("analytics_last_touch", 0.0)
    )
    last_context = st.session_state.get("analytics_last_context")
    context = (page, hip_number)

    should_touch = (
        force
        or context != last_context
        or now - last_touch >= TOUCH_INTERVAL_SECONDS
    )

    if not should_touch:
        return

    query = """
        INSERT INTO public.keeneland_app_sessions (
            session_id,
            browser_id,
            user_id,
            email,
            started_at,
            last_seen_at,
            last_page,
            last_hip
        )
        VALUES (
            %s::uuid,
            %s::uuid,
            %s::uuid,
            %s,
            NOW(),
            NOW(),
            %s,
            %s
        )
        ON CONFLICT (session_id)
        DO UPDATE SET
            last_seen_at = NOW(),
            last_page = EXCLUDED.last_page,
            last_hip = EXCLUDED.last_hip;
    """

    _execute(
        query,
        (
            session_id,
            browser_id,
            user_id,
            email,
            page,
            hip_number,
        ),
    )

    st.session_state["analytics_last_touch"] = now
    st.session_state["analytics_last_context"] = context


def log_event(
    event_type: str,
    page: str,
    hip_number: int | None = None,
    dedupe_key: str | None = None,
) -> None:
    """
    Store a usage event and touch the parent session.

    dedupe_key prevents Streamlit reruns from producing duplicate events.
    """
    if dedupe_key:
        seen = st.session_state.setdefault(
            "analytics_event_keys",
            set(),
        )

        if dedupe_key in seen:
            start_or_touch_session(
                page=page,
                hip_number=hip_number,
            )
            return

    session_id = ensure_session_id()
    user_id, email, browser_id = current_identity()

    if not user_id or not email or not browser_id:
        return

    start_or_touch_session(
        page=page,
        hip_number=hip_number,
        force=True,
    )

    query = """
        INSERT INTO public.keeneland_app_events (
            session_id,
            browser_id,
            user_id,
            email,
            event_type,
            page,
            hip_number,
            occurred_at
        )
        VALUES (
            %s::uuid,
            %s::uuid,
            %s::uuid,
            %s,
            %s,
            %s,
            %s,
            NOW()
        );
    """

    _execute(
        query,
        (
            session_id,
            browser_id,
            user_id,
            email,
            event_type,
            page,
            hip_number,
        ),
    )

    if dedupe_key:
        seen.add(dedupe_key)


def log_session_start() -> None:
    log_event(
        event_type="session_start",
        page=str(st.session_state.get("page", "catalog")),
        hip_number=None,
        dedupe_key="session_start",
    )


def log_catalog_view() -> None:
    log_event(
        event_type="catalog_view",
        page="catalog",
        hip_number=None,
        dedupe_key="catalog_view",
    )


def log_horse_view(hip_number: int) -> None:
    hip_number = int(hip_number)

    log_event(
        event_type="horse_view",
        page="profile",
        hip_number=hip_number,
        dedupe_key=f"horse_view:{hip_number}",
    )
