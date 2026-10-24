"""Landing page for the PlasticFlow Streamlit app."""

from __future__ import annotations

import streamlit as st

from app import styles

_FEATURE_CARDS = [
    {
        "icon": "🗺️",
        "tag": "GLOBAL OBSERVATIONS",
        "title": "50 Years. Every Ocean.",
        "desc": "16,706 NOAA sampling events mapped worldwide. Filter by basin and year to see exactly where plastic concentrates.",
        "insight": "Pacific and Indian Ocean densities spike at the five major subtropical gyres — exactly where currents trap debris.",
        "page": "observations",
        "key": "cta-obs",
        "btn": "Open Observations Map →",
    },
    {
        "icon": "🌊",
        "tag": "OCEAN CURRENTS",
        "title": "The Ocean's Conveyor Belt",
        "desc": "NASA OSCAR streamlines at 1/3° resolution. Thicker, brighter lines = faster currents. The gyre highways are unmistakable.",
        "insight": "Gulf Stream and Kuroshio funnel surface debris into five rotating accumulation zones.",
        "page": "currents",
        "key": "cta-cur",
        "btn": "Explore Ocean Currents →",
    },
    {
        "icon": "🌀",
        "tag": "DRIFT SIMULATION",
        "title": "Watch Plastic Travel 5 Years",
        "desc": "Particles released from 18 coastal cities, carried by real OSCAR currents daily. Watch them converge — live.",
        "insight": "Within 2 years, particles from every continent arrive at the same gyres NOAA identifies as hotspots.",
        "page": "drift",
        "key": "cta-drift",
        "btn": "Run Drift Simulation →",
    },
    {
        "icon": "📊",
        "tag": "STATISTICAL INSIGHTS",
        "title": "The Numbers Don't Lie",
        "desc": "Basin comparisons, temporal trends, DBSCAN hotspot clustering, and Spearman correlation — all in one view.",
        "insight": "Latitude and longitude correlate with density at p < 0.05. Geography is destiny for microplastics.",
        "page": "stats",
        "key": "cta-stats",
        "btn": "View Statistical Insights →",
    },
]


def _hero_html() -> str:
    return """
<div style="
    background: linear-gradient(135deg, #071520 0%, #0d2840 50%, #071520 100%);
    border: 1px solid rgba(39, 211, 255, 0.14);
    border-radius: 20px;
    padding: 3.5rem 2.5rem 2.75rem;
    text-align: center;
    position: relative;
    overflow: hidden;
    margin-bottom: 2rem;
">
  <svg xmlns='http://www.w3.org/2000/svg' width='100%' height='100%'
       style='position:absolute;inset:0;pointer-events:none;opacity:0.045;'>
    <defs><pattern id='lp-dots' x='0' y='0' width='24' height='24' patternUnits='userSpaceOnUse'>
      <circle cx='1.2' cy='1.2' r='1.2' fill='#27d3ff'/></pattern></defs>
    <rect width='100%' height='100%' fill='url(#lp-dots)'/>
  </svg>

  <div style="position:relative;z-index:1;">
    <h1 style="font-size:5rem;margin:0 0 0.7rem;display:inline-block;
               color:#7dd8f8;font-weight:800;letter-spacing:-0.02em;line-height:1.1;">
      PlasticFlow
    </h1>
    <p style="color:#b8d8e8;font-size:1.35rem;max-width:640px;margin:0 auto;
              line-height:1.7;font-weight:300;">
      Tracing the invisible tide of microplastics across our oceans —
      from satellite observations to predictive drift simulation.
    </p>
  </div>
</div>
"""


def _feature_card_html(card: dict) -> str:
    return f"""
<div class="pf-card" style="min-height:270px;display:flex;flex-direction:column;cursor:default;">
  <div style="font-size:2.4rem;margin-bottom:0.65rem;">{card['icon']}</div>
  <div style="color:#27d3ff;font-size:0.8rem;font-weight:700;letter-spacing:0.1em;
              text-transform:uppercase;margin-bottom:0.35rem;">{card['tag']}</div>
  <div style="color:#e6eef8;font-size:1.15rem;font-weight:700;margin-bottom:0.6rem;
              line-height:1.3;">{card['title']}</div>
  <div style="color:#91a7c0;font-size:0.95rem;line-height:1.65;flex:1;">{card['desc']}</div>
  <div style="margin-top:0.9rem;padding-top:0.75rem;
              border-top:1px solid rgba(120,224,143,0.13);
              color:#78e08f;font-size:0.88rem;line-height:1.55;">
    💡 {card['insight']}
  </div>
</div>
"""


def _methodology_html() -> str:
    return """
<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:1rem;margin-top:0.5rem;">

  <div style="background:rgba(13,27,42,0.75);border:1px solid rgba(39,211,255,0.10);
              border-radius:14px;padding:1.3rem 1.4rem;">
    <div style="font-size:1.5rem;margin-bottom:0.55rem;">🛰️</div>
    <div style="color:#e6eef8;font-size:1.05rem;font-weight:600;margin-bottom:0.45rem;">
      Data Sources
    </div>
    <div style="color:#91a7c0;font-size:0.95rem;line-height:1.65;">
      <strong style="color:#b8d8e8;">NOAA NCEI</strong> — 50+ years of ocean sampling:
      surface trawls, manta nets, water column grabs.<br><br>
      <strong style="color:#b8d8e8;">NASA OSCAR</strong> — 1/3° surface velocity
      composites across 315 time steps.
    </div>
  </div>

  <div style="background:rgba(13,27,42,0.75);border:1px solid rgba(39,211,255,0.10);
              border-radius:14px;padding:1.3rem 1.4rem;">
    <div style="font-size:1.5rem;margin-bottom:0.55rem;">🔬</div>
    <div style="color:#e6eef8;font-size:1.05rem;font-weight:600;margin-bottom:0.45rem;">
      Analysis Methods
    </div>
    <div style="color:#91a7c0;font-size:0.95rem;line-height:1.65;">
      <strong style="color:#b8d8e8;">DBSCAN</strong> spatial clustering with haversine
      distance (ε = 250 km) — no assumed cluster count.<br><br>
      <strong style="color:#b8d8e8;">Spearman correlation</strong> between density and
      geographic features, with p-value significance testing.
    </div>
  </div>

  <div style="background:rgba(13,27,42,0.75);border:1px solid rgba(39,211,255,0.10);
              border-radius:14px;padding:1.3rem 1.4rem;">
    <div style="font-size:1.5rem;margin-bottom:0.55rem;">🌊</div>
    <div style="color:#e6eef8;font-size:1.05rem;font-weight:600;margin-bottom:0.45rem;">
      Drift Simulation
    </div>
    <div style="color:#91a7c0;font-size:0.95rem;line-height:1.65;">
      <strong style="color:#b8d8e8;">Lagrangian particle tracking</strong> — particles
      advected by OSCAR velocity fields at daily timesteps over 5 years.<br><br>
      Released from <strong style="color:#b8d8e8;">18 coastal cities</strong>. Frozen
      particles (displacement &lt; 0.5°) filtered out.
    </div>
  </div>

</div>
"""


def render() -> None:
    """Render the PlasticFlow landing page."""

    # Sidebar: project info
    st.sidebar.markdown(
        """
        <div style="padding:0.25rem 0;color:#91a7c0;font-size:0.84rem;line-height:1.7;">
          <strong style="color:#e6eef8;font-size:0.95rem;">About PlasticFlow</strong>
          <br><br>
          A data science hackathon project exploring global microplastics distribution,
          ocean current dynamics, and long-range plastic drift using open satellite datasets.
          <br><br>
          <strong style="color:#b8d8e8;">Built for</strong><br>
          NC SMathHacks 2026 · 36-hour hackathon<br>Theme: Under the Sea
          <br><br>
          <strong style="color:#b8d8e8;">Stack</strong><br>
          Python · Streamlit · Plotly<br>
          pandas · NumPy · scikit-learn<br>
          xarray · OSCAR NetCDF
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Hero
    st.markdown(_hero_html(), unsafe_allow_html=True)

    # Feature cards
    st.markdown(styles.section_divider("Explore the Dashboard"), unsafe_allow_html=True)
    cols = st.columns(4)
    for col, card in zip(cols, _FEATURE_CARDS):
        col.markdown(_feature_card_html(card), unsafe_allow_html=True)
        if col.button(card["btn"], key=card["key"], use_container_width=True):
            st.session_state.page = card["page"]
            st.rerun()

    # Methodology
    st.markdown(styles.section_divider("How We Built It"), unsafe_allow_html=True)
    st.markdown(_methodology_html(), unsafe_allow_html=True)
