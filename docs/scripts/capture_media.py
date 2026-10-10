"""Capture README screenshots and the demo GIF from a running OptLens stack.

Usage (with the API and web UI running, see README "Quick start"):

    pip install playwright pillow
    python docs/scripts/capture_media.py              # uses your installed Chrome
    python docs/scripts/capture_media.py --channel msedge

Writes PNGs and demo.gif into docs/assets/.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import io
import time
from pathlib import Path

from PIL import Image
from playwright.async_api import Page, async_playwright

ASSETS = Path(__file__).resolve().parents[1] / "assets"

# A visible mouse cursor so the GIF shows what is being clicked.
CURSOR_JS = """
window.addEventListener('DOMContentLoaded', () => {
  const c = document.createElement('div');
  c.id = '__demo_cursor';
  c.innerHTML = `<svg width="22" height="22" viewBox="0 0 24 24"><path d="M4 2l15 11-6.5 1.2L16 21l-3 1.4-3.4-6.7L4 20z"
    fill="white" stroke="black" stroke-width="1.4" stroke-linejoin="round"/></svg>`;
  Object.assign(c.style, {position: 'fixed', left: '-40px', top: '-40px', zIndex: 2147483647,
    pointerEvents: 'none', transition: 'transform 120ms ease', filter: 'drop-shadow(0 2px 3px rgba(0,0,0,.5))'});
  document.body.appendChild(c);
  document.addEventListener('mousemove', e => { c.style.left = e.clientX + 'px'; c.style.top = e.clientY + 'px'; });
  document.addEventListener('mousedown', () => c.style.transform = 'scale(0.82)');
  document.addEventListener('mouseup', () => c.style.transform = 'scale(1)');
});
"""


async def fresh_page(browser, *, theme: str = "dark", width: int = 1440, height: int = 900,
                     cursor: bool = False, mobile: bool = False) -> Page:
    ctx = await browser.new_context(
        viewport={"width": width, "height": height}, device_scale_factor=1,
        is_mobile=mobile, has_touch=mobile,
    )
    await ctx.add_init_script(f"try {{ localStorage.clear(); localStorage.setItem('optlens.theme', '{theme}'); }} catch {{}}")
    if cursor:
        await ctx.add_init_script(CURSOR_JS)
    return await ctx.new_page()


async def open_app(page: Page, base: str) -> None:
    await page.goto(base + "/")
    await page.locator("main button.card").first.wait_for(state="visible")  # presets loaded
    await page.wait_for_selector("text=sandbox ready")  # health check done
    await page.wait_for_load_state("networkidle")
    await page.wait_for_timeout(1200)  # fonts, Monaco and the fade-in animation


_mouse = {"x": 0.0, "y": 0.0}


async def move_mouse(page: Page, x: float, y: float, duration_ms: int = 450) -> None:
    """Move the cursor along an eased path in real time, so recordings show the motion."""
    x0, y0 = _mouse["x"], _mouse["y"]
    steps = max(8, duration_ms // 35)
    for i in range(1, steps + 1):
        t = i / steps
        e = t * t * (3 - 2 * t)  # smoothstep
        await page.mouse.move(x0 + (x - x0) * e, y0 + (y - y0) * e)
        await page.wait_for_timeout(duration_ms / steps / 2)  # each move is itself a round-trip
    _mouse.update(x=x, y=y)


async def glide_click(page: Page, locator) -> None:
    box = await locator.bounding_box()
    assert box, "element not visible"
    await move_mouse(page, box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    await page.wait_for_timeout(150)
    await page.mouse.down()
    await page.wait_for_timeout(90)
    await page.mouse.up()


async def run_preset(page: Page, title: str, *, glide: bool = False) -> None:
    card = page.locator("main button.card", has_text=title)
    await (glide_click(page, card) if glide else card.click())
    await page.wait_for_timeout(500)
    run = page.get_by_role("button", name="Run")
    await (glide_click(page, run) if glide else run.click())
    await page.wait_for_selector("text=Compile matrix", timeout=90_000)
    await page.wait_for_timeout(700)


async def tab(page: Page, name: str, *, glide: bool = False) -> None:
    t = page.get_by_role("tab", name=name)
    await (glide_click(page, t) if glide else t.click())
    await page.wait_for_timeout(900)


async def screenshots(browser, base: str) -> None:
    page = await fresh_page(browser)
    await open_app(page, base)
    await page.screenshot(path=ASSETS / "empty-state.png")

    await run_preset(page, "Signed overflow")
    await page.screenshot(path=ASSETS / "verdict-ub.png")

    await open_app(page, base)
    await run_preset(page, "Out-of-bounds")
    await tab(page, "Outputs")
    await page.screenshot(path=ASSETS / "outputs.png")

    await open_app(page, base)
    await run_preset(page, "Loop vectorization")
    await tab(page, "Assembly Diff")
    await page.get_by_role("radio", name="Clang").click()
    await page.wait_for_timeout(900)
    await page.screenshot(path=ASSETS / "assembly-diff.png")
    await tab(page, "Optimizer Remarks")
    await page.locator("button", has_text="vectorized loop").first.click()
    await page.wait_for_timeout(300)
    await page.screenshot(path=ASSETS / "remarks.png")
    await page.context.close()

    light = await fresh_page(browser, theme="light")
    await open_app(light, base)
    await run_preset(light, "Well-defined program")
    await light.screenshot(path=ASSETS / "verdict-match-light.png")
    await light.context.close()

    phone = await fresh_page(browser, width=390, height=844, mobile=True)
    await open_app(phone, base)
    await run_preset(phone, "Uninitialized")
    await phone.locator("[role=tablist]").scroll_into_view_if_needed()
    await phone.wait_for_timeout(400)
    await phone.screenshot(path=ASSETS / "mobile.png")
    await phone.context.close()


async def record_gif(browser, base: str, width: int = 1280, height: int = 760, out_width: int = 960) -> None:
    page = await fresh_page(browser, width=width, height=height, cursor=True)
    await open_app(page, base)
    await page.mouse.move(width * 0.55, height * 0.75)
    _mouse.update(x=width * 0.55, y=height * 0.75)

    # Chrome's screencast pushes a frame whenever the page repaints, which is far
    # smoother than polling page.screenshot().
    frames: list[tuple[float, bytes]] = []
    cdp = await page.context.new_cdp_session(page)

    async def on_frame(ev: dict) -> None:
        frames.append((ev["metadata"]["timestamp"], base64.b64decode(ev["data"])))
        await cdp.send("Page.screencastFrameAck", {"sessionId": ev["sessionId"]})

    cdp.on("Page.screencastFrame", lambda ev: asyncio.ensure_future(on_frame(ev)))
    await cdp.send("Page.startScreencast", {"format": "png", "maxWidth": width, "maxHeight": height})
    await page.wait_for_timeout(1000)
    await glide_click(page, page.locator("main button.card", has_text="Signed overflow"))
    await page.wait_for_timeout(1000)
    await glide_click(page, page.get_by_role("button", name="Run"))
    wait_start = time.time() + 0.6  # leave the first moments of the loading state at real speed
    await page.wait_for_selector("text=Compile matrix", timeout=90_000)
    wait_end = time.time()
    await page.wait_for_timeout(2600)
    evidence = page.locator("button", has_text="line ").first
    await glide_click(page, evidence)
    await page.wait_for_timeout(1600)
    await tab(page, "Outputs", glide=True)
    await page.wait_for_timeout(1400)
    await tab(page, "Assembly Diff", glide=True)
    await glide_click(page, page.get_by_role("radio", name="Clang"))
    await page.wait_for_timeout(2400)
    await tab(page, "Verdict", glide=True)
    await page.wait_for_timeout(2000)
    await cdp.send("Page.stopScreencast")
    await page.wait_for_timeout(300)
    end = time.time()
    await page.context.close()

    # Keep at most ~15 fps: a frame shown for less than MIN_MS is dropped and its
    # time given to the frame before it. Then downscale with one shared palette.
    MIN_GAP = 0.066
    kept: list[tuple[float, bytes]] = []  # (start time, png)
    for t, png in frames:
        if kept and (t - kept[-1][0] < MIN_GAP or png == kept[-1][1]):
            continue  # the previously kept frame simply stays on screen longer
        kept.append((t, png))

    def load(png: bytes) -> Image.Image:
        img = Image.open(io.BytesIO(png)).convert("RGB")
        return img.resize((out_width, round(img.height * out_width / img.width)), Image.LANCZOS)

    # The sandbox run itself (often 3-10 s of spinner) is squeezed to ~2.5 s.
    squeeze = min(1.0, 2.5 / max(0.1, wait_end - wait_start))
    rgb = [load(png) for _, png in kept]
    durations = []
    for i, (t, _) in enumerate(kept):
        nxt = kept[i + 1][0] if i + 1 < len(kept) else end
        scale = squeeze if wait_start <= t < wait_end else 1.0
        durations.append(max(20, int((nxt - t) * 1000 * scale)))
    # Build the palette from a strip of sample frames so every colour that appears
    # later (amber verdict, diff reds/greens) is represented from the start.
    samples = rgb[:: max(1, len(rgb) // 10)]
    strip = Image.new("RGB", (out_width, rgb[0].height * len(samples)))
    for k, s in enumerate(samples):
        strip.paste(s, (0, k * rgb[0].height))
    palette = strip.quantize(colors=160, method=Image.Quantize.MEDIANCUT)
    images = [im.quantize(palette=palette, dither=Image.Dither.NONE) for im in rgb]
    images[0].save(
        ASSETS / "demo.gif", save_all=True, append_images=images[1:], duration=durations,
        loop=0, optimize=True, disposal=1,
    )
    size = (ASSETS / "demo.gif").stat().st_size / 1e6
    print(f"demo.gif: {len(images)} frames, {sum(durations) / 1000:.1f}s, {size:.1f} MB")


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://localhost:5173")
    ap.add_argument("--channel", default="chrome", help="installed browser: chrome or msedge")
    ap.add_argument("--only", choices=["screens", "gif"])
    args = ap.parse_args()
    ASSETS.mkdir(parents=True, exist_ok=True)
    async with async_playwright() as p:
        browser = await p.chromium.launch(channel=args.channel)
        if args.only != "gif":
            await screenshots(browser, args.base)
            print("screenshots written to", ASSETS)
        if args.only != "screens":
            await record_gif(browser, args.base)
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
