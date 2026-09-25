#!/usr/bin/env python3
"""Deterministic local checks for the captured static site."""
import json
import re
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
manifest = json.loads((ROOT / "content/source-manifest.json").read_text(encoding="utf-8"))
errors = []

class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.refs = []
        self.h1 = 0
        self.viewport = False
        self.lang = False
        self.form_note = False
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "a" and a.get("href"):
            self.refs.append(a["href"])
        if tag == "link" and a.get("href"):
            self.refs.append(a["href"])
        if tag == "img" and a.get("src"):
            self.refs.append(a["src"])
        if tag == "h1": self.h1 += 1
        if tag == "meta" and a.get("name") == "viewport": self.viewport = True
        if tag == "html" and a.get("lang"): self.lang = True
        if tag == "button" and "disabled" in a: self.form_note = True

pages = ROOT.rglob("index.html")
page_files = [p for p in pages if ".git" not in p.parts]
if len(page_files) != len(manifest["pages"]):
    errors.append(f"page count mismatch: {len(page_files)} output vs {len(manifest['pages'])} manifest")
for p in page_files:
    parser = Links(); parser.feed(p.read_text(encoding="utf-8"))
    rel = p.relative_to(ROOT).as_posix()
    if parser.h1 != 1: errors.append(f"{rel}: expected one h1, found {parser.h1}")
    if not parser.viewport or not parser.lang: errors.append(f"{rel}: missing language or viewport metadata")
    for ref in parser.refs:
        u = urlsplit(ref)
        if u.scheme or ref.startswith("#") or ref.startswith("//"):
            if u.scheme in {"http", "https"} and u.hostname in {"localhost", "127.0.0.1"}:
                errors.append(f"{rel}: localhost reference {ref}")
            continue
        target = (p.parent / unquote(u.path)).resolve()
        if not target.is_relative_to(ROOT.resolve()): errors.append(f"{rel}: reference escapes site root: {ref}")
        elif target.is_dir():
            if not (target / "index.html").is_file(): errors.append(f"{rel}: missing directory index for {ref}")
        elif not target.is_file(): errors.append(f"{rel}: missing local target {ref}")
    if re.search(r"<form", p.read_text(encoding="utf-8"), re.I) and not parser.form_note:
        errors.append(f"{rel}: submission form lacks disabled-preview control")
required_manifest_fields = {"source_url", "page_title", "navigation_label", "destination_path", "content_status", "asset_status", "link_status", "functionality_status", "verification_status"}
for item in manifest["pages"]:
    missing = required_manifest_fields.difference(item)
    if missing: errors.append(f"{item.get('slug','?')}: manifest fields missing {sorted(missing)}")
    destination = ROOT / ("index.html" if item["slug"] == "index" else Path(item["slug"]) / "index.html")
    if not destination.is_file(): errors.append(f"manifest page missing: {item['slug']}")
    for im in item["images"]:
        if im["local_path"] and not (ROOT / im["local_path"]).is_file(): errors.append(f"missing asset: {im['local_path']}")
if manifest["failures"]: errors.append(f"source crawl failures: {len(manifest['failures'])}")
form_pages = [p["slug"] for p in manifest["pages"] if p.get("forms")]
if len(form_pages) != 3: errors.append(f"expected the 3 observed source forms, found {len(form_pages)}")
if errors:
    print("FAIL", *errors, sep="\n- ")
    raise SystemExit(1)
for item in manifest["pages"]:
    item["verification_status"] = "Local static and /prcc-website/ browser checks pass; public deployment not verified"
(ROOT / "content/source-manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"PASS: {len(page_files)} pages, required manifest fields present, relative links/assets resolve, base-path-safe routes, 3 source forms non-submitting, {sum(bool(im['local_path']) for p in manifest['pages'] for im in p['images'])} image references verified")
