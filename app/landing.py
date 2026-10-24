"""Landing page for PlasticFlow — editorial scroll experience."""

from __future__ import annotations

import streamlit as st

_HTML = """\
<style>
@import url('https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,400;0,700;0,900;1,400&family=Source+Sans+3:wght@300;400;600&display=swap');

.pf-landing *,
.pf-landing *::before,
.pf-landing *::after { box-sizing: border-box; margin: 0; padding: 0; }

.pf-landing {
  position: relative;
  background: #0a0e1a;
  color: #e8e0d0;
  font-family: 'Source Sans 3', sans-serif;
  font-weight: 300;
  line-height: 1.7;
  overflow-x: hidden;
}

/* ── grain overlay ── */
.pf-landing::before {
  content: '';
  position: fixed;
  inset: 0;
  pointer-events: none;
  z-index: 9999;
  opacity: 0.025;
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='200' height='200'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4'/%3E%3CfeColorMatrix type='saturate' values='0'/%3E%3C/filter%3E%3Crect width='200' height='200' filter='url(%23n)' opacity='0.4'/%3E%3C/svg%3E");
  background-repeat: repeat;
}

/* ── section entrance animation ── */
.pf-reveal {
  opacity: 1;
  transform: translateY(0);
  transition: opacity 0.7s ease, transform 0.7s ease;
}
.pf-js-ready .pf-reveal {
  opacity: 0;
  transform: translateY(30px);
}
.pf-reveal.pf-visible {
  opacity: 1 !important;
  transform: translateY(0) !important;
}

/* ── hero ── */
.pf-hero {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  padding: 2rem;
  position: relative;
}
.pf-hero-title {
  font-family: 'Playfair Display', serif;
  font-weight: 900;
  font-size: clamp(60px, 10vw, 140px);
  color: #e8e0d0;
  letter-spacing: -0.02em;
  line-height: 1.05;
  margin-bottom: 0.3em;
}
.pf-hero-sub {
  font-size: clamp(16px, 2vw, 22px);
  color: #8a9ab0;
  max-width: 620px;
  font-weight: 300;
  line-height: 1.6;
  margin-bottom: 1em;
}
.pf-hero-meta {
  font-size: 0.82rem;
  color: #5a6a7a;
  letter-spacing: 0.04em;
}
.pf-hero-meta em { color: #8a9ab0; font-style: italic; }

/* scroll indicator */
.pf-scroll-hint {
  position: absolute;
  bottom: 2.5rem;
  left: 50%;
  transform: translateX(-50%);
  animation: pf-bob 2s ease-in-out infinite;
}
.pf-scroll-hint svg { opacity: 0.35; }
@keyframes pf-bob {
  0%, 100% { transform: translateX(-50%) translateY(0); }
  50% { transform: translateX(-50%) translateY(8px); }
}

/* ── stats ribbon ── */
.pf-stats {
  display: flex;
  justify-content: center;
  gap: clamp(2rem, 6vw, 6rem);
  padding: 4rem 2rem;
  background: rgba(45, 106, 90, 0.04);
  flex-wrap: wrap;
}
.pf-stat { text-align: center; }
.pf-stat-num {
  font-family: 'Playfair Display', serif;
  font-weight: 700;
  font-size: clamp(40px, 6vw, 80px);
  color: #e07a5f;
  line-height: 1.1;
}
.pf-stat-label {
  font-size: 0.85rem;
  color: #8a9ab0;
  margin-top: 0.3em;
  font-weight: 400;
}

/* ── wavy divider ── */
.pf-wave-div { width: 100%; overflow: hidden; line-height: 0; padding: 0; }
.pf-wave-div svg { display: block; width: 100%; height: 24px; }

/* ── feature sections ── */
.pf-feat {
  display: flex;
  align-items: center;
  gap: clamp(2rem, 5vw, 5rem);
  padding: clamp(3rem, 6vh, 6rem) clamp(2rem, 8vw, 10rem);
  position: relative;
}
.pf-feat:nth-child(even) { flex-direction: row-reverse; background: rgba(45, 106, 90, 0.04); }
.pf-feat-text { flex: 1; min-width: 280px; }
.pf-feat-vis { flex: 0 0 300px; height: 200px; position: relative; }
.pf-feat-vis canvas { width: 100%; height: 100%; border-radius: 12px; }

.pf-feat h2 {
  font-family: 'Playfair Display', serif;
  font-weight: 700;
  font-size: clamp(28px, 4vw, 48px);
  color: #e8e0d0;
  margin-bottom: 0.5em;
  line-height: 1.15;
}
.pf-feat p {
  color: #8a9ab0;
  font-size: 1rem;
  line-height: 1.7;
  margin-bottom: 1em;
}
.pf-feat blockquote {
  border-left: 3px solid #e07a5f;
  padding-left: 1em;
  margin: 1em 0 1.5em;
  font-style: italic;
  color: #c0b8a8;
  font-size: 0.95rem;
  line-height: 1.6;
}
.pf-cta {
  display: inline-block;
  padding: 0.65em 1.8em;
  border-radius: 100px;
  background: #e07a5f;
  color: #0a0e1a;
  font-family: 'Source Sans 3', sans-serif;
  font-weight: 600;
  font-size: 0.95rem;
  text-decoration: none;
  border: none;
  cursor: pointer;
  transition: background 0.25s ease;
}
.pf-cta:hover { background: #c96a4f; }

/* hover glow on feature sections */
.pf-feat:hover {
  box-shadow: 0 0 0 1px rgba(224, 122, 95, 0.25);
}

/* ── methodology pipeline ── */
.pf-pipeline {
  padding: 4rem 2rem;
  text-align: center;
}
.pf-pipeline h3 {
  font-family: 'Playfair Display', serif;
  font-weight: 700;
  font-size: 1.6rem;
  color: #e8e0d0;
  margin-bottom: 2rem;
}
.pf-pipe-row {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0;
  flex-wrap: wrap;
  max-width: 900px;
  margin: 0 auto;
}
.pf-pipe-node {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.5rem;
}
.pf-pipe-dot {
  width: 14px; height: 14px;
  border-radius: 50%;
  background: #2d6a5a;
  border: 2px solid #3a8a74;
}
.pf-pipe-label {
  font-size: 0.78rem;
  color: #8a9ab0;
  max-width: 100px;
  text-align: center;
  line-height: 1.35;
}
.pf-pipe-line {
  width: 60px;
  height: 2px;
  margin-bottom: 1.6rem;
  overflow: visible;
}

/* ── footer ── */
.pf-footer {
  padding: 3rem 2rem 2rem;
  text-align: center;
  color: #5a6a7a;
  font-size: 0.82rem;
  line-height: 2;
  border-top: 1px solid rgba(45, 106, 90, 0.15);
}
.pf-footer strong { color: #8a9ab0; font-weight: 400; }

/* ── bottle animation ── */
#pf-bottle-wrap {
  position: fixed;
  pointer-events: none;
  z-index: 9998;
  width: 60px;
  height: 120px;
  top: 0; left: 0;
  will-change: transform, opacity;
}
#pf-bottle-wrap .pf-frag { position: absolute; opacity: 0; transition: none; }
</style>

<!-- ═══════ BOTTLE SVG (fixed on screen) ═══════ -->
<div id="pf-bottle-wrap">
  <svg id="pf-bottle-svg" viewBox="0 0 60 120" width="60" height="120" fill="none" xmlns="http://www.w3.org/2000/svg">
    <defs>
      <linearGradient id="bg" x1="20" y1="0" x2="40" y2="120" gradientUnits="userSpaceOnUse">
        <stop offset="0%" stop-color="#d0e8f0" stop-opacity="0.45"/>
        <stop offset="100%" stop-color="#8ab8d0" stop-opacity="0.25"/>
      </linearGradient>
    </defs>
    <!-- cap -->
    <rect x="23" y="2" width="14" height="10" rx="3" fill="#e8e0d0" fill-opacity="0.5" stroke="#8a9ab0" stroke-width="0.8"/>
    <!-- neck -->
    <path d="M25 12 L25 22 Q20 26 18 32 L18 32" stroke="#8a9ab0" stroke-width="0.8" fill="none"/>
    <path d="M35 12 L35 22 Q40 26 42 32 L42 32" stroke="#8a9ab0" stroke-width="0.8" fill="none"/>
    <!-- body -->
    <path d="M18 32 Q16 34 16 40 L16 100 Q16 110 22 112 L38 112 Q44 110 44 100 L44 40 Q44 34 42 32 Z"
          fill="url(#bg)" stroke="#8a9ab0" stroke-width="0.8"/>
    <!-- label band -->
    <rect x="18" y="55" width="24" height="18" rx="2" fill="rgba(224,122,95,0.12)" stroke="rgba(224,122,95,0.25)" stroke-width="0.5"/>
    <!-- water line -->
    <path d="M18 78 Q24 74 30 78 Q36 82 42 78" stroke="rgba(45,106,90,0.4)" stroke-width="0.7" fill="none"/>
    <!-- highlight -->
    <line x1="22" y1="36" x2="22" y2="95" stroke="rgba(232,224,208,0.12)" stroke-width="1.5" stroke-linecap="round"/>
  </svg>
  <!-- fragment pieces (hidden initially) -->
  <svg class="pf-frag" id="pf-f0" viewBox="0 0 18 18" width="18" height="18"><polygon points="2,8 9,1 16,6 12,16 4,14" fill="rgba(208,232,240,0.35)" stroke="#8a9ab0" stroke-width="0.6"/></svg>
  <svg class="pf-frag" id="pf-f1" viewBox="0 0 14 14" width="14" height="14"><polygon points="1,5 7,1 13,7 8,13 2,10" fill="rgba(138,184,208,0.3)" stroke="#8a9ab0" stroke-width="0.5"/></svg>
  <svg class="pf-frag" id="pf-f2" viewBox="0 0 16 12" width="16" height="12"><polygon points="1,6 8,1 15,4 12,11 3,10" fill="rgba(224,122,95,0.2)" stroke="#e07a5f" stroke-width="0.5"/></svg>
  <svg class="pf-frag" id="pf-f3" viewBox="0 0 12 16" width="12" height="16"><polygon points="2,3 10,1 11,10 6,15 1,11" fill="rgba(45,106,90,0.25)" stroke="#2d6a5a" stroke-width="0.5"/></svg>
  <svg class="pf-frag" id="pf-f4" viewBox="0 0 15 13" width="15" height="13"><polygon points="3,1 12,3 14,10 7,12 1,8" fill="rgba(208,232,240,0.3)" stroke="#8a9ab0" stroke-width="0.5"/></svg>
</div>

<div class="pf-landing">

<!-- ═══════ HERO ═══════ -->
<section class="pf-hero">
  <h1 class="pf-hero-title">PlasticFlow</h1>
  <p class="pf-hero-sub">Tracing microplastics from ocean to gyre &mdash; 50&nbsp;years of data, simulated.</p>
  <p class="pf-hero-meta">NC SMathHacks 2026 &nbsp;&middot;&nbsp; <em>Under the Sea</em> &nbsp;&middot;&nbsp; NOAA NCEI &times; NASA OSCAR</p>
  <div class="pf-scroll-hint">
    <svg width="24" height="24" viewBox="0 0 24 24" stroke="#8a9ab0" stroke-width="2" fill="none">
      <polyline points="6,9 12,15 18,9"/>
    </svg>
  </div>
</section>

<!-- ═══════ STATS RIBBON ═══════ -->
<section class="pf-stats pf-reveal">
  <div class="pf-stat"><div class="pf-stat-num" data-target="16706">0</div><div class="pf-stat-label">NOAA observations</div></div>
  <div class="pf-stat"><div class="pf-stat-num" data-target="5">0</div><div class="pf-stat-label">ocean basins</div></div>
  <div class="pf-stat"><div class="pf-stat-num" data-target="18">0</div><div class="pf-stat-label">coastal cities simulated</div></div>
  <div class="pf-stat"><div class="pf-stat-num" data-target="5">0</div><div class="pf-stat-label">years of drift</div></div>
</section>

<!-- divider -->
<div class="pf-wave-div"><svg viewBox="0 0 1200 24" preserveAspectRatio="none"><path d="M0 12 Q150 0 300 12 T600 12 T900 12 T1200 12" stroke="rgba(45,106,90,0.3)" stroke-width="1" fill="none"/></svg></div>

<!-- ═══════ FEATURE 1: Observations ═══════ -->
<section class="pf-feat pf-reveal">
  <div class="pf-feat-text">
    <h2>Global Observations</h2>
    <p>16,706 NOAA sampling events spanning 1972 to 2023, plotted on a dark interactive world map and colored by density. Filter by ocean basin and year range, with DBSCAN hotspot clusters overlaid.</p>
    <blockquote>Pacific and Indian Oceans show peak concentrations &mdash; matching the five major subtropical gyres.</blockquote>
    <button class="pf-cta">Open Map &rarr;</button>
  </div>
  <div class="pf-feat-vis"><canvas id="pf-cv-obs" width="600" height="400"></canvas></div>
</section>

<div class="pf-wave-div"><svg viewBox="0 0 1200 24" preserveAspectRatio="none"><path d="M0 12 Q150 24 300 12 T600 12 T900 12 T1200 12" stroke="rgba(45,106,90,0.3)" stroke-width="1" fill="none"/></svg></div>

<!-- ═══════ FEATURE 2: Currents ═══════ -->
<section class="pf-feat pf-reveal">
  <div class="pf-feat-text">
    <h2>Ocean Currents</h2>
    <p>NASA OSCAR surface current streamlines rendered at 1/3&deg; resolution. Color and thickness encode speed, revealing the Gulf Stream, Kuroshio Current, and gyre circulation pathways.</p>
    <blockquote>The five subtropical gyres act as conveyor belts, funneling plastic into persistent accumulation zones.</blockquote>
    <button class="pf-cta">Explore Currents &rarr;</button>
  </div>
  <div class="pf-feat-vis"><canvas id="pf-cv-cur" width="600" height="400"></canvas></div>
</section>

<div class="pf-wave-div"><svg viewBox="0 0 1200 24" preserveAspectRatio="none"><path d="M0 12 Q150 0 300 12 T600 12 T900 12 T1200 12" stroke="rgba(45,106,90,0.3)" stroke-width="1" fill="none"/></svg></div>

<!-- ═══════ FEATURE 3: Drift ═══════ -->
<section class="pf-feat pf-reveal">
  <div class="pf-feat-text">
    <h2>Drift Simulation</h2>
    <p>A 5-year Lagrangian particle simulation releases particles from 18 coastal cities worldwide and advects them daily using real OSCAR velocity fields. Watch them converge.</p>
    <blockquote>Within 1&ndash;2 years, particles accumulate in the same gyres where NOAA records the highest concentrations.</blockquote>
    <button class="pf-cta">Run Simulation &rarr;</button>
  </div>
  <div class="pf-feat-vis"><canvas id="pf-cv-drift" width="600" height="400"></canvas></div>
</section>

<div class="pf-wave-div"><svg viewBox="0 0 1200 24" preserveAspectRatio="none"><path d="M0 12 Q150 24 300 12 T600 12 T900 12 T1200 12" stroke="rgba(45,106,90,0.3)" stroke-width="1" fill="none"/></svg></div>

<!-- ═══════ FEATURE 4: Statistics ═══════ -->
<section class="pf-feat pf-reveal">
  <div class="pf-feat-text">
    <h2>Statistical Insights</h2>
    <p>Basin-level comparisons, temporal trend decomposition, DBSCAN hotspot clustering with haversine distance, and Spearman rank correlation across geographic features.</p>
    <blockquote>Latitude and longitude correlate significantly with density (p&nbsp;&lt;&nbsp;0.05) &mdash; geography drives accumulation.</blockquote>
    <button class="pf-cta">View Insights &rarr;</button>
  </div>
  <div class="pf-feat-vis">
    <svg id="pf-sv-stats" viewBox="0 0 300 200" width="300" height="200" style="border-radius:12px;">
      <text x="10" y="26" fill="#8a9ab0" font-size="10" font-family="Source Sans 3,sans-serif">N. Pacific</text>
      <rect class="pf-bar" x="90" y="14" width="0" height="14" rx="3" fill="#e07a5f" data-w="180"/>
      <text x="10" y="52" fill="#8a9ab0" font-size="10" font-family="Source Sans 3,sans-serif">Indian</text>
      <rect class="pf-bar" x="90" y="40" width="0" height="14" rx="3" fill="#e07a5f" data-w="145" opacity="0.85"/>
      <text x="10" y="78" fill="#8a9ab0" font-size="10" font-family="Source Sans 3,sans-serif">S. Pacific</text>
      <rect class="pf-bar" x="90" y="66" width="0" height="14" rx="3" fill="#e07a5f" data-w="120" opacity="0.7"/>
      <text x="10" y="104" fill="#8a9ab0" font-size="10" font-family="Source Sans 3,sans-serif">N. Atlantic</text>
      <rect class="pf-bar" x="90" y="92" width="0" height="14" rx="3" fill="#e07a5f" data-w="100" opacity="0.6"/>
      <text x="10" y="130" fill="#8a9ab0" font-size="10" font-family="Source Sans 3,sans-serif">S. Atlantic</text>
      <rect class="pf-bar" x="90" y="118" width="0" height="14" rx="3" fill="#e07a5f" data-w="65" opacity="0.5"/>
    </svg>
  </div>
</section>

<!-- ═══════ METHODOLOGY PIPELINE ═══════ -->
<section class="pf-pipeline pf-reveal">
  <h3>Methodology</h3>
  <div class="pf-pipe-row">
    <div class="pf-pipe-node"><div class="pf-pipe-dot"></div><div class="pf-pipe-label">Data Ingestion</div></div>
    <svg class="pf-pipe-line" viewBox="0 0 60 12"><path d="M0 6 Q15 2 30 6 T60 6" stroke="rgba(45,106,90,0.4)" stroke-width="1.2" fill="none"/></svg>
    <div class="pf-pipe-node"><div class="pf-pipe-dot"></div><div class="pf-pipe-label">Spatial Cleaning</div></div>
    <svg class="pf-pipe-line" viewBox="0 0 60 12"><path d="M0 6 Q15 10 30 6 T60 6" stroke="rgba(45,106,90,0.4)" stroke-width="1.2" fill="none"/></svg>
    <div class="pf-pipe-node"><div class="pf-pipe-dot"></div><div class="pf-pipe-label">Statistical Analysis</div></div>
    <svg class="pf-pipe-line" viewBox="0 0 60 12"><path d="M0 6 Q15 2 30 6 T60 6" stroke="rgba(45,106,90,0.4)" stroke-width="1.2" fill="none"/></svg>
    <div class="pf-pipe-node"><div class="pf-pipe-dot"></div><div class="pf-pipe-label">Drift Simulation</div></div>
    <svg class="pf-pipe-line" viewBox="0 0 60 12"><path d="M0 6 Q15 10 30 6 T60 6" stroke="rgba(45,106,90,0.4)" stroke-width="1.2" fill="none"/></svg>
    <div class="pf-pipe-node"><div class="pf-pipe-dot"></div><div class="pf-pipe-label">Visualization</div></div>
  </div>
</section>

<!-- ═══════ FOOTER ═══════ -->
<footer class="pf-footer">
  <strong>NC SMathHacks 2026</strong> &nbsp;&middot;&nbsp; Theme: Under the Sea<br>
  Data: NOAA NCEI Marine Microplastics &nbsp;&middot;&nbsp; NASA OSCAR Surface Currents<br>
  Built with Python &nbsp;&middot;&nbsp; Streamlit &nbsp;&middot;&nbsp; Plotly &nbsp;&middot;&nbsp; NumPy &nbsp;&middot;&nbsp; scikit-learn
</footer>

</div><!-- / .pf-landing -->

<script>
(function(){
  /* ── helpers ── */
  function lerp(a,b,t){ return a + (b - a) * t; }
  function clamp(v,lo,hi){ return Math.max(lo, Math.min(hi, v)); }
  function ease(t){ return t < 0.5 ? 2*t*t : -1 + (4 - 2*t)*t; } /* ease-in-out quad */

  /* ── find Streamlit's scroll container ── */
  function getScrollEl(){
    /* Streamlit wraps content in a scrollable div; walk up from the landing div */
    var el = document.querySelector('.pf-landing');
    while(el){
      if(el.scrollHeight > el.clientHeight + 10 && getComputedStyle(el).overflowY !== 'visible'){
        return el;
      }
      el = el.parentElement;
    }
    return window;
  }

  /* ── scroll progress ── */
  var ticking = false;
  function getProgress(){
    var sc = getScrollEl();
    if(sc === window){
      var h = document.documentElement.scrollHeight - window.innerHeight;
      return h > 0 ? window.scrollY / h : 0;
    }
    var h = sc.scrollHeight - sc.clientHeight;
    return h > 0 ? sc.scrollTop / h : 0;
  }

  /* ── BOTTLE ANIMATION ── */
  var bw = document.getElementById('pf-bottle-wrap');
  var bSvg = document.getElementById('pf-bottle-svg');
  var frags = [
    { el: document.getElementById('pf-f0'), dx: -120, dy: -80, rot: 35 },
    { el: document.getElementById('pf-f1'), dx: 100, dy: -110, rot: -50 },
    { el: document.getElementById('pf-f2'), dx: 140, dy: 40, rot: 70 },
    { el: document.getElementById('pf-f3'), dx: -100, dy: 70, rot: -30 },
    { el: document.getElementById('pf-f4'), dx: 50, dy: 120, rot: 55 }
  ];

  function updateBottle(p){
    if(!bw) return;
    var vw = window.innerWidth, vh = window.innerHeight;

    if(p < 0.01){
      /* off screen below */
      bw.style.opacity = '0';
      return;
    }

    /* phase 1: 0-15% enter from lower right */
    if(p < 0.15){
      var t = ease(p / 0.15);
      var x = lerp(vw * 0.85, vw * 0.75, t);
      var y = lerp(vh * 1.1, vh * 0.65, t);
      var rot = lerp(15, 5, t);
      var sc = lerp(0.7, 1, t);
      var op = lerp(0, 0.9, t);
      bw.style.transform = 'translate(' + x + 'px,' + y + 'px) rotate(' + rot + 'deg) scale(' + sc + ')';
      bw.style.opacity = op;
      bSvg.style.opacity = '1';
      for(var i = 0; i < frags.length; i++) frags[i].el.style.opacity = '0';
      return;
    }

    /* phase 2: 15-50% S-curve drift */
    if(p < 0.50){
      var t2 = (p - 0.15) / 0.35;
      var et = ease(t2);
      var x = vw * (0.2 + 0.6 * Math.sin(et * Math.PI * 1.5));
      var y = vh * (0.65 - et * 0.5);
      /* bobbing */
      var bob = Math.sin(t2 * Math.PI * 6) * 8;
      y += bob;
      var rot = Math.sin(t2 * Math.PI * 4) * 12;
      var sc = 1 + Math.sin(t2 * Math.PI * 3) * 0.05;
      bw.style.transform = 'translate(' + x + 'px,' + y + 'px) rotate(' + rot + 'deg) scale(' + sc + ')';
      bw.style.opacity = '0.9';
      bSvg.style.opacity = '1';
      for(var i = 0; i < frags.length; i++) frags[i].el.style.opacity = '0';
      return;
    }

    /* phase 3: 50-70% crack / fragment transition */
    if(p < 0.70){
      var t3 = (p - 0.50) / 0.20;
      var et3 = ease(t3);
      var x = vw * (0.2 + 0.6 * Math.sin(ease(1.0) * Math.PI * 1.5));
      var y = vh * 0.15;
      var shake = Math.sin(t3 * Math.PI * 10) * (4 * t3);
      bw.style.transform = 'translate(' + (x + shake) + 'px,' + y + 'px) rotate(' + (shake * 0.5) + 'deg) scale(' + lerp(1, 0.9, et3) + ')';
      bw.style.opacity = '0.9';
      bSvg.style.opacity = String(1 - et3);
      for(var i = 0; i < frags.length; i++){
        frags[i].el.style.opacity = String(et3 * 0.8);
        var fd = et3 * 0.3;
        frags[i].el.style.transform = 'translate(' + (frags[i].dx * fd) + 'px,' + (frags[i].dy * fd) + 'px) rotate(' + (frags[i].rot * fd) + 'deg)';
      }
      return;
    }

    /* phase 4: 70-100% fragments scatter and fade */
    var t4 = (p - 0.70) / 0.30;
    var et4 = ease(t4);
    var baseX = vw * 0.5;
    var baseY = vh * 0.15;
    bw.style.transform = 'translate(' + baseX + 'px,' + baseY + 'px)';
    bSvg.style.opacity = '0';
    for(var i = 0; i < frags.length; i++){
      var spread = 0.3 + et4 * 0.7;
      frags[i].el.style.opacity = String(clamp(0.8 - et4 * 1.2, 0, 0.8));
      frags[i].el.style.transform = 'translate(' + (frags[i].dx * spread) + 'px,' + (frags[i].dy * spread) + 'px) rotate(' + (frags[i].rot * spread) + 'deg)';
    }
    bw.style.opacity = String(clamp(1 - et4 * 1.3, 0, 1));
  }

  /* ── INTERSECTION OBSERVER: reveal + counters + bars ── */
  var revealed = new Set();
  var counted = new Set();
  var barsDone = false;

  function animateCount(el){
    var target = parseInt(el.getAttribute('data-target'), 10);
    var duration = 1600;
    var start = performance.now();
    function tick(now){
      var t = clamp((now - start) / duration, 0, 1);
      var et = ease(t);
      el.textContent = Math.round(et * target).toLocaleString();
      if(t < 1) requestAnimationFrame(tick);
    }
    requestAnimationFrame(tick);
  }

  function animateBars(){
    var bars = document.querySelectorAll('.pf-bar');
    bars.forEach(function(b){
      var w = b.getAttribute('data-w');
      b.style.transition = 'width 1s ease';
      b.style.width = w + 'px';
    });
  }

  var obs = new IntersectionObserver(function(entries){
    entries.forEach(function(e){
      if(e.isIntersecting){
        var el = e.target;
        if(el.classList.contains('pf-reveal') && !revealed.has(el)){
          revealed.add(el);
          el.classList.add('pf-visible');
        }
        /* counter animation */
        el.querySelectorAll('.pf-stat-num').forEach(function(sn){
          if(!counted.has(sn)){ counted.add(sn); animateCount(sn); }
        });
        /* bar animation */
        if(!barsDone && el.querySelector('.pf-bar')){
          barsDone = true;
          animateBars();
        }
      }
    });
  }, { threshold: 0.15, root: null });

  document.querySelectorAll('.pf-reveal').forEach(function(el){ obs.observe(el); });
  /* immediately reveal everything visible in the initial viewport */
  document.querySelectorAll('.pf-reveal').forEach(function(el){
    var r = el.getBoundingClientRect();
    if(r.top < window.innerHeight * 1.1){ el.classList.add('pf-visible'); }
  });

  /* ── MINI CANVAS VISUALIZATIONS ── */

  /* 1. Observations: scattered dots */
  (function(){
    var c = document.getElementById('pf-cv-obs');
    if(!c) return;
    var ctx = c.getContext('2d');
    var dots = [];
    /* weighted toward Pacific / Indian ocean zones in abstract */
    for(var i = 0; i < 200; i++){
      var zone = Math.random();
      var x, y;
      if(zone < 0.4){ x = 350 + Math.random()*200; y = 100 + Math.random()*200; }
      else if(zone < 0.7){ x = 100 + Math.random()*150; y = 120 + Math.random()*180; }
      else { x = Math.random()*600; y = Math.random()*400; }
      dots.push({ x:x, y:y, r: 1.5 + Math.random()*2, delay: Math.random()*3000, hue: Math.random() });
    }
    var start = performance.now();
    function draw(){
      ctx.clearRect(0,0,600,400);
      var now = performance.now() - start;
      dots.forEach(function(d){
        var a = clamp((now - d.delay) / 800, 0, 1);
        if(a <= 0) return;
        var r = Math.round(lerp(224, 232, d.hue));
        var g = Math.round(lerp(122, 224, d.hue));
        var b = Math.round(lerp(95, 208, d.hue));
        ctx.beginPath();
        ctx.arc(d.x, d.y, d.r, 0, Math.PI*2);
        ctx.fillStyle = 'rgba('+r+','+g+','+b+','+(a*0.7)+')';
        ctx.fill();
      });
      if(performance.now() - start < 5000) requestAnimationFrame(draw);
    }
    draw();
  })();

  /* 2. Currents: flowing bezier lines */
  (function(){
    var c = document.getElementById('pf-cv-cur');
    if(!c) return;
    var ctx = c.getContext('2d');
    var lines = [];
    for(var i = 0; i < 25; i++){
      lines.push({
        y: 30 + Math.random()*340,
        amp: 20 + Math.random()*40,
        freq: 0.005 + Math.random()*0.008,
        speed: 0.5 + Math.random()*1.5,
        op: 0.15 + Math.random()*0.35,
        w: 0.5 + Math.random()*1.5
      });
    }
    var off = 0;
    function draw(){
      ctx.clearRect(0,0,600,400);
      off += 1.2;
      lines.forEach(function(l){
        ctx.beginPath();
        for(var x = 0; x <= 600; x += 4){
          var y = l.y + Math.sin((x + off * l.speed) * l.freq) * l.amp;
          if(x === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
        }
        ctx.strokeStyle = 'rgba(45,106,90,' + l.op + ')';
        ctx.lineWidth = l.w;
        ctx.stroke();
      });
      requestAnimationFrame(draw);
    }
    draw();
  })();

  /* 3. Drift: particles spiraling inward */
  (function(){
    var c = document.getElementById('pf-cv-drift');
    if(!c) return;
    var ctx = c.getContext('2d');
    var centers = [{x:220, y:160},{x:400, y:220}];
    var particles = [];
    var origins = [
      {x:10,y:50},{x:590,y:60},{x:10,y:350},{x:590,y:340},{x:300,y:10},{x:300,y:390}
    ];
    for(var i = 0; i < 80; i++){
      var o = origins[i % origins.length];
      var dest = centers[i % 2];
      particles.push({
        ox: o.x + (Math.random()-0.5)*40,
        oy: o.y + (Math.random()-0.5)*40,
        dx: dest.x + (Math.random()-0.5)*30,
        dy: dest.y + (Math.random()-0.5)*30,
        t: Math.random(),
        speed: 0.001 + Math.random()*0.002,
        r: 1.2 + Math.random()*1.5
      });
    }
    function draw(){
      ctx.clearRect(0,0,600,400);
      particles.forEach(function(p){
        p.t += p.speed;
        if(p.t > 1) p.t = 0;
        var et = ease(p.t);
        /* spiral offset */
        var angle = p.t * Math.PI * 4;
        var spiral = (1 - et) * 40;
        var x = lerp(p.ox, p.dx, et) + Math.cos(angle) * spiral;
        var y = lerp(p.oy, p.dy, et) + Math.sin(angle) * spiral;
        ctx.beginPath();
        ctx.arc(x, y, p.r, 0, Math.PI*2);
        ctx.fillStyle = 'rgba(224,122,95,' + (0.3 + et * 0.4) + ')';
        ctx.fill();
      });
      requestAnimationFrame(draw);
    }
    draw();
  })();

  /* ── SCROLL HANDLER — attach to Streamlit scroll container ── */
  function attachScroll(){
    var sc = getScrollEl();
    var target = (sc === window) ? window : sc;
    target.addEventListener('scroll', function(){
      if(!ticking){
        ticking = true;
        requestAnimationFrame(function(){
          updateBottle(getProgress());
          ticking = false;
        });
      }
    }, { passive: true });
  }

  /* wait for DOM to settle before attaching */
  setTimeout(function(){
    attachScroll();
    updateBottle(getProgress());
    /* trigger reveal for items already in view */
    document.querySelectorAll('.pf-reveal').forEach(function(el){
      var r = el.getBoundingClientRect();
      if(r.top < window.innerHeight){ el.classList.add('pf-visible'); }
    });
    /* trigger stat counters for visible stats */
    document.querySelectorAll('.pf-stat-num').forEach(function(sn){
      var r = sn.getBoundingClientRect();
      if(r.top < window.innerHeight && !counted.has(sn)){ counted.add(sn); animateCount(sn); }
    });
  }, 300);
})();
</script>
"""


def render() -> None:
    """Render the PlasticFlow editorial landing page."""
    st.markdown(_HTML, unsafe_allow_html=True)
