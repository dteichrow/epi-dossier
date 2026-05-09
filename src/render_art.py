from __future__ import annotations

import html


THEMES = {
    "respiratory": {
        "bg_a": "#102739",
        "bg_b": "#1f4b68",
        "accent": "#d8edf6",
        "signal": "#a7d3e7",
        "gold": "#d8aa46",
    },
    "vector": {
        "bg_a": "#173226",
        "bg_b": "#376846",
        "accent": "#d8f1dc",
        "signal": "#9fd0aa",
        "gold": "#d4b15a",
    },
    "enteric": {
        "bg_a": "#17394a",
        "bg_b": "#2a6278",
        "accent": "#d7f0f6",
        "signal": "#8ac7da",
        "gold": "#e3bf67",
    },
    "hemorrhagic": {
        "bg_a": "#3c181c",
        "bg_b": "#7a2c33",
        "accent": "#f5d8db",
        "signal": "#e9aab0",
        "gold": "#d7b36a",
    },
    "zoonotic": {
        "bg_a": "#2c2316",
        "bg_b": "#645238",
        "accent": "#f0e6d7",
        "signal": "#cbb89a",
        "gold": "#d4aa59",
    },
    "surveillance": {
        "bg_a": "#1a2440",
        "bg_b": "#35528a",
        "accent": "#dde5f7",
        "signal": "#9eb5ea",
        "gold": "#d8b86a",
    },
    "historical": {
        "bg_a": "#3b2a1c",
        "bg_b": "#7a6040",
        "accent": "#f3e8d8",
        "signal": "#d8c3a2",
        "gold": "#d7a95a",
    },
    "general": {
        "bg_a": "#152536",
        "bg_b": "#2f516e",
        "accent": "#e2edf5",
        "signal": "#a9c8db",
        "gold": "#d8b25b",
    },
}


def render_visual_plate(subject: str, context: str = "", mode: str = "card") -> str:
    theme_name = detect_theme(subject, context)
    palette = THEMES[theme_name]
    width, height, radius = mode_dimensions(mode)
    viewbox = f"0 0 {width} {height}"
    safe_subject = html.escape(subject or "", quote=False)
    safe_context = html.escape(context or "", quote=False)
    motif = motif_svg(theme_name, palette, width, height)
    label_block = label_svg(safe_subject, safe_context, palette, width, height, mode)
    grid = (
        f'<path d="M0 0H{width}V{height}" fill="none" stroke="rgba(255,255,255,0.08)" stroke-width="0"/>'
    )
    return f"""
<svg viewBox="{viewbox}" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="{safe_subject or 'editorial illustration'}">
  <defs>
    <linearGradient id="bg-{theme_name}-{mode}" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="{palette['bg_a']}"/>
      <stop offset="100%" stop-color="{palette['bg_b']}"/>
    </linearGradient>
    <pattern id="grid-{theme_name}-{mode}" width="28" height="28" patternUnits="userSpaceOnUse">
      <path d="M28 0H0V28" fill="none" stroke="rgba(255,255,255,0.07)" stroke-width="1"/>
    </pattern>
  </defs>
  <rect width="{width}" height="{height}" rx="{radius}" fill="url(#bg-{theme_name}-{mode})"/>
  <rect width="{width}" height="{height}" rx="{radius}" fill="url(#grid-{theme_name}-{mode})" opacity="0.55"/>
  {motif}
  {label_block}
</svg>
""".strip()


def detect_theme(subject: str, context: str) -> str:
    text = f"{subject} {context}".lower()
    if any(term in text for term in ("h5n1", "influenza", "respiratory", "tuberculosis", "measles", "rsv", "covid", "sars-cov-2", "pneumonia")):
        return "respiratory"
    if any(term in text for term in ("dengue", "malaria", "mosquito", "arbovirus", "vector", "oropouche", "rift valley", "zika")):
        return "vector"
    if any(term in text for term in ("cholera", "norovirus", "salmonella", "foodborne", "wastewater", "hepatitis a", "enteric")):
        return "enteric"
    if any(term in text for term in ("ebola", "marburg", "hemorrhagic")):
        return "hemorrhagic"
    if any(term in text for term in ("hantavirus", "rabies", "anthrax", "zoonotic", "rodent", "avian")):
        return "zoonotic"
    if any(term in text for term in ("historical", "ancient", "paleopathology", "archaeology")):
        return "historical"
    if any(term in text for term in ("surveillance", "tracking", "monitoring", "wastewater", "policy", "dashboard")):
        return "surveillance"
    return "general"


def mode_dimensions(mode: str) -> tuple[int, int, int]:
    if mode == "wide":
        return (960, 220, 26)
    if mode == "hero":
        return (1180, 240, 28)
    if mode == "thumb":
        return (220, 168, 20)
    return (360, 180, 22)


def motif_svg(theme: str, palette: dict[str, str], width: int, height: int) -> str:
    if theme == "respiratory":
        return f"""
  <path d="M60 {height-34}C120 {height-82}, 160 34, 232 40C300 46, 332 {height-66}, 300 {height-24}" fill="none" stroke="{palette['accent']}" stroke-width="6" stroke-linecap="round"/>
  <path d="M{width-64} 28C{width-180} 58, {width-248} 122, {width-306} {height-24}" fill="none" stroke="{palette['signal']}" stroke-width="5" stroke-linecap="round"/>
  <circle cx="{width-110}" cy="58" r="26" fill="none" stroke="{palette['gold']}" stroke-width="4"/>
  <path d="M{width-128} 58h36M{width-110} 40v36" stroke="{palette['gold']}" stroke-width="4" stroke-linecap="round"/>
"""
    if theme == "vector":
        return f"""
  <path d="M72 {height-36}C118 {height-104}, 176 44, 242 42" fill="none" stroke="{palette['accent']}" stroke-width="5" stroke-linecap="round"/>
  <path d="M182 42c28 22 54 62 58 96" fill="none" stroke="{palette['signal']}" stroke-width="4"/>
  <path d="M206 58c36-12 88-4 122 28" fill="none" stroke="{palette['gold']}" stroke-width="4"/>
  <circle cx="{width-84}" cy="{height-54}" r="30" fill="none" stroke="{palette['accent']}" stroke-width="4"/>
  <path d="M{width-114} {height-54}h60M{width-84} {height-84}v60" stroke="{palette['accent']}" stroke-width="4" stroke-linecap="round"/>
"""
    if theme == "enteric":
        return f"""
  <path d="M0 {height-44}C78 {height-72}, 152 {height-12}, 242 {height-38}C318 {height-60}, 404 {height-14}, {width} {height-52}" fill="none" stroke="{palette['signal']}" stroke-width="6" stroke-linecap="round"/>
  <path d="M0 {height-18}C78 {height-46}, 152 14, 242 {height-12}C318 {height-34}, 404 12, {width} {height-26}" fill="none" stroke="{palette['accent']}" stroke-width="3" stroke-linecap="round" opacity="0.9"/>
  <rect x="{width-132}" y="26" width="74" height="52" rx="16" fill="none" stroke="{palette['gold']}" stroke-width="4"/>
  <path d="M{width-95} 78v48" stroke="{palette['gold']}" stroke-width="4" stroke-linecap="round"/>
"""
    if theme == "hemorrhagic":
        return f"""
  <path d="M82 32C114 84, 126 108, 126 128C126 162, 102 184, 74 184C46 184, 22 162, 22 128C22 108, 40 82, 82 32Z" fill="none" stroke="{palette['accent']}" stroke-width="5"/>
  <path d="M214 26C254 72, 274 102, 274 130C274 166, 248 188, 218 188C188 188, 162 166, 162 130C162 102, 176 74, 214 26Z" fill="none" stroke="{palette['signal']}" stroke-width="5"/>
  <path d="M{width-210} 48C{width-148} 78, {width-120} 114, {width-78} 174" fill="none" stroke="{palette['gold']}" stroke-width="5" stroke-linecap="round"/>
"""
    if theme == "zoonotic":
        return f"""
  <path d="M32 {height-44}C78 {height-96}, 140 {height-120}, 204 {height-122}C252 {height-124}, 298 {height-96}, 346 {height-48}" fill="none" stroke="{palette['accent']}" stroke-width="5" stroke-linecap="round"/>
  <circle cx="92" cy="58" r="18" fill="none" stroke="{palette['gold']}" stroke-width="4"/>
  <circle cx="132" cy="88" r="14" fill="none" stroke="{palette['gold']}" stroke-width="4"/>
  <circle cx="170" cy="54" r="12" fill="none" stroke="{palette['gold']}" stroke-width="4"/>
  <path d="M{width-180} 30l62 38-62 38z" fill="none" stroke="{palette['signal']}" stroke-width="4" stroke-linejoin="round"/>
  <path d="M{width-142} 68h84" stroke="{palette['signal']}" stroke-width="4" stroke-linecap="round"/>
"""
    if theme == "historical":
        return f"""
  <rect x="28" y="26" width="170" height="{height-52}" rx="18" fill="none" stroke="{palette['accent']}" stroke-width="4"/>
  <path d="M54 58H174M54 82H168M54 106H156M54 130H176" stroke="{palette['signal']}" stroke-width="4" stroke-linecap="round"/>
  <circle cx="{width-120}" cy="64" r="30" fill="none" stroke="{palette['gold']}" stroke-width="4"/>
  <path d="M{width-148} {height-44}C{width-124} {height-84}, {width-92} {height-102}, {width-54} {height-128}" fill="none" stroke="{palette['accent']}" stroke-width="5" stroke-linecap="round"/>
"""
    if theme == "surveillance":
        return f"""
  <path d="M18 {height-54}H{width-18}" stroke="{palette['signal']}" stroke-width="4" stroke-linecap="round"/>
  <path d="M40 {height-54}C78 {height-52}, 108 42, 154 42C196 42, 210 {height-84}, 258 {height-84}C302 {height-84}, 326 {height-30}, 388 {height-42}" fill="none" stroke="{palette['accent']}" stroke-width="5" stroke-linecap="round"/>
  <circle cx="{width-98}" cy="54" r="28" fill="none" stroke="{palette['gold']}" stroke-width="4"/>
  <path d="M{width-98} 26V82M{width-126} 54H{width-70}" stroke="{palette['gold']}" stroke-width="4" stroke-linecap="round"/>
"""
    return f"""
  <path d="M24 {height-46}C88 {height-102}, 176 28, 286 34C378 40, 438 {height-70}, {width-34} {height-34}" fill="none" stroke="{palette['accent']}" stroke-width="5" stroke-linecap="round"/>
  <path d="M{width-170} 32l94 48-94 48z" fill="none" stroke="{palette['signal']}" stroke-width="4" stroke-linejoin="round"/>
  <circle cx="94" cy="60" r="28" fill="none" stroke="{palette['gold']}" stroke-width="4"/>
"""


def label_svg(subject: str, context: str, palette: dict[str, str], width: int, height: int, mode: str) -> str:
    if mode == "thumb":
        return ""
    max_width = width - 48
    if mode == "hero":
        y = height - 28
    elif mode == "wide":
        y = height - 24
    else:
        y = height - 18
    text = context if context else subject
    safe_text = html.escape(text[:72], quote=False)
    return f"""
  <text x="24" y="{y}" fill="{palette['accent']}" font-family="'Avenir Next Condensed', 'Franklin Gothic Medium', sans-serif" font-size="13" font-weight="700" letter-spacing="2.4">{safe_text.upper()}</text>
"""
