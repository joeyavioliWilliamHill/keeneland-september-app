import base64
import hashlib
import hmac
import json
import os
import re
import time
import uuid
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv


COOKIE_NAME = "wpt_keeneland_session"
COOKIE_MAX_AGE_SECONDS = 30 * 24 * 60 * 60


def get_project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def load_local_environment() -> None:
    load_dotenv(
        get_project_root() / ".env",
        override=False,
    )


def get_secret(name: str) -> str | None:
    try:
        value = st.secrets.get(name)
    except Exception:
        value = None

    if value:
        return str(value)

    load_local_environment()

    value = os.getenv(name)
    return str(value) if value else None


def normalize_email(email: str) -> str:
    return str(email or "").strip().lower()


def is_valid_email(email: str) -> bool:
    email = normalize_email(email)

    if not email or len(email) > 254:
        return False

    pattern = (
        r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+"
        r"@[A-Za-z0-9-]+"
        r"(?:\.[A-Za-z0-9-]+)+$"
    )

    return bool(re.fullmatch(pattern, email))


def build_user_id(email: str) -> str:
    return str(
        uuid.uuid5(
            uuid.NAMESPACE_URL,
            f"wpt-keeneland:{normalize_email(email)}",
        )
    )


def _b64_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("utf-8").rstrip("=")


def _b64_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def get_auth_cookie_secret() -> str:
    secret = get_secret("AUTH_COOKIE_SECRET")

    if not secret:
        raise ValueError(
            "AUTH_COOKIE_SECRET is missing. Add it to Streamlit secrets "
            "and your local .env file."
        )

    return secret


def build_auth_cookie(
    email: str,
    user_id: str,
    browser_id: str,
) -> str:
    payload = {
        "email": normalize_email(email),
        "user_id": str(user_id),
        "browser_id": str(browser_id),
        "exp": int(time.time()) + COOKIE_MAX_AGE_SECONDS,
    }

    payload_bytes = json.dumps(
        payload,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")

    payload_b64 = _b64_encode(payload_bytes)

    signature = hmac.new(
        get_auth_cookie_secret().encode("utf-8"),
        payload_b64.encode("utf-8"),
        hashlib.sha256,
    ).digest()

    return f"{payload_b64}.{_b64_encode(signature)}"


def decode_auth_cookie(cookie_value: str) -> dict | None:
    try:
        payload_b64, signature_b64 = cookie_value.split(".", 1)

        expected = hmac.new(
            get_auth_cookie_secret().encode("utf-8"),
            payload_b64.encode("utf-8"),
            hashlib.sha256,
        ).digest()

        supplied = _b64_decode(signature_b64)

        if not hmac.compare_digest(expected, supplied):
            return None

        payload = json.loads(
            _b64_decode(payload_b64).decode("utf-8")
        )

        if int(payload.get("exp", 0)) <= int(time.time()):
            return None

        email = normalize_email(payload.get("email", ""))
        user_id = str(payload.get("user_id", "")).strip()
        browser_id = str(payload.get("browser_id", "")).strip()

        if not is_valid_email(email) or not user_id or not browser_id:
            return None

        return {
            "email": email,
            "user_id": user_id,
            "browser_id": browser_id,
        }

    except Exception:
        return None


def remember_user(
    cookie_controller,
    email: str,
    user_id: str,
    browser_id: str,
) -> None:
    cookie_controller.set(
        COOKIE_NAME,
        build_auth_cookie(
            email=email,
            user_id=user_id,
            browser_id=browser_id,
        ),
        max_age=COOKIE_MAX_AGE_SECONDS,
        same_site="lax",
    )


def restore_remembered_user(cookie_controller) -> bool:
    cookie_value = None

    try:
        cookie_value = st.context.cookies.get(COOKIE_NAME)
    except Exception:
        cookie_value = None

    if not cookie_value:
        try:
            cookie_value = cookie_controller.get(COOKIE_NAME)
        except Exception:
            cookie_value = None

    if not cookie_value:
        return False

    payload = decode_auth_cookie(str(cookie_value))

    if not payload:
        try:
            cookie_controller.remove(COOKIE_NAME)
        except Exception:
            pass
        return False

    st.session_state["authenticated"] = True
    st.session_state["user_email"] = payload["email"]
    st.session_state["user_id"] = payload["user_id"]
    st.session_state["browser_id"] = payload["browser_id"]

    return True


def is_authenticated() -> bool:
    return bool(
        st.session_state.get("authenticated", False)
        and st.session_state.get("user_email")
        and st.session_state.get("user_id")
        and st.session_state.get("browser_id")
    )


def login_user(
    cookie_controller,
    email: str,
) -> bool:
    email = normalize_email(email)

    if not is_valid_email(email):
        return False

    user_id = build_user_id(email)

    # Preserve the same browser identity during this browser's remembered period.
    browser_id = (
        st.session_state.get("browser_id")
        or str(uuid.uuid4())
    )

    st.session_state["authenticated"] = True
    st.session_state["user_email"] = email
    st.session_state["user_id"] = user_id
    st.session_state["browser_id"] = browser_id

    remember_user(
        cookie_controller=cookie_controller,
        email=email,
        user_id=user_id,
        browser_id=browser_id,
    )

    return True


def render_login_brand() -> None:
    st.markdown(
        """
        <div style="
            text-align:center;
            padding:0.5rem 0 1.2rem 0;
        ">
            <div style="
                color:#15392F;
                font-size:2.35rem;
                font-weight:900;
                letter-spacing:0.06em;
            ">
                ★ WEST POINT
            </div>
            <div style="
                color:#A18348;
                font-size:0.82rem;
                font-weight:800;
                letter-spacing:0.22em;
                margin-top:0.2rem;
            ">
                THOROUGHBREDS
            </div>
            <div style="
                color:#475569;
                font-size:1rem;
                margin-top:0.8rem;
            ">
                Keeneland September Yearlings · 2026
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_email_login(cookie_controller) -> None:
    with st.container(border=True):
        st.markdown("## Enter Catalog")

        st.caption(
            "Enter your email once. This browser will be remembered for 30 days."
        )

        with st.form(
            "email_login_form",
            clear_on_submit=False,
        ):
            email = st.text_input(
                "Email",
                placeholder="name@email.com",
            )

            submitted = st.form_submit_button(
                "Enter Catalog",
                use_container_width=True,
                type="primary",
            )

        if submitted:
            if not login_user(
                cookie_controller=cookie_controller,
                email=email,
            ):
                st.error("Please enter a valid email address.")
                return

            st.success(
                "You're all set. This browser will remember you for 30 days."
            )

            if st.button(
                "Open Catalog",
                key="complete_login",
                use_container_width=True,
                type="primary",
            ):
                st.rerun()

            st.stop()


def require_login(cookie_controller) -> None:
    if is_authenticated():
        return

    if restore_remembered_user(cookie_controller):
        return

    left, center, right = st.columns([1, 1.3, 1])

    with center:
        render_login_brand()
        render_email_login(cookie_controller)

    st.stop()


def render_user_menu(cookie_controller) -> None:
    if not is_authenticated():
        return

    user_email = st.session_state.get("user_email", "")

    st.sidebar.markdown(
        """
        <div style="
            margin-top:1rem;
            border-top:1px solid #E5E7EB;
            padding-top:0.8rem;
        ">
            <div style="
                color:#6B7280;
                font-size:0.7rem;
                font-weight:800;
                letter-spacing:0.08em;
                text-transform:uppercase;
            ">
                Partner Session
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.sidebar.caption(f"Viewing as {user_email}")
