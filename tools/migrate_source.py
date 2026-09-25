#!/usr/bin/env python3
"""Bounded, read-only source capture and static PRCC site generator."""
from __future__ import annotations

import html
import json
import posixpath
import re
import sys
import time
from collections import deque
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit
from urllib.request import Request, urlopen

ROOT = "https://prccgreensboro.org/"
DOMAIN = "prccgreensboro.org"
MAX_PAGES = 80
MAX_PAGE_BYTES = 2_000_000
MAX_ASSET_BYTES = 6_000_000
MAX_TOTAL_ASSETS = 25_000_000
TIMEOUT = 15
DEST = Path(__file__).resolve().parents[1]


class PageParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.items = []
        self.links = []
        self.images = []
        self.forms = []
        self._active_form = None
        self.title = ""
        self._capture = None
        self._text = []
        self._skip = 0
        self._in_title = False

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in {"script", "style", "noscript", "svg"}:
            self._skip += 1
        if self._skip:
            return
        if tag == "form":
            self.forms.append({"action": a.get("action", ""), "method": a.get("method", "get"), "fields": []})
            self._active_form = self.forms[-1]
        if tag in {"input", "textarea", "select"} and self._active_form is not None:
            self._active_form["fields"].append({"tag": tag, "type": a.get("type", "text"), "name": a.get("name", ""), "required": "required" in a})
        if tag == "title":
            self._in_title = True
        if tag == "a" and a.get("href"):
            self.links.append({"href": a["href"], "label": ""})
            self._anchor = self.links[-1]
        if tag == "img" and a.get("src"):
            self.images.append({"src": a["src"], "alt": a.get("alt", "").strip()})
        if tag in {"h1", "h2", "h3", "h4", "p", "li", "blockquote"}:
            self._capture = tag
            self._text = []

    def handle_endtag(self, tag):
        if tag in {"script", "style", "noscript", "svg"} and self._skip:
            self._skip -= 1
        if self._skip:
            return
        if tag == "form":
            self._active_form = None
        if tag == "title":
            self._in_title = False
        if self._capture == tag:
            text = " ".join("".join(self._text).split())
            if text:
                self.items.append({"type": tag, "text": text[:3000]})
            self._capture = None
            self._text = []
        if tag == "a":
            self._anchor = None

    def handle_data(self, data):
        if self._skip:
            return
        if self._in_title:
            self.title += data
        if self._capture:
            self._text.append(data)
        if getattr(self, "_anchor", None) is not None:
            self._anchor["label"] += data


def canonical(raw, base):
    u = urlsplit(urljoin(base, html.unescape(raw.strip())))
    if u.scheme not in {"http", "https"} or u.hostname not in {DOMAIN, "www." + DOMAIN}:
        return None
    path = re.sub(r"/{2,}", "/", u.path or "/")
    return urlunsplit(("https", DOMAIN, path, "", ""))


def fetch(url, limit):
    req = Request(url, headers={"User-Agent": "PRCC-public-site-reconstruction/1.0"})
    with urlopen(req, timeout=TIMEOUT) as response:
        if "text/html" not in response.headers.get("Content-Type", ""):
            return None, response.status
        body = response.read(limit + 1)
        if len(body) > limit:
            raise ValueError("response exceeded byte ceiling")
        return body.decode(response.headers.get_content_charset() or "utf-8", "replace"), response.status


def slug_for(url):
    p = urlsplit(url).path.strip("/")
    return p or "index"


def esc(v):
    return html.escape(v, quote=True)


def main():
    queue = deque([(ROOT, 0)])
    seen, pages, failures = set(), [], []
    while queue and len(seen) < MAX_PAGES:
        url, depth = queue.popleft()
        if url in seen:
            continue
        seen.add(url)
        try:
            source, status = fetch(url, MAX_PAGE_BYTES)
            if status != 200 or source is None:
                failures.append({"source_url": url, "http_status": status})
                continue
            parser = PageParser()
            parser.feed(source)
            page = {"source_url": url, "slug": slug_for(url), "page_title": " ".join(parser.title.split()), "items": parser.items, "images": [], "links": [], "external_links": [], "forms": parser.forms}
            for im in parser.images:
                asset_url = canonical(im["src"], url)
                page["images"].append({"source_url": urljoin(url, im["src"]), "alt": im["alt"], "local_path": None})
                if asset_url and depth < 3 and len(pages) < MAX_PAGES:
                    queue.append((asset_url, 9))
            for link in parser.links:
                dest = canonical(link["href"], url)
                if dest:
                    page["links"].append({"label": " ".join(link["label"].split()), "source_url": dest})
                    if depth < 2 and not re.search(r"\.(?:pdf|docx?|xlsx?|pptx?|zip|jpe?g|png|gif|webp|svg|mp4)(?:$)", urlsplit(dest).path, re.I):
                        queue.append((dest, depth + 1))
                else:
                    external = urlsplit(urljoin(url, html.unescape(link["href"].strip())))
                    if external.scheme in {"http", "https"} and external.hostname not in {DOMAIN, "www." + DOMAIN, "img1.wsimg.com"}:
                        tracking = {"fbclid", "gclid", "igshid", "mc_cid", "mc_eid", "srsltid"}
                        query = [(key, value) for key, value in parse_qsl(external.query, keep_blank_values=True) if not key.lower().startswith("utm_") and key.lower() not in tracking]
                        page["external_links"].append({"label": " ".join(link["label"].split()), "source_url": urlunsplit((external.scheme, external.netloc, external.path, urlencode(query), ""))})
            pages.append(page)
        except Exception as exc:
            failures.append({"source_url": url, "error": type(exc).__name__})
        time.sleep(0.1)

    # Download bounded first-party images, keeping the source manifest even on failure.
    assets_dir = DEST / "assets"
    assets_dir.mkdir(exist_ok=True)
    total = 0
    asset_map = {}
    for page in pages:
        for image in page["images"]:
            src = image["source_url"]
            if src in asset_map or total >= MAX_TOTAL_ASSETS:
                image["local_path"] = asset_map.get(src)
                continue
            try:
                if urlsplit(src).hostname not in {DOMAIN, "www." + DOMAIN, "img1.wsimg.com"}:
                    raise ValueError("image host outside PRCC and its public image CDN")
                req = Request(src, headers={"User-Agent": "PRCC-public-site-reconstruction/1.0"})
                with urlopen(req, timeout=TIMEOUT) as response:
                    kind = response.headers.get("Content-Type", "")
                    if not kind.startswith("image/"):
                        raise ValueError("not an image")
                    data = response.read(min(MAX_ASSET_BYTES, MAX_TOTAL_ASSETS-total) + 1)
                if len(data) > MAX_ASSET_BYTES or total + len(data) > MAX_TOTAL_ASSETS:
                    raise ValueError("asset byte ceiling")
                suffix = Path(urlsplit(src).path).suffix.lower()
                if suffix not in {".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg"}:
                    suffix = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp", "image/gif": ".gif", "image/svg+xml": ".svg"}.get(kind.split(";")[0], ".img")
                name = f"{len(asset_map)+1:03d}{suffix}"
                (assets_dir / name).write_bytes(data)
                total += len(data)
                asset_map[src] = f"assets/{name}"
                image["local_path"] = asset_map[src]
            except Exception:
                image["local_path"] = None

    # Assign URLs to all captured pages and keep uncaptured first-party links explicit.
    by_source = {p["source_url"]: p for p in pages}
    for page in pages:
        for link in page["links"]:
            target = by_source.get(link["source_url"])
            link["destination_path"] = (target["slug"] + ("/" if target["slug"] != "index" else "")) if target else None
        for image in page["images"]:
            if not image["local_path"]:
                image["external_fallback"] = image["source_url"]
        source_label = next((link["label"] for owner in pages for link in owner["links"] if link["source_url"] == page["source_url"] and link["label"]), None)
        page["navigation_label"] = "Home" if page["slug"] == "index" else source_label or page["page_title"]
        page["destination_path"] = "/prcc-website/" if page["slug"] == "index" else "/prcc-website/" + page["slug"] + "/"
        page["content_status"] = "captured" if page["items"] else "empty"
        page["asset_status"] = "complete" if all(im["local_path"] for im in page["images"]) else "partial" if page["images"] else "none"
        page["link_status"] = "complete" if all(link.get("destination_path") for link in page["links"]) else "partial"
        page["functionality_status"] = "form preview only; approved endpoint required" if page["forms"] else "static page; source outbound links retained"
        page["verification_status"] = "pending local verification"

    (DEST / "content").mkdir(exist_ok=True)
    (DEST / "content" / "source-manifest.json").write_text(json.dumps({"source_root": ROOT, "limits": {"pages": MAX_PAGES, "page_bytes": MAX_PAGE_BYTES, "asset_bytes_each": MAX_ASSET_BYTES, "asset_bytes_total": MAX_TOTAL_ASSETS}, "pages": pages, "failures": failures}, ensure_ascii=False, indent=2), encoding="utf-8")

    nav = []
    nav_seen = set()
    for page in pages:
        if page["slug"] == "index":
            continue
        label = page["page_title"].split("|")[0].strip() or page["slug"].replace("-", " ").title()
        if page["slug"] not in nav_seen:
            nav.append((label, page["slug"]))
            nav_seen.add(page["slug"])
    # Prefer meaningful labels from source navigation links.
    for page in pages:
        for link in page["links"]:
            if link.get("destination_path") and link["destination_path"] != "index/" and link["destination_path"].rstrip("/") not in nav_seen and link["label"]:
                nav.append((link["label"], link["destination_path"].rstrip("/")))
                nav_seen.add(link["destination_path"].rstrip("/"))

    css = """*{box-sizing:border-box}body{margin:0;color:#23302c;background:#f7f5ef;font:17px/1.65 Georgia,serif}a{color:#1e5b4e}a:focus-visible,button:focus-visible{outline:3px solid #c78038;outline-offset:3px}.skip{position:absolute;left:-9999px}.skip:focus{left:1rem;top:1rem;background:white;padding:.7rem;z-index:9}header{background:#193d35;color:white;padding:1rem max(1.2rem,calc((100% - 1100px)/2))}header a{color:white}.brand{font:700 1.4rem Arial,sans-serif;text-decoration:none}.address{font: .95rem Arial,sans-serif;color:#e6ede8}nav{display:flex;gap:.55rem 1.15rem;flex-wrap:wrap;margin-top:1rem}nav a{font:600 .9rem Arial,sans-serif;text-decoration:none}main{max-width:960px;margin:2.5rem auto;padding:0 1.2rem;min-height:65vh}h1,h2,h3{font-family:Arial,sans-serif;line-height:1.2;color:#193d35}h1{font-size:clamp(2rem,5vw,3.3rem)}.hero{background:#e9eee9;padding:2rem;border-radius:4px}.hero img,.photo{max-width:100%;height:auto;border-radius:3px}article{background:white;padding:clamp(1.2rem,4vw,2.5rem);box-shadow:0 8px 30px #193d3510}li{margin:.4rem 0}.gallery{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:1rem}.gallery figure{margin:0}.gallery img{width:100%;height:auto}footer{background:#193d35;color:#f4f6f2;padding:2rem max(1.2rem,calc((100% - 1100px)/2));font: .95rem Arial,sans-serif}footer a{color:white}.notice{background:#fff4d9;border-left:4px solid #c78038;padding:1rem}form{display:grid;gap:.8rem;max-width:34rem}label{font:600 1rem Arial,sans-serif}input,textarea{font:inherit;padding:.65rem;border:1px solid #78857e;border-radius:2px}button{font:600 1rem Arial,sans-serif;padding:.75rem 1rem;background:#1e5b4e;color:white;border:0;border-radius:2px}@media(max-width:600px){header{padding:1rem}nav{gap:.6rem}main{margin:1.2rem auto}.hero{padding:1rem}}"""
    (DEST / "styles.css").write_text(css, encoding="utf-8")
    forms_detected = any("form" in p["source_url"] for p in pages)
    for page in pages:
        path = page["slug"]
        folder = DEST if path == "index" else DEST / path
        folder.mkdir(parents=True, exist_ok=True)
        depth = 0 if path == "index" else len(Path(path).parts)
        up = "../" * depth
        links = []
        for label, target in nav:
            rel = posixpath.relpath(("index.html" if target == "index" else target + "/"), path if path != "index" else ".")
            if target != "index":
                rel = rel.rstrip("/") + "/"
            links.append(f'<a href="{esc(rel)}">{esc(label)}</a>')
        body = []
        for item in page["items"]:
            t, text = item["type"], esc(item["text"])
            if t == "li" and html.unescape(item["text"]).strip().casefold() in {label.casefold() for label, _ in nav}:
                continue
            if t == "h1":
                continue
            if t.startswith("h"):
                body.append(f"<{t}>{text}</{t}>")
            elif t == "li":
                body.append(f"<li>{text}</li>")
            elif t == "blockquote":
                body.append(f"<blockquote>{text}</blockquote>")
            else:
                body.append(f"<p>{text}</p>")
        imgs = []
        for im in page["images"]:
            src = im["local_path"] or im.get("external_fallback")
            if src:
                imgs.append(f'<figure><img class="photo" src="{esc(up + src if im["local_path"] else src)}" alt="{esc(im["alt"] or "Photo from " + (page["page_title"] or "Pleasant Ridge Christian Church"))}" loading="lazy"></figure>')
        form_ui = ""
        if page["forms"]:
            form_ui = '<section class="notice" aria-labelledby="form-note"><h2 id="form-note">Message form preview</h2><p>This form is a preview only and does not send messages. The church must connect and approve its submission service before this site can accept requests.</p><form><label for="name">Name</label><input id="name" name="name" autocomplete="name"><label for="email">Email</label><input id="email" name="email" type="email" autocomplete="email"><label for="message">Message</label><textarea id="message" name="message" rows="5"></textarea><button type="button" disabled>Submissions unavailable</button></form></section>'
        external_items = []
        external_seen = set()
        for item in page["external_links"]:
            if item["source_url"] in external_seen:
                continue
            external_seen.add(item["source_url"])
            label = item["label"] or urlsplit(item["source_url"]).hostname
            external_items.append(f'<li><a href="{esc(item["source_url"])}" target="_blank" rel="noopener noreferrer">{esc(label)}</a></li>')
        external_html = (f'<section aria-labelledby="related-links"><h2 id="related-links">Related links</h2><ul>{"".join(external_items)}</ul></section>' if external_items else "")
        title = page["page_title"] or page["slug"].replace("-", " ").title()
        output = f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="description" content="Pleasant Ridge Christian Church in Greensboro, North Carolina"><title>{esc(title)}</title><link rel="icon" type="image/svg+xml" href="{up}favicon.svg"><link rel="stylesheet" href="{up}styles.css"></head><body><a class="skip" href="#main">Skip to content</a><header><a class="brand" href="{up}index.html">Pleasant Ridge Christian Church</a><div class="address">2049 Pleasant Ridge Road · Greensboro, North Carolina</div><nav aria-label="Main navigation">{''.join(links)}</nav></header><main id="main"><article><h1>{esc(title)}</h1>{''.join(imgs)}{''.join(body)}{external_html}{form_ui}</article></main><footer><p>Sunday worship at 9 a.m. · Everyone is welcome.</p><p><a href="{up}index.html">Home</a> · Source: <a href="{esc(page['source_url'])}">original PRCC page</a></p></footer></body></html>'''
        (folder / "index.html").write_text(output, encoding="utf-8")
    (DEST / "README.md").write_text("""# Pleasant Ridge Christian Church

Independent static reconstruction for GitHub Pages at `/prcc-website/`.

## Local development and verification

Run `python -m http.server 8000` from this directory and open `http://localhost:8000/`. Run `python tools/verify_site.py` to check the captured pages, local links, assets, required manifest fields, and repository-path safety.

## Content and assets

`content/source-manifest.json` keeps source URLs, navigation labels, destination routes, status fields, forms, and image provenance separate from the presentation templates. `python tools/migrate_source.py` refreshes the manifest, pages, and public images from the PRCC site with a maximum of 80 pages, a 2 MB page limit, and a 25 MB total image limit. The source navigation and sitemap currently list the same 16 pages. Generated HTML is refreshed from the public source; update the generator when a deliberate presentation or content correction must survive a refresh. No GoDaddy platform code is used.

## Forms

Contact, prayer, and “Find Peace in Christ” controls are presentational and cannot submit data. A church-approved recipient and submission service are required before enabling them.

## Deployment

`.github/workflows/pages.yml` publishes the repository root to GitHub Pages after a commit reaches `main` or a manual workflow dispatch. Repository write and Pages workflow access are required. No custom domain is configured, and the existing PRCC production website and DNS remain untouched. See `docs/future-domain-migration.md` for the separately approved future migration procedure.
""", encoding="utf-8")
    (DEST / ".gitignore").write_text("__pycache__/\n*.pyc\n.DS_Store\n", encoding="utf-8")
    print(json.dumps({"pages_captured": len(pages), "failures": len(failures), "assets_downloaded": len(asset_map), "asset_bytes": total, "source_forms_visible": any(bool(p["forms"]) for p in pages), "target": "local project directory"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
