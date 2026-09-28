"""Capture comparable production and staging screenshots for the PRCC route inventory."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.parse import urljoin

from PIL import Image, ImageChops, ImageStat
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import sync_playwright


ROUTES = [
    ("home", "/"),
    ("contact-us", "/contact-us/"),
    ("ministry-staff", "/ministry-staff/"),
    ("core-values", "/core-values/"),
    ("missions", "/missions/"),
    ("church-history", "/church-history/"),
    ("faqs", "/faqs/"),
    ("weekly-update", "/weekly-update/"),
    ("small-groups", "/small-groups/"),
    ("children-and-youth", "/children-and-youth/"),
    ("prayer", "/prayer/"),
    ("find-peace-in-christ", "/find-peace-in-christ/"),
    ("online-giving", "/online-giving/"),
    ("sermons", "/sermons/"),
    ("event-calendar", "/event-calendar/"),
    ("event-recap", "/event-recap/"),
]
VIEWPORTS = [("1920x1080", 1920, 1080), ("1440x900", 1440, 900),
             ("1366x768", 1366, 768), ("390x844", 390, 844),
             ("430x932", 430, 932)]


def capture(browser, base: str, route: str, width: int, height: int, output: Path) -> dict:
    page = browser.new_page(viewport={"width": width, "height": height}, device_scale_factor=1)
    errors: list[str] = []
    page.on("pageerror", lambda _: errors.append("javascript_error"))
    response = None
    for attempt in range(2):
        try:
            response = page.goto(urljoin(base.rstrip("/") + "/", route.lstrip("/")),
                                 wait_until="commit", timeout=30000)
            break
        except PlaywrightError:
            if attempt == 1:
                page.close()
                raise
    page.evaluate("""async () => {
      await Promise.race([document.fonts.ready, new Promise(r => setTimeout(r, 5000))]);
      const step = Math.max(400, Math.floor(innerHeight * .8));
      for (let y = 0, limit = Math.min(document.body.scrollHeight, 300000); y < limit; y += step) {
        scrollTo(0, y);
        await new Promise(r => setTimeout(r, 60));
      }
      scrollTo(0, 0);
    }""")
    page.wait_for_timeout(500)
    page.screenshot(path=str(output), type="jpeg", quality=90, full_page=True)
    details = page.evaluate("""() => ({
      title: document.title,
      h1_count: document.querySelectorAll('h1').length,
      width: document.documentElement.scrollWidth,
      height: document.body.scrollHeight,
      broken_images: [...document.images].filter(i => !i.complete || !i.naturalWidth).length,
      internal_links: [...document.links].filter(a => {
        try { return new URL(a.href).origin === location.origin; } catch { return false; }
      }).length,
      external_links: [...document.links].filter(a => {
        try { return new URL(a.href).origin !== location.origin; } catch { return false; }
      }).length
    })""")
    result = {"status": response.status if response else None, **details,
              "page_errors": len(errors), "screenshot": str(output)}
    page.close()
    return result


def image_delta(left: Path, right: Path) -> dict:
    with Image.open(left) as a, Image.open(right) as b:
        a, b = a.convert("RGB"), b.convert("RGB")
        sample_width = 720
        ah = max(1, round(a.height * sample_width / a.width))
        bh = max(1, round(b.height * sample_width / b.width))
        a = a.resize((sample_width, ah), Image.Resampling.BILINEAR)
        b = b.resize((sample_width, bh), Image.Resampling.BILINEAR)
        common_height = min(ah, bh, 18000)
        a, b = a.crop((0, 0, sample_width, common_height)), b.crop((0, 0, sample_width, common_height))
        diff = ImageChops.difference(a, b)
        mean = sum(ImageStat.Stat(diff).mean) / 3
        thresholded = diff.convert("L").point(lambda pixel: 255 if pixel > 32 else 0)
        changed = thresholded.histogram()[255]
        return {"sample_mean_absolute_difference_0_255": round(mean, 2),
                "sample_pixels_over_32_percent": round(100 * changed / (sample_width * common_height), 2),
                "sample_common_height": common_height}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--production", default="https://prccgreensboro.org/")
    parser.add_argument("--staging", default="http://127.0.0.1:8765/")
    parser.add_argument("--output", type=Path, default=Path("../prcc-visual-evidence/mission-final-20260928"))
    parser.add_argument("--offline-reference-dir", type=Path,
                        help="use saved production screenshots and capture local staging only")
    parser.add_argument("--fresh", action="store_true", help="recapture existing route/viewport screenshots")
    args = parser.parse_args()
    source_dir, stage_dir = args.output / "production", args.output / "staging"
    source_dir.mkdir(parents=True, exist_ok=True)
    stage_dir.mkdir(parents=True, exist_ok=True)
    report_path = args.output / "visual-audit.json"
    progress_path = args.output / "visual-audit.progress.json"
    rows = []
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge", headless=True)
        for slug, route in ROUTES:
            for viewport, width, height in VIEWPORTS:
                source_path = source_dir / f"{slug}-{viewport}.jpg"
                stage_path = stage_dir / f"{slug}-{viewport}.jpg"
                reference_path = source_path
                if args.offline_reference_dir:
                    fallback = None
                    if (width, height) == (1440, 900):
                        fallback = args.offline_reference_dir / f"live-{slug}-desktop.png"
                    elif (width, height) == (390, 844):
                        fallback = args.offline_reference_dir / f"live-{slug}-mobile.png"
                    if not source_path.exists() and fallback and fallback.exists():
                        reference_path = fallback
                    source = None
                    if source_path.exists() or (fallback and fallback.exists()):
                        with Image.open(reference_path if source_path.exists() else fallback) as image:
                            ref = reference_path if source_path.exists() else fallback
                            source = {"status": "saved_reference", "width": image.width,
                                      "height": image.height, "screenshot": str(ref)}
                    stage = capture(browser, args.staging, route, width, height, stage_path)
                else:
                    cached = not args.fresh and source_path.exists() and stage_path.exists()
                    if cached:
                        with Image.open(source_path) as image:
                            source = {"status": 200, "width": image.width, "height": image.height,
                                      "screenshot": str(source_path), "cached_previous_capture": True}
                        with Image.open(stage_path) as image:
                            stage = {"status": 200, "width": image.width, "height": image.height,
                                     "screenshot": str(stage_path), "cached_previous_capture": True}
                    else:
                        try:
                            source = capture(browser, args.production, route, width, height, source_path)
                        except PlaywrightError:
                            source = {"status": None, "capture_error": "production_navigation_timeout"}
                        try:
                            stage = capture(browser, args.staging, route, width, height, stage_path)
                        except PlaywrightError:
                            stage = {"status": None, "capture_error": "staging_navigation_timeout"}
                    reference_path = source_path
                comparison = image_delta(reference_path if source else source_path, stage_path) if source and stage_path.exists() else None
                rows.append({"route": route, "slug": slug, "viewport": viewport,
                             "production": source, "staging": stage,
                             "comparison": comparison})
                partial = {"production_base": args.production, "staging_base": args.staging,
                           "routes": len(ROUTES), "viewports": [v[0] for v in VIEWPORTS], "results": rows}
                progress_path.write_text(json.dumps(partial, indent=2), encoding="utf-8")
                mae = comparison["sample_mean_absolute_difference_0_255"] if comparison else "unavailable"
                print(f"{route} {viewport}: source={source.get('status') if source else None} stage={stage.get('status')} "
                      f"MAE={mae}", flush=True)
        browser.close()
    report = {"production_base": args.production, "staging_base": args.staging,
              "routes": len(ROUTES), "viewports": [v[0] for v in VIEWPORTS], "results": rows}
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    progress_path.unlink(missing_ok=True)
    print(f"Wrote {report_path}")


if __name__ == "__main__":
    main()
