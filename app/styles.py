"""Shared visual design system for the PlasticFlow Streamlit app.

Provides CSS/HTML/JS building blocks that adapt Magic UI patterns
(AnimatedGradientText, MagicCard, BorderBeam, NumberTicker, etc.)
to a pure Python/Streamlit context via st.markdown(unsafe_allow_html=True).

Tested with Streamlit ≥ 1.30.
"""

from __future__ import annotations

__all__ = [
    "inject_global_styles",
    "page_header",
    "metric_card",
    "callout",
    "section_divider",
    "dot_pattern_svg",
    "number_ticker_js",
    "PAGE_ICONS",
]

import streamlit as st

# ---------------------------------------------------------------------------
# Design tokens
# ---------------------------------------------------------------------------

PAGE_ICONS: dict[str, str] = {
    "Global Observations Map": "🗺️",
    "Ocean Currents": "🌊",
    "Particle Drift": "🌀",
    "Statistical Insights": "📊",
}

_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

/* ── Base ─────────────────────────────────────────────────────────────── */
html, body, [class*="css"], .stApp {
    font-family: 'Inter', 'IBM Plex Sans', 'Segoe UI', sans-serif !important;
    background-color: #07131f;
}
#MainMenu { display: none; }
footer    { display: none; }
header    { display: none; }
[data-testid="stToolbar"]          { display: none !important; }
[data-testid="stDecoration"]       { display: none !important; }
[data-testid="stStatusWidget"]     { display: none !important; }
div[class*="StatusWidget"]         { display: none !important; }
div[class*="deployButton"]         { display: none !important; }

div.block-container {
    padding-top: 3.5rem;
    padding-bottom: 2rem;
}
div[data-testid="stTabContent"] { padding-bottom: 2rem; }

/* ── Sidebar ──────────────────────────────────────────────────────────── */
section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #08121d 0%, #0a1525 60%, #07131f 100%);
    border-right: 1px solid rgba(39, 211, 255, 0.08);
}
div[data-testid="stSidebarUserContent"] h1,
div[data-testid="stSidebarUserContent"] h2,
div[data-testid="stSidebarUserContent"] h3,
div[data-testid="stSidebarUserContent"] label,
div[data-testid="stSidebarUserContent"] p,
div[data-testid="stSidebarUserContent"] span {
    color: #e6eef8;
}

/* ── Unified HTML nav bar ────────────────────────────────────────────── */
nav.pf-navbar {
    display: flex;
    align-items: center;
    gap: 0;
    background: rgba(5, 14, 28, 0.98);
    border-bottom: 1px solid rgba(39, 211, 255, 0.12);
    padding: 0 1.5rem;
    margin-bottom: 1.5rem;
    position: sticky;
    top: 0;
    z-index: 999;
    height: 52px;
}
.pf-nav-logo {
    color: #7dd8f8;
    font-size: 1.1rem;
    font-weight: 800;
    letter-spacing: -0.01em;
    padding: 0 1.6rem 0 0;
    margin-right: 1rem;
    border-right: 1px solid rgba(39, 211, 255, 0.18);
    cursor: pointer;
    white-space: nowrap;
    user-select: none;
    line-height: 52px;
}
.pf-nav-link {
    color: #8ab4cc;
    font-size: 0.88rem;
    font-weight: 500;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    padding: 0 1.1rem;
    cursor: pointer;
    white-space: nowrap;
    user-select: none;
    line-height: 52px;
    border-bottom: 2px solid transparent;
    transition: color 0.15s, border-color 0.15s;
}
.pf-nav-link:hover, .pf-nav-logo:hover {
    color: #e6eef8;
}
.pf-nav-link.pf-nav-active {
    color: #7dd8f8;
    border-bottom: 2px solid #7dd8f8;
    font-weight: 600;
}

/* ── Global button style (CTA look everywhere except nav) ─────────────── */
div[data-testid="stButton"] > button {
    background: rgba(39, 211, 255, 0.07) !important;
    border: 1px solid rgba(39, 211, 255, 0.22) !important;
    color: #27d3ff !important;
    border-radius: 8px !important;
    font-family: 'Inter', sans-serif !important;
    font-weight: 500 !important;
    font-size: 0.9rem !important;
    transition: background 0.2s, border-color 0.2s !important;
}
div[data-testid="stButton"] > button:hover {
    background: rgba(39, 211, 255, 0.14) !important;
    border-color: rgba(39, 211, 255, 0.45) !important;
    color: #e6eef8 !important;
}

/* ── Animated gradient title ─────────────────────────────────────────── */
@keyframes pf-gradient-shift {
    0%, 100% { background-position: 0% 50%; }
    50%       { background-position: 100% 50%; }
}
.pf-gradient-title {
    background: linear-gradient(270deg, #27d3ff, #78e08f, #3ba4ff, #27d3ff);
    background-size: 300% 300%;
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    animation: pf-gradient-shift 6s ease infinite;
    font-weight: 700;
    letter-spacing: -0.02em;
    line-height: 1.1;
}

/* ── Metric cards (MagicCard + NeonGradientCard pattern) ─────────────── */
.pf-card {
    position: relative;
    background: linear-gradient(160deg, rgba(13,27,42,0.95), rgba(7,19,31,0.98));
    border: 1px solid rgba(120, 224, 143, 0.15);
    border-radius: 16px;
    padding: 1.2rem 1.4rem;
    min-height: 120px;
    box-shadow: 0 8px 24px rgba(0,0,0,0.25);
    transition: border-color 0.3s ease, box-shadow 0.3s ease, transform 0.2s ease;
    overflow: hidden;
}
.pf-card:hover {
    border-color: rgba(39, 211, 255, 0.45);
    box-shadow:
        0 0 18px rgba(39, 211, 255, 0.15),
        0 0 40px rgba(39, 211, 255, 0.07),
        inset 0 1px 0 rgba(39, 211, 255, 0.08);
    transform: translateY(-2px);
}
/* MagicCard spotlight — driven by JS mousemove listener */
.pf-card::before {
    content: '';
    position: absolute;
    inset: 0;
    border-radius: inherit;
    background: radial-gradient(
        200px circle at var(--mouse-x, -400px) var(--mouse-y, -400px),
        rgba(39, 211, 255, 0.09),
        transparent 70%
    );
    pointer-events: none;
    z-index: 0;
}
.pf-card > * { position: relative; z-index: 1; }

/* Number ticker entrance */
@keyframes pf-count-up {
    from { opacity: 0; transform: translateY(5px); }
    to   { opacity: 1; transform: translateY(0); }
}
.pf-ticker { display: inline-block; animation: pf-count-up 0.5s ease forwards; }

/* ── Landing page stat chips ─────────────────────────────────────────── */
.pf-stat-chip {
    display: inline-block;
    background: rgba(39, 211, 255, 0.08);
    border: 1px solid rgba(39, 211, 255, 0.20);
    border-radius: 100px;
    padding: 0.35rem 1rem;
    color: #b0cfe0;
    font-size: 0.87rem;
    font-weight: 500;
}

/* ── Callout boxes ────────────────────────────────────────────────────── */
.pf-callout {
    position: relative;
    padding: 0.8rem 1.1rem 0.8rem 1.2rem;
    border-radius: 10px;
    border: 1px solid;
    font-size: 0.92rem;
    line-height: 1.6;
    margin-bottom: 1rem;
}
.pf-callout-info {
    background: rgba(39, 211, 255, 0.06);
    border-color: rgba(39, 211, 255, 0.22);
    color: #b8d8e8;
    border-left: 3px solid #27d3ff;
}
.pf-callout-warn {
    background: rgba(255, 209, 102, 0.07);
    border-color: rgba(255, 209, 102, 0.25);
    color: #d4c08a;
    border-left: 3px solid #ffd166;
}

/* ── Bento grid ───────────────────────────────────────────────────────── */
.pf-bento { display: grid; gap: 1rem; width: 100%; }
.pf-bento-3col { grid-template-columns: repeat(3, 1fr); }
.pf-bento-4col { grid-template-columns: repeat(4, 1fr); }
@media (max-width: 768px) {
    .pf-bento-3col, .pf-bento-4col { grid-template-columns: 1fr; }
}
"""

# ---------------------------------------------------------------------------
# Combined JS: spotlight + nav row tagging
# ---------------------------------------------------------------------------
_JS = """
<script>
(function() {
  // ── MagicCard spotlight ───────────────────────────────────────────────
  if (!document.querySelector('#pf-spotlight-guard')) {
    var g = document.createElement('span');
    g.id = 'pf-spotlight-guard';
    g.style.display = 'none';
    document.body.appendChild(g);
    document.addEventListener('mousemove', function(e) {
      document.querySelectorAll('.pf-card').forEach(function(card) {
        var r = card.getBoundingClientRect();
        card.style.setProperty('--mouse-x', (e.clientX - r.left) + 'px');
        card.style.setProperty('--mouse-y', (e.clientY - r.top) + 'px');
      });
    });
  }

  // ── Tag nav row with .pf-nav-row ──────────────────────────────────────
  function tagNavRow() {
    var sentinel = document.querySelector('.pf-nav-sentinel');
    if (!sentinel) { setTimeout(tagNavRow, 150); return; }
    var blocks = document.querySelectorAll('[data-testid="stHorizontalBlock"]');
    for (var i = 0; i < blocks.length; i++) {
      if (sentinel.compareDocumentPosition(blocks[i]) & Node.DOCUMENT_POSITION_FOLLOWING) {
        blocks[i].classList.add('pf-nav-row');
        return;
      }
    }
    setTimeout(tagNavRow, 150);
  }
  tagNavRow();
})();
</script>
"""


def inject_global_styles() -> None:
    """Inject global PlasticFlow CSS + JS. Call once from main.py."""
    st.markdown(f"<style>{_CSS}</style>{_JS}", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# HTML component builders
# ---------------------------------------------------------------------------


def page_header(title: str, subtitle: str = "") -> str:
    """Return an animated gradient page header HTML string."""
    sub_html = (
        f'<p style="color:#91a7c0;font-size:0.97rem;margin:0.4rem 0 0;font-weight:400;">'
        f"{subtitle}</p>"
    ) if subtitle else ""
    return f"""
<div style="margin-bottom:1.5rem;">
  <h1 class="pf-gradient-title" style="font-size:2rem;margin:0;display:inline-block;">
    {title}
  </h1>
  {sub_html}
  <div style="height:2px;
              background:linear-gradient(90deg,#27d3ff,#78e08f,transparent);
              margin-top:0.7rem;border-radius:2px;"></div>
</div>
"""


def metric_card(
    title: str,
    value: str,
    subtitle: str = "",
    icon: str = "",
    *,
    ticker_id: str | None = None,
    ticker_value: int | float | None = None,
    ticker_decimals: int = 0,
) -> str:
    """Return an HTML metric card (NeonGradientCard + NumberTicker pattern)."""
    icon_html = (
        f'<div style="font-size:1.25rem;margin-bottom:0.35rem;">{icon}</div>'
    ) if icon else ""
    value_attrs = f' id="{ticker_id}"' if ticker_id else ""
    sub_html = (
        f'<div style="color:#91a7c0;font-size:0.82rem;margin-top:0.45rem;">{subtitle}</div>'
    ) if subtitle else ""
    ticker_script = (
        number_ticker_js(ticker_value, ticker_id, ticker_decimals)
        if ticker_id and ticker_value is not None
        else ""
    )
    return f"""
<div class="pf-card">
  {icon_html}
  <div style="color:#91a7c0;font-size:0.8rem;margin-bottom:0.2rem;font-weight:600;
              letter-spacing:0.05em;text-transform:uppercase;">{title}</div>
  <div{value_attrs} class="pf-ticker"
      style="color:#e6eef8;font-size:1.85rem;font-weight:700;line-height:1.1;">{value}</div>
  {sub_html}
</div>
{ticker_script}
"""


def number_ticker_js(
    value: int | float,
    element_id: str,
    decimals: int = 0,
) -> str:
    """Return an inline <script> that animates a count-up on the target element."""
    return f"""
<script>
(function() {{
  var el = document.getElementById('{element_id}');
  if (!el) return;
  var end = {float(value)};
  var dur = 1400;
  var startTime = null;
  function easeOut(t) {{ return 1 - Math.pow(1 - t, 3); }}
  function step(ts) {{
    if (!startTime) startTime = ts;
    var pct = Math.min((ts - startTime) / dur, 1);
    el.textContent = new Intl.NumberFormat('en-US', {{
      minimumFractionDigits: {decimals},
      maximumFractionDigits: {decimals}
    }}).format(end * easeOut(pct));
    if (pct < 1) requestAnimationFrame(step);
  }}
  requestAnimationFrame(step);
}})();
</script>
"""


def callout(text: str, kind: str = "info", icon: str = "") -> str:
    """Return a styled callout box replacing st.info / st.warning."""
    icon_html = (
        f'<span style="margin-right:0.5rem;font-size:1.05em;">{icon}</span>'
    ) if icon else ""
    return f'<div class="pf-callout pf-callout-{kind}">{icon_html}{text}</div>'


def section_divider(label: str = "") -> str:
    """Return a gradient divider line with an optional centered label."""
    label_html = (
        f'<h2 style="margin:0;padding:0 1rem;color:#e6eef8;font-size:2rem;'
        f'font-weight:700;letter-spacing:-0.01em;white-space:nowrap;">{label}</h2>'
    ) if label else ""
    return f"""
<div style="display:flex;align-items:center;margin:2.5rem 0 1.5rem;gap:0.75rem;">
  <div style="flex:1;height:1px;
              background:linear-gradient(90deg,rgba(39,211,255,0.25),transparent);"></div>
  {label_html}
  <div style="flex:1;height:1px;
              background:linear-gradient(270deg,rgba(120,224,143,0.25),transparent);"></div>
</div>
"""


def dot_pattern_svg(opacity: float = 0.035) -> str:
    """Return an SVG dot-pattern background overlay (DotPattern adaptation)."""
    return f"""
<svg xmlns='http://www.w3.org/2000/svg' width='100%' height='100%'
     style='position:absolute;inset:0;pointer-events:none;z-index:0;opacity:{opacity}'>
  <defs>
    <pattern id='pf-dots' x='0' y='0' width='20' height='20'
             patternUnits='userSpaceOnUse'>
      <circle cx='1' cy='1' r='1' fill='#27d3ff'/>
    </pattern>
  </defs>
  <rect width='100%' height='100%' fill='url(#pf-dots)'/>
</svg>
"""


def sidebar_app_title(title: str) -> str:
    """Return HTML for the animated gradient app title (kept for compatibility)."""
    return f"""
<div style="padding:1rem 0.25rem 1.25rem;">
  <div class="pf-gradient-title" style="font-size:1.45rem;">
    🌊 {title}
  </div>
</div>
<hr style="border:none;border-top:1px solid rgba(39,211,255,0.12);margin:0 0 0.25rem;">
"""
