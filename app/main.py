"""Main Streamlit entrypoint for the PlasticFlow app."""

from __future__ import annotations

import os
import sys

import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app import styles

APP_TITLE = "PlasticFlow"

_NAV_PAGES = ["home", "observations", "currents", "drift", "stats"]
_NAV_LABELS = {
    "home": "🌊  PlasticFlow",
    "observations": "Observations",
    "currents": "Currents",
    "drift": "Drift",
    "stats": "Insights",
}


def _sync_page_from_query_params() -> None:
    """Read ?page= from the URL and update session state."""
    params = st.query_params
    if "page" in params:
        requested = params["page"]
        if requested in _NAV_PAGES and requested != st.session_state.get("page"):
            st.session_state.page = requested
        st.query_params.clear()


def render_top_nav() -> None:
    """Render a single cohesive HTML nav bar."""

    current = st.session_state.get("page", "home")

    links_html = ""
    for page in _NAV_PAGES:
        label = _NAV_LABELS[page]
        active_class = "pf-nav-active" if page == current else ""
        css_class = f"pf-nav-logo {active_class}" if page == "home" else f"pf-nav-link {active_class}"
        links_html += (
            f'<a class="{css_class.strip()}" href="?page={page}">{label}</a>'
        )

    st.markdown(
        f"""
<nav class="pf-navbar">
  {links_html}
</nav>
        """,
        unsafe_allow_html=True,
    )


def render_selected_page(page: str) -> None:
    """Render the currently active page."""

    if page == "observations":
        from app import page_observations
        page_observations.render()
    elif page == "currents":
        from app import page_currents
        page_currents.render()
    elif page == "drift":
        from app import page_drift
        page_drift.render()
    elif page == "stats":
        from app import page_statistics
        page_statistics.render()
    else:
        from app import page_landing
        page_landing.render()


def render_footer() -> None:
    """Render shared sidebar footer content."""

    st.sidebar.markdown(
        '<hr style="border:none;border-top:1px solid rgba(39,211,255,0.10);margin:0.5rem 0;">',
        unsafe_allow_html=True,
    )
    st.sidebar.caption("Data: NOAA NCEI Marine Microplastics & NASA OSCAR Surface Currents")


def main() -> None:
    """Render the PlasticFlow Streamlit app."""

    if "page" not in st.session_state:
        st.session_state.page = "home"

    try:
        st.set_page_config(
            page_title=APP_TITLE,
            page_icon="🌊",
            layout="wide",
        )
    except st.errors.StreamlitAPIException:
        pass

    _sync_page_from_query_params()
    styles.inject_global_styles()
    render_top_nav()
    render_selected_page(st.session_state.page)
    render_footer()


if __name__ == "__main__":
    main()
