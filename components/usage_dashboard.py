from __future__ import annotations

from datetime import datetime
from typing import Any

import pandas as pd
import psycopg2
import streamlit as st

from components.auth import get_secret


def _database_url() -> str:
    database_url = get_secret("DATABASE_URL")
    if not database_url:
        raise ValueError("DATABASE_URL is missing.")
    return database_url


def _admin_emails() -> set[str]:
    raw = get_secret("USAGE_ADMIN_EMAILS") or ""
    return {
        email.strip().lower()
        for email in raw.split(",")
        if email.strip()
    }


def is_usage_admin() -> bool:
    email = str(
        st.session_state.get("user_email", "")
    ).strip().lower()

    return bool(
        email
        and email in _admin_emails()
    )


@st.cache_data(ttl=30, show_spinner=False)
def _read_sql(
    query: str,
    params: tuple[Any, ...] = (),
) -> pd.DataFrame:
    with psycopg2.connect(
        _database_url()
    ) as connection:
        return pd.read_sql_query(
            query,
            connection,
            params=params,
        )


def _period_clause(days: int | None, column: str) -> tuple[str, tuple]:
    if days is None:
        return "", ()

    return (
        f" WHERE {column} >= NOW() - (%s * INTERVAL '1 day') ",
        (days,),
    )


def _format_timestamp(value: Any) -> str:
    if value is None or pd.isna(value):
        return "—"

    try:
        timestamp = pd.Timestamp(value)

        if timestamp.tzinfo is not None:
            timestamp = timestamp.tz_convert(
                "America/Denver"
            )

        return timestamp.strftime(
            "%b %-d, %-I:%M %p"
        )
    except Exception:
        return str(value)


def _metric_data(days: int | None) -> dict[str, int]:
    event_where, event_params = _period_clause(
        days,
        "occurred_at",
    )
    session_where, session_params = _period_clause(
        days,
        "started_at",
    )

    users = _read_sql(
        f"""
        SELECT COUNT(DISTINCT lower(email)) AS value
        FROM public.keeneland_app_events
        {event_where};
        """,
        event_params,
    )

    sessions = _read_sql(
        f"""
        SELECT COUNT(*) AS value
        FROM public.keeneland_app_sessions
        {session_where};
        """,
        session_params,
    )

    views = _read_sql(
        f"""
        SELECT COUNT(*) AS value
        FROM public.keeneland_app_events
        {event_where}
        {"AND" if event_where else "WHERE"} event_type = 'horse_view';
        """,
        event_params,
    )

    active = _read_sql(
        """
        SELECT COUNT(DISTINCT lower(email)) AS value
        FROM public.keeneland_app_sessions
        WHERE last_seen_at >= NOW() - INTERVAL '10 minutes';
        """
    )

    return {
        "users": int(users.iloc[0]["value"] or 0),
        "sessions": int(sessions.iloc[0]["value"] or 0),
        "horse_views": int(views.iloc[0]["value"] or 0),
        "active_now": int(active.iloc[0]["value"] or 0),
    }


def _user_summary(days: int | None) -> pd.DataFrame:
    where, params = _period_clause(
        days,
        "e.occurred_at",
    )

    return _read_sql(
        f"""
        SELECT
            lower(e.email) AS email,
            COUNT(DISTINCT e.session_id) AS sessions,
            COUNT(*) FILTER (
                WHERE e.event_type = 'horse_view'
            ) AS horse_views,
            COUNT(DISTINCT e.hip_number) FILTER (
                WHERE e.event_type = 'horse_view'
            ) AS unique_horses,
            MIN(e.occurred_at) AS first_activity,
            MAX(e.occurred_at) AS last_activity
        FROM public.keeneland_app_events e
        {where}
        GROUP BY lower(e.email)
        ORDER BY last_activity DESC;
        """,
        params,
    )


def _recent_sessions(days: int | None) -> pd.DataFrame:
    where, params = _period_clause(
        days,
        "started_at",
    )

    return _read_sql(
        f"""
        SELECT
            email,
            started_at,
            last_seen_at,
            ROUND(
                EXTRACT(
                    EPOCH FROM (
                        last_seen_at - started_at
                    )
                ) / 60.0,
                1
            ) AS minutes,
            last_page,
            last_hip
        FROM public.keeneland_app_sessions
        {where}
        ORDER BY last_seen_at DESC
        LIMIT 100;
        """,
        params,
    )


def _popular_horses(days: int | None) -> pd.DataFrame:
    where, params = _period_clause(
        days,
        "e.occurred_at",
    )

    extra = (
        "AND"
        if where
        else "WHERE"
    )

    return _read_sql(
        f"""
        SELECT
            e.hip_number,
            COALESCE(h.sire, '—') AS sire,
            COALESCE(h.dam, '—') AS dam,
            COUNT(*) AS views,
            COUNT(DISTINCT lower(e.email)) AS unique_users
        FROM public.keeneland_app_events e
        LEFT JOIN public.keeneland_september_2026 h
            ON h.hip_number = e.hip_number
        {where}
        {extra} e.event_type = 'horse_view'
          AND e.hip_number IS NOT NULL
        GROUP BY
            e.hip_number,
            h.sire,
            h.dam
        ORDER BY
            views DESC,
            unique_users DESC,
            e.hip_number
        LIMIT 25;
        """,
        params,
    )


def _daily_usage(days: int | None) -> pd.DataFrame:
    effective_days = days or 30

    return _read_sql(
        """
        SELECT
            DATE(occurred_at AT TIME ZONE 'America/Denver') AS day,
            COUNT(DISTINCT lower(email)) AS users,
            COUNT(DISTINCT session_id) AS sessions,
            COUNT(*) FILTER (
                WHERE event_type = 'horse_view'
            ) AS horse_views
        FROM public.keeneland_app_events
        WHERE occurred_at >= NOW() - (%s * INTERVAL '1 day')
        GROUP BY DATE(
            occurred_at AT TIME ZONE 'America/Denver'
        )
        ORDER BY day;
        """,
        (effective_days,),
    )


def render_usage_dashboard() -> None:
    if not is_usage_admin():
        st.error(
            "You do not have access to usage analytics."
        )
        return

    st.title("App Usage")
    st.caption(
        "Keeneland September catalog activity · "
        "sessions, users, horse views, and recent usage."
    )

    top_left, top_right = st.columns(
        [3, 1],
        vertical_alignment="bottom",
    )

    with top_left:
        period_label = st.segmented_control(
            "Time period",
            options=[
                "Today",
                "7 days",
                "30 days",
                "All time",
            ],
            default="7 days",
            key="usage_period",
        )

    with top_right:
        if st.button(
            "↻ Refresh",
            use_container_width=True,
            key="usage_refresh",
        ):
            _read_sql.clear()
            st.rerun()

    period_days = {
        "Today": 1,
        "7 days": 7,
        "30 days": 30,
        "All time": None,
    }.get(
        period_label,
        7,
    )

    metrics = _metric_data(
        period_days
    )

    metric_columns = st.columns(4)

    metric_columns[0].metric(
        "Unique Users",
        f"{metrics['users']:,}",
    )
    metric_columns[1].metric(
        "Sessions",
        f"{metrics['sessions']:,}",
    )
    metric_columns[2].metric(
        "Horse Views",
        f"{metrics['horse_views']:,}",
    )
    metric_columns[3].metric(
        "Active · 10 min",
        f"{metrics['active_now']:,}",
        help=(
            "Users whose session has touched the app "
            "within the last 10 minutes."
        ),
    )

    st.divider()

    daily = _daily_usage(
        period_days
    )

    if not daily.empty:
        st.markdown("### Usage Trend")

        chart_data = (
            daily
            .set_index("day")[
                [
                    "users",
                    "sessions",
                    "horse_views",
                ]
            ]
        )

        st.line_chart(
            chart_data,
            height=300,
        )

    user_summary = _user_summary(
        period_days
    )

    st.markdown("### Who Is Using the App")

    if user_summary.empty:
        st.info(
            "No usage has been recorded for this period."
        )
    else:
        users_display = user_summary.copy()

        users_display[
            "first_activity"
        ] = users_display[
            "first_activity"
        ].map(_format_timestamp)

        users_display[
            "last_activity"
        ] = users_display[
            "last_activity"
        ].map(_format_timestamp)

        users_display = users_display.rename(
            columns={
                "email": "Email",
                "sessions": "Sessions",
                "horse_views": "Horse Views",
                "unique_horses": "Unique Horses",
                "first_activity": "First Activity",
                "last_activity": "Last Activity",
            }
        )

        st.dataframe(
            users_display,
            use_container_width=True,
            hide_index=True,
        )

    left_column, right_column = st.columns(
        [1.1, 1],
        gap="large",
    )

    with left_column:
        st.markdown("### Recent Sessions")

        recent = _recent_sessions(
            period_days
        )

        if recent.empty:
            st.caption(
                "No sessions in this period."
            )
        else:
            recent_display = recent.copy()

            recent_display[
                "started_at"
            ] = recent_display[
                "started_at"
            ].map(_format_timestamp)

            recent_display[
                "last_seen_at"
            ] = recent_display[
                "last_seen_at"
            ].map(_format_timestamp)

            recent_display = recent_display.rename(
                columns={
                    "email": "Email",
                    "started_at": "Started",
                    "last_seen_at": "Last Seen",
                    "minutes": "Minutes",
                    "last_page": "Last Page",
                    "last_hip": "Last Hip",
                }
            )

            st.dataframe(
                recent_display,
                use_container_width=True,
                hide_index=True,
                height=430,
            )

    with right_column:
        st.markdown("### Most Viewed Horses")

        popular = _popular_horses(
            period_days
        )

        if popular.empty:
            st.caption(
                "No horse-profile views in this period."
            )
        else:
            popular_display = popular.rename(
                columns={
                    "hip_number": "Hip",
                    "sire": "Sire",
                    "dam": "Dam",
                    "views": "Views",
                    "unique_users": "Users",
                }
            )

            st.dataframe(
                popular_display,
                use_container_width=True,
                hide_index=True,
                height=430,
            )
