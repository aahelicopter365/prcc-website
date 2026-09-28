#!/usr/bin/env python3
"""Render captured PRCC route content and locally mirrored images with the shared site shell."""
from __future__ import annotations
import html, json, re, urllib.parse
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NAV = [
    ("Home", "index.html"), ("Weekly Update", "weekly-update/"),
    ("Small Groups", "small-groups/"), ("Children and Youth", "children-and-youth/"),
    ("Prayer", "prayer/"), ("Find Peace in Christ", "find-peace-in-christ/"),
    ("Online Giving", "online-giving/"), ("Sermons", "sermons/"),
    ("Event Calendar", "event-calendar/"), ("Event Recap", "event-recap/"),
]
ABOUT = [("Contact Us", "contact-us/"), ("Ministry Staff", "ministry-staff/"),
         ("Core Values", "core-values/"), ("Missions", "missions/"),
         ("Church History", "church-history/"), ("FAQs", "faqs/")]
NAV_TEXT = {x.casefold() for x, _ in NAV + ABOUT}
NAV_TEXT.add("about")


def esc(value: str) -> str:
    return html.escape(value, quote=True)


def file_name(url: str) -> str:
    path = urllib.parse.unquote(urllib.parse.urlsplit(url).path.split("/:")[0])
    return path.rsplit("/", 1)[-1]


def content_for(page: dict) -> tuple[str, list[dict]]:
    title = ""
    content = []
    seen = set()
    for item in page.get("items", []):
        tag = item.get("type", "p").lower()
        text = " ".join(item.get("text", "").split())
        if not text or text.casefold() in NAV_TEXT or text in {"Powered by"} or text.startswith("Copyright"):
            continue
        if tag == "h1" and not title:
            title = text
            continue
        if tag == "h1":
            continue
        if "This site is protected by reCAPTCHA" in text:
            continue
        key = (tag, text.casefold())
        if key in seen:
            continue
        # The original capture can retain a shortened lazy/hidden copy before its full text.
        shorter = next((i for i, old in enumerate(content) if old["tag"] == tag and len(text) > len(old["text"]) and text.startswith(old["text"][:min(90, len(old["text"]))])), None)
        if shorter is not None:
            content[shorter] = {"tag": tag, "text": text}
            seen.add(key)
            continue
        seen.add(key)
        content.append({"tag": tag, "text": text})
    return title or page.get("page_title") or page["slug"].replace("-", " ").title(), content


def groups_for(content: list[dict]) -> list[dict]:
    groups = [{"heading": None, "items": [], "images": []}]
    for item in content:
        if item["tag"] in {"h2", "h3", "h4"} and groups[-1]["items"]:
            groups.append({"heading": None, "items": [], "images": []})
        if item["tag"] in {"h2", "h3", "h4"}:
            groups[-1]["heading"] = item
        else:
            groups[-1]["items"].append(item)
    return [g for g in groups if g["heading"] or g["items"]]


def image_records(slug: str, inventory: dict, local: dict) -> list[dict]:
    page = next((p for p in inventory["pages"] if p["route"] == slug), None)
    if not page:
        return []
    result = []
    for image in page.get("images", []):
        if image.get("aid", "").startswith("HEADER_"):
            continue
        name = file_name(image.get("src", ""))
        if not name or name.casefold().startswith("spotlight-poi"):
            continue
        path = local.get(name.casefold())
        if not path:
            continue
        result.append({"path": path, "alt": image.get("alt") or name.rsplit(".", 1)[0].replace("_", " ").replace("-", " ")})
    return result


def linkify(text: str) -> str:
    safe = esc(text)
    if re.fullmatch(r"https?://[^\s]+", text):
        return f'<a href="{esc(text)}" target="_blank" rel="noopener noreferrer">{safe}</a>'
    return safe


def render_group(group: dict, slug: str, up: str) -> str:
    items = group["items"]
    images = group["images"]
    title = group["heading"]
    inner = []
    if title:
        tag = title["tag"] if title["tag"] in {"h2", "h3", "h4"} else "h2"
        inner.append(f'<{tag}>{esc(title["text"])}</{tag}>')
    text_html = []
    in_list = False
    for item in items:
        tag, text = item["tag"], item["text"]
        if tag == "li":
            if not in_list:
                text_html.append("<ul>"); in_list = True
            text_html.append(f"<li>{linkify(text)}</li>")
        else:
            if in_list:
                text_html.append("</ul>"); in_list = False
            if tag == "blockquote":
                text_html.append(f"<blockquote>{linkify(text)}</blockquote>")
            elif tag == "p":
                text_html.append(f"<p>{linkify(text)}</p>")
            else:
                text_html.append(f"<p>{linkify(text)}</p>")
    if in_list:
        text_html.append("</ul>")
    gallery = ""
    if images:
        gallery = '<div class="page-gallery">' + "".join(
            f'<figure><img src="{up}{esc(img["path"])}" alt="{esc(img["alt"])}" loading="lazy"></figure>' for img in images
        ) + "</div>"
    if len(images) == 1:
        return f'<section class="page-section media-section"><div class="section-copy">{"".join(inner)}{"".join(text_html)}</div><figure class="section-photo"><img src="{up}{esc(images[0]["path"])}" alt="{esc(images[0]["alt"])}" loading="lazy"></figure></section>'
    return f'<section class="page-section">{"".join(inner)}{"".join(text_html)}{gallery}</section>'


def nav_markup(up: str) -> str:
    def link(label, path):
        href = up + path
        return f'<a href="{esc(href)}">{esc(label)}</a>'
    about_links = "".join(link(label, path) for label, path in ABOUT)
    more_items = [("Find Peace in Christ", "find-peace-in-christ/"), ("Online Giving", "online-giving/"), ("Sermons", "sermons/"), ("Event Calendar", "event-calendar/"), ("Event Recap", "event-recap/")]
    more_links = "".join(link(label, path) for label, path in more_items)
    desktop = f'<nav class="desktop-nav" aria-label="Main navigation">{link("Home", "index.html")}<details><summary>About <span aria-hidden="true">⌄</span></summary><div class="menu-panel">{about_links}</div></details>{link("Weekly Update","weekly-update/")}{link("Small Groups","small-groups/")}{link("Children and Youth","children-and-youth/")}{link("Prayer","prayer/")}<details><summary>More <span aria-hidden="true">⌄</span></summary><div class="menu-panel">{more_links}</div></details></nav>'
    mobile = f'<div class="mobile-menu"><details><summary aria-label="Open navigation"><span></span><span></span><span></span></summary><nav aria-label="Main navigation">{link("Home","index.html")}<details><summary>About</summary>{about_links}</details>{link("Weekly Update","weekly-update/")}{link("Small Groups","small-groups/")}{link("Children and Youth","children-and-youth/")}{link("Prayer","prayer/")}<details><summary>More</summary>{more_links}</details></nav></details></div>'
    return f'<header class="site-header">{mobile}<a class="site-logo" href="{up}index.html" aria-label="Pleasant Ridge Christian Church home"><img src="{up}assets/001.png" width="100" height="100" alt="Pleasant Ridge Christian Church"></a>{desktop}</header>'


def main():
    manifest = json.load(open(ROOT / "content/source-manifest.json", encoding="utf-8"))
    inventory = json.load(open(ROOT / "content/production-image-inventory.json", encoding="utf-8"))
    prod = json.load(open(ROOT / "content/production-assets.json", encoding="utf-8"))
    local = {}
    for page in manifest["pages"]:
        for im in page.get("images", []):
            if im.get("local_path"):
                local[file_name(im.get("source_url", "")).casefold()] = im["local_path"]
    for im in prod["assets"]:
        if im.get("local_path"):
            local[im["source_name"].casefold()] = im["local_path"]
    counts = []
    for page in manifest["pages"]:
        slug = page["slug"]
        if slug == "index":
            continue
        folder = ROOT / slug
        folder.mkdir(parents=True, exist_ok=True)
        up = "../"
        title, content = content_for(page)
        groups = groups_for(content)
        images = image_records(slug, inventory, local)
        if groups and images:
            # Distribute the observed source images across actual heading groups in source order.
            for i, image in enumerate(images):
                groups[min(i, len(groups)-1)]["images"].append(image)
        sections = "".join(render_group(g, slug, up) for g in groups)
        source_links=[]
        seen=set()
        for link in page.get("external_links", []):
            url=link.get("source_url","")
            if not url or url in seen: continue
            seen.add(url); label=link.get("label") or urllib.parse.urlsplit(url).hostname or url
            source_links.append(f'<li><a href="{esc(url)}" target="_blank" rel="noopener noreferrer">{esc(label)}</a></li>')
        links_html=f'<section class="page-section external-links"><h2>Connect with us</h2><ul>{"".join(source_links)}</ul></section>' if source_links else ""
        forms = ""
        if page.get("forms"):
            forms = '<section class="page-section form-preview"><h2>Request form preview</h2><p>This staging copy does not send submissions.</p><form onsubmit="return false"><label>Name<input name="name" autocomplete="name"></label><label>Email<input name="email" type="email" autocomplete="email"></label><label>Message<textarea name="message" rows="5"></textarea></label><button type="button" disabled>Submissions unavailable</button></form></section>'
        output=f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="description" content="{esc(title)} — Pleasant Ridge Christian Church in Greensboro, North Carolina"><title>{esc(title)} | Pleasant Ridge Christian Church</title><link rel="icon" type="image/svg+xml" href="{up}favicon.svg"><link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin><link href="https://fonts.googleapis.com/css2?family=Adamina&family=Poppins:wght@400;500;600;700&display=swap" rel="stylesheet"><link rel="stylesheet" href="{up}pages.css"></head><body class="page-{esc(slug)}"><a class="skip" href="#main">Skip to content</a>{nav_markup(up)}<main id="main" class="page-main"><div class="page-heading"><h1>{esc(title)}</h1></div><article>{sections}{links_html}{forms}</article></main><footer class="page-footer"><small>Copyright © 2026 Pleasant Ridge Christian Church · All rights reserved.</small><a href="https://www.facebook.com/profile.php?id=100089013843748" aria-label="Facebook">f</a><small>Powered by GoDaddy</small></footer></body></html>'''
        (folder/"index.html").write_text(output,encoding="utf-8")
        counts.append({"route":"/"+slug+"/","content_blocks":len(content),"images":len(images),"groups":len(groups),"safe_form_preview":bool(forms)})
    print(json.dumps({"pages_rendered":len(counts),"routes":counts},indent=2,ensure_ascii=False))

if __name__ == "__main__": main()