"""Generate docs/assets/banner.svg: an animated (pure CSS, no JS) README header.

GitHub renders SVGs in <img> tags with CSS animations, but without external
fonts or scripts, so this sticks to system font stacks and @keyframes.

    python docs/scripts/make_banner.py
"""

from __future__ import annotations

from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "assets" / "banner.svg"

W, H = 1200, 380
CYCLE = 10  # seconds per loop

SANS = "'Segoe UI', -apple-system, BlinkMacSystemFont, Helvetica, Arial, sans-serif"
MONO = "ui-monospace, SFMono-Regular, Consolas, 'Liberation Mono', Menlo, monospace"

BG, PANEL, LINE = "#0b0c10", "#111318", "#ffffff14"
FG, MUTED, FAINT = "#e8eaf0", "#969caa", "#5f6573"
ACCENT, OK, WARN = "#8b7bff", "#34d399", "#fbbf24"

COMMAND = "$ optlens prog.c   # gcc+clang × -O0/-O2/-O3"
CHAR_W = 9.6  # 16px monospace ~ 0.6em per glyph
ROWS = [("gcc", "-O0", "1"), ("gcc", "-O2", "1"), ("gcc", "-O3", "1"),
        ("clang", "-O0", "0"), ("clang", "-O2", "1"), ("clang", "-O3", "1")]
ODD = 3  # the row that disagrees


def pct(seconds: float) -> str:
    return f"{seconds / CYCLE * 100:.2f}%"


def keyframes() -> str:
    type_end = 2.0
    css = [
        # Whole dynamic layer fades out at the end of each loop, then restarts.
        f"@keyframes loop {{ 0% {{opacity:0}} 3% {{opacity:1}} {pct(9.2)} {{opacity:1}} {pct(9.8)} {{opacity:0}} 100% {{opacity:0}} }}",
        f"@keyframes type {{ 0% {{width:0}} {pct(0.3)} {{width:0}} {pct(type_end)} {{width:{len(COMMAND) * CHAR_W:.0f}px}} 100% {{width:{len(COMMAND) * CHAR_W:.0f}px}} }}",
        f"@keyframes caret {{ 0% {{transform:translateX(0)}} {pct(0.3)} {{transform:translateX(0)}} "
        f"{pct(type_end)} {{transform:translateX({len(COMMAND) * CHAR_W:.0f}px)}} 100% {{transform:translateX({len(COMMAND) * CHAR_W:.0f}px)}} }}",
        "@keyframes blink { 0%, 49% {opacity:1} 50%, 100% {opacity:0} }",
    ]
    for i in range(len(ROWS)):
        start = 2.3 + i * 0.45
        done = start + 0.75
        css.append(
            f"@keyframes fill{i} {{ 0% {{transform:scaleX(0)}} {pct(start)} {{transform:scaleX(0)}} "
            f"{pct(done)} {{transform:scaleX(1)}} 100% {{transform:scaleX(1)}} }}"
        )
        css.append(
            f"@keyframes show{i} {{ 0% {{opacity:0}} {pct(done)} {{opacity:0}} {pct(done + 0.15)} {{opacity:1}} 100% {{opacity:1}} }}"
        )
    flag = 2.3 + len(ROWS) * 0.45 + 0.8
    css.append(f"@keyframes flag {{ 0% {{opacity:0}} {pct(flag)} {{opacity:0}} {pct(flag + 0.3)} {{opacity:1}} 100% {{opacity:1}} }}")
    css.append(
        f"@keyframes verdict {{ 0% {{opacity:0; transform:translateY(8px)}} {pct(flag + 0.6)} {{opacity:0; transform:translateY(8px)}} "
        f"{pct(flag + 1.0)} {{opacity:1; transform:translateY(0)}} 100% {{opacity:1; transform:translateY(0)}} }}"
    )
    css.append("@keyframes glow { 0%, 100% {opacity:.55} 50% {opacity:.9} }")
    return "\n    ".join(css)


def build() -> str:
    px, py, pw, ph = 690, 44, 466, 292  # matrix panel
    row_y0, row_h = py + 64, 30
    bar_x, bar_w = px + 150, 150
    out_x = bar_x + bar_w + 34
    rows = []
    for i, (cc, opt, out) in enumerate(ROWS):
        y = row_y0 + i * row_h
        odd = i == ODD
        color = WARN if odd else OK
        rows.append(f"""
      <g>
        {f'<rect x="{px + 10}" y="{y - 19}" width="{pw - 20}" height="{row_h - 2}" rx="7" fill="{WARN}" fill-opacity="0.10" stroke="{WARN}" stroke-opacity="0.35" style="animation:flag {CYCLE}s infinite"/>' if odd else ''}
        <text x="{px + 26}" y="{y}" class="mono" font-size="14" fill="{WARN if odd else FG}">{cc:<5} {opt}</text>
        <rect x="{bar_x}" y="{y - 8}" width="{bar_w}" height="6" rx="3" fill="{LINE}"/>
        <rect x="{bar_x}" y="{y - 8}" width="{bar_w}" height="6" rx="3" fill="{ACCENT}" class="bar" style="animation:fill{i} {CYCLE}s infinite"/>
        <g style="animation:show{i} {CYCLE}s infinite">
          <text x="{out_x}" y="{y}" class="mono" font-size="14" fill="{color}">prints {out}</text>
          <circle cx="{px + pw - 30}" cy="{y - 5}" r="5" fill="{color}"/>
        </g>
      </g>""")
    flag_t = f"animation:flag {CYCLE}s infinite"
    verdict_y = row_y0 + len(ROWS) * row_h - 4
    cmd_w = len(COMMAND) * CHAR_W

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="OptLens: see what the optimizer did, and whether it changed your program">
  <title>OptLens</title>
  <style>
    .sans {{ font-family: {SANS}; }}
    .mono {{ font-family: {MONO}; white-space: pre; }}
    .bar {{ transform-box: fill-box; transform-origin: left center; }}
    .dyn {{ animation: loop {CYCLE}s infinite; }}
    {keyframes()}
    @media (prefers-reduced-motion: reduce) {{ * {{ animation: none !important; }} }}
  </style>
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="#101219"/><stop offset="1" stop-color="{BG}"/>
    </linearGradient>
    <radialGradient id="halo" cx="0.18" cy="0.25" r="0.55">
      <stop offset="0" stop-color="{ACCENT}" stop-opacity="0.28"/><stop offset="1" stop-color="{ACCENT}" stop-opacity="0"/>
    </radialGradient>
    <pattern id="grid" width="32" height="32" patternUnits="userSpaceOnUse">
      <path d="M32 0H0V32" fill="none" stroke="#ffffff" stroke-opacity="0.035"/>
    </pattern>
    <clipPath id="typeclip"><rect x="64" y="244" height="30" width="0" style="animation:type {CYCLE}s infinite steps({len(COMMAND)})"/></clipPath>
  </defs>

  <rect width="{W}" height="{H}" rx="22" fill="url(#bg)"/>
  <rect width="{W}" height="{H}" rx="22" fill="url(#grid)"/>
  <rect width="{W}" height="{H}" rx="22" fill="url(#halo)" style="animation:glow 6s ease-in-out infinite"/>
  <rect x="0.5" y="0.5" width="{W - 1}" height="{H - 1}" rx="21.5" fill="none" stroke="{LINE}"/>

  <!-- Logo + title -->
  <g transform="translate(64 66)">
    <rect width="60" height="60" rx="15" fill="#1a1c24" stroke="{LINE}"/>
    <circle cx="26" cy="26" r="13" fill="none" stroke="{ACCENT}" stroke-width="4"/>
    <path d="M35.5 35.5l10 10" stroke="{ACCENT}" stroke-width="4" stroke-linecap="round"/>
    <path d="M20 26h12M26 20v12" stroke="{FG}" stroke-width="3" stroke-linecap="round"/>
  </g>
  <text x="142" y="112" class="sans" font-size="54" font-weight="700" fill="{FG}" letter-spacing="-1.5">OptLens</text>
  <text x="64" y="170" class="sans" font-size="21" fill="{MUTED}">See what the compiler's optimizer did to your C program,</text>
  <text x="64" y="199" class="sans" font-size="21" fill="{MUTED}">and whether it <tspan fill="{FG}" font-weight="600">changed its behaviour</tspan>.</text>

  <!-- Typed command -->
  <g class="dyn">
    <text x="64" y="265" class="mono" font-size="16" fill="{ACCENT}" clip-path="url(#typeclip)" textLength="{cmd_w:.0f}" lengthAdjust="spacing">{COMMAND.replace('$', '<tspan fill="' + FAINT + '">$</tspan>', 1)}</text>
    <g style="animation:caret {CYCLE}s infinite steps({len(COMMAND)})">
      <rect x="66" y="250" width="9" height="19" fill="{ACCENT}" style="animation:blink 1s infinite"/>
    </g>
  </g>

  <!-- Chips -->
  <g class="mono" font-size="13" fill="{MUTED}">
    {"".join(
        f'<g transform="translate({x} 302)"><rect width="{w}" height="28" rx="8" fill="#ffffff08" stroke="{LINE}"/>'
        f'<text x="{w / 2}" y="18.5" text-anchor="middle">{label}</text></g>'
        for x, w, label in [(64, 92, "GCC 13"), (164, 100, "Clang 18"), (272, 92, "ASan"),
                            (372, 92, "UBSan"), (472, 92, "MSan"), (572, 92, "Docker")]
    )}
  </g>

  <!-- Compile matrix panel -->
  <rect x="{px}" y="{py}" width="{pw}" height="{ph}" rx="16" fill="{PANEL}" stroke="{LINE}"/>
  <text x="{px + 24}" y="{py + 32}" class="sans" font-size="14" font-weight="600" fill="{FG}">Compile matrix</text>
  <text x="{px + pw - 24}" y="{py + 32}" class="mono" font-size="11" fill="{FAINT}" text-anchor="end">same output? same exit code?</text>
  <path d="M{px} {py + 46}H{px + pw}" stroke="{LINE}"/>
  <g class="dyn">{"".join(rows)}
    <g style="animation:verdict {CYCLE}s infinite">
      <rect x="{px + 10}" y="{verdict_y}" width="{pw - 20}" height="40" rx="10" fill="{WARN}" fill-opacity="0.12" stroke="{WARN}" stroke-opacity="0.45"/>
      <path d="M{px + 30} {verdict_y + 28}l9-16 9 16z" fill="none" stroke="{WARN}" stroke-width="2" stroke-linejoin="round"/>
      <path d="M{px + 39} {verdict_y + 18}v4M{px + 39} {verdict_y + 25}v.5" stroke="{WARN}" stroke-width="2" stroke-linecap="round"/>
      <text x="{px + 58}" y="{verdict_y + 25}" class="sans" font-size="14" font-weight="700" fill="{WARN}" letter-spacing="0.6">MISMATCH · UB</text>
      <text x="{px + 178}" y="{verdict_y + 25}" class="mono" font-size="12" fill="{MUTED}">UBSan: signed overflow, line 9</text>
    </g>
    <text x="{px + pw - 24}" y="{py + ph + 24}" class="sans" font-size="12" fill="{FAINT}" text-anchor="end" style="{flag_t}">your bug, not the compiler's</text>
  </g>
</svg>
"""


if __name__ == "__main__":
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(build(), encoding="utf-8")
    print("wrote", OUT)
