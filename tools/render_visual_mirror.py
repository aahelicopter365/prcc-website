#!/usr/bin/env python3
"""Render captured PRCC route content and locally mirrored images with the shared site shell."""
from __future__ import annotations
import html, json, re, urllib.parse
from collections import defaultdict
from pathlib import Path
import sys

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
                if text.isupper() or text.casefold().startswith("we use two candles"):
                    text_html.append(f"<p><strong>{linkify(text)}</strong></p>")
                else:
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


def image_tag(path: str, alt: str, up: str = "../") -> str:
    return f'<img src="{up}{esc(path)}" alt="{esc(alt)}" loading="eager">'


def render_contact_page() -> str:
    hours = [
        ("Sunday:", "Worship Service: 9 a.m."),
        ('Children\'s "Sonshine" Ministry:', "During Service"),
        ("Fellowship:", "10-10:30"),
        ("Small Groups:", "10:30-11:30"),
        ("Children's Sunday School:", "10:30-11:30"),
        ("Youth Sunday School:", "10:30-11:30"),
    ]
    hours_html = "".join(f'<p><strong>{esc(label)}</strong> {esc(value)}</p>' for label, value in hours)
    directions = 'https://www.google.com/maps/search/?api=1&amp;query=2049+Pleasant+Ridge+Road%2C+Greensboro%2C+NC+27410'
    address = "2049 Pleasant Ridge Road, Greensboro, NC 27410"
    maps_embed = "https://www.google.com/maps?q=2049+Pleasant+Ridge+Road%2C+Greensboro%2C+NC+27410&amp;output=embed"
    return f'''<section class="contact-main"><div class="contact-content"><div class="contact-form-column"><h1>We would love to hear from you</h1><h2>Pastor: Rev Doreen Gibbons</h2><form class="local-preview-form" data-integration="activity-accounts:prcc-contact" data-submission-state="not-connected"><label>Name<input name="name" autocomplete="name"></label><label>Email*<input name="email" type="email" autocomplete="email" required></label><label class="contact-message"><span class="contact-helper">How can we help you with your faith?</span><span class="visually-hidden">Message</span><textarea name="message" placeholder="Tell us about your faith journey" rows="5" required></textarea></label><button type="submit">Preview message</button><p class="submission-note" aria-live="polite">This preview validates locally and does not send messages.</p></form></div><div class="contact-details"><h2>Pleasant Ridge Christian Church</h2><p>{address}</p><p><a href="tel:3366682290">336-668-2290</a></p><h3>Hours</h3>{hours_html}</div></div></section><section class="contact-map" aria-label="Map to Pleasant Ridge Christian Church"><iframe title="Map to Pleasant Ridge Christian Church, 2049 Pleasant Ridge Road" src="{maps_embed}" loading="lazy" referrerpolicy="no-referrer-when-downgrade" allowfullscreen></iframe><a class="contact-directions" href="{directions}" target="_blank" rel="noopener noreferrer">➤&nbsp; Get Directions</a></section><section class="contact-social"><h2>Connect with us</h2><a class="facebook-link" href="https://www.facebook.com/profile.php?id=100089013843748" target="_blank" rel="noopener noreferrer" aria-label="Facebook"><svg aria-hidden="true" viewBox="0 0 24 24"><path d="M13.4 21v-8h2.7l.4-3.1h-3.1v-2c0-.9.3-1.5 1.6-1.5h1.7V3.6c-.3 0-1.3-.1-2.4-.1-2.4 0-4.1 1.5-4.1 4.2v2.3H7.5v3.1h2.7v8z"/></svg></a></section>'''


def render_faq_page(content: list[dict]) -> str:
    answers = [item["text"] for item in content if item["tag"] == "p"]
    intro, answers = answers[0], answers[1:]
    questions = [
        "What are the service times at Pleasant Ridge Christian Church?",
        "What denomination is Pleasant Ridge Christian Church?",
        "What types of ministries does Pleasant Ridge Christian Church offer?",
        "How long are the services?",
        "Is there a dress code for attending services at Pleasant Ridge Christian Church?",
    ]
    def answer_html(answer: str) -> str:
        escaped = esc(answer)
        return re.sub(r"https?://[^\s]+", lambda match: f'<a href="{match.group(0)}" target="_blank" rel="noopener noreferrer">{match.group(0)}</a>', escaped)
    rows = "".join(
        f'<details class="faq-row"><summary>{esc(question)}</summary><div>{answer_html(answer)}</div></details>'
        for question, answer in zip(questions, answers)
    )
    contact = esc(intro).replace("prcc2049@gmail.com", '<a href="mailto:prcc2049@gmail.com">prcc2049@gmail.com</a>')
    return f'<section class="faq-content"><h1>Frequently Asked Questions</h1><p>{contact}</p><div class="faq-accordion">{rows}</div></section>'


def render_calendar_page(groups: list[dict]) -> str:
    quote = next((item["text"] for group in groups for item in group["items"] if item["tag"] == "p"), "")
    return f'''<section class="calendar-hero">{image_tag("assets/021.jpg", "Family standing together before a cross at sunset.")}<blockquote>{esc(quote)}</blockquote></section><section class="calendar-list"><div class="calendar-row"><h2>All of 2026</h2><div><h3>Food Collection for Greensboro Urban Ministries</h3><p>2026 Goal: 1,000 Lbs.</p><p>Current Total: 825 Lbs.</p></div><span>PRCC</span></div><div class="calendar-row"><h2>Ongoing</h2><div><h3>Collecting Bibles for 7Homes</h3><p>We continue to collect Bibles for the kids that come to Seven Homes. They are in need of Spanish Bibles ($12.99) and Explorer Bibles.</p></div><span>PRCC</span></div><div class="calendar-row"><h2>Ongoing</h2><div><h3>Fall/Winter Clothing Drive</h3><p>We are continuing to collect clothes for the homeless to be donated to the “Church Under the Bridge” homeless ministry.</p></div><span>PRCC</span></div></section>'''


def render_sermons_page() -> str:
    sermons = [
        ("9-27-26 Soar Like an Eagle", "Isaiah 40:21-31", ""),
        ("9-20-26 The Lord Is My Shepherd", "Psalm 23", ""),
        ("9-13-26 God Always Had a Plan for Joseph", "Genesis 50:15-21", ""),
        ("9-6-26 God Guides Joseph to Reconcile and Forgive", "Genesis 45:1-8", ""),
        ("8-30-26 God Guides Joseph to Freedom", "Genesis 41:1-43", ""),
        ("8-23-26 God Is with Joseph When Waiting", "Genesis 40:1-23", ""),
        ("8-16-26 God Is with Joseph When Suffering", "Genesis 39:1-23", ""),
    ]
    entries = []
    for index, (title, passage, video) in enumerate(sermons):
        player = f'<div class="sermon-player"><iframe src="{video}?title=0&amp;byline=0&amp;portrait=0" title="{esc(title)} sermon video" loading="lazy" allow="autoplay; fullscreen; picture-in-picture" allowfullscreen></iframe></div>' if video else ''
        heading = "h1" if not entries else "h2"
        entries.append(f'<section class="sermon-entry"><div class="sermon-copy"><{heading}>{esc(title)}</{heading}><p>{esc(passage)}</p></div>{player}</section>')
    return "".join(entries)


def render_recap_page(images: list[dict], up: str) -> str:
    playground = [f'assets/{name}.jpg' for name in ("022", "023", "024", "025", "026", "027")]
    used = set(playground)
    vbs = []
    for image in images:
        path = image["path"]
        if path.startswith("assets/production/") and path not in used:
            used.add(path)
            vbs.append(path)
    first = "".join(f'<figure>{image_tag(path, "Kids playscape rebuilding project.", up)}</figure>' for path in playground)
    feature_paths = vbs
    gallery = "".join(f'<figure data-slide="{i}">{image_tag(path, "Vacation Bible School community photo.", up)}</figure>' for i, path in enumerate(feature_paths))
    thumbs = "".join(f'<button type="button" data-slide="{i}" aria-label="Show Vacation Bible School photo {i+1}" aria-current="false">{image_tag(path, "", up)}</button>' for i, path in enumerate(feature_paths))
    controls = '<div class="carousel-controls"><button type="button" data-carousel-step="-1" aria-label="Previous Vacation Bible School photo">‹</button><button type="button" data-carousel-step="1" aria-label="Next Vacation Bible School photo">›</button></div>'
    script = '''<script>document.querySelectorAll(".recap-vbs").forEach(section=>{const slides=[...section.querySelectorAll(".recap-vbs-feature figure")],feature=section.querySelector(".recap-vbs-feature"),buttons=[...section.querySelectorAll(".recap-thumbnails button")],steps=[...section.querySelectorAll("[data-carousel-step]")];let selected=0,startX=null,timer;function select(index){selected=(index+slides.length)%slides.length;const start=(selected-1+slides.length)%slides.length;slides.forEach((slide,i)=>{const slot=(i-start+slides.length)%slides.length;slide.hidden=slot>2;slide.style.order=slot;slide.dataset.position=slot===1?"active":slot===0?"previous":"next"});buttons.forEach((button,i)=>button.setAttribute("aria-current",String(i===selected)));}function resume(){clearInterval(timer);timer=setTimeout(()=>{clearInterval(timer);timer=setInterval(()=>select(selected+1),6000)},12000)}function pause(){clearInterval(timer)}buttons.forEach((button,i)=>button.addEventListener("click",()=>{select(i);resume()}));steps.forEach(button=>button.addEventListener("click",()=>{select(selected+Number(button.dataset.carouselStep));resume()}));feature.addEventListener("mouseenter",pause);feature.addEventListener("mouseleave",()=>timer=setInterval(()=>select(selected+1),6000));feature.addEventListener("focusin",pause);feature.addEventListener("focusout",event=>{if(!feature.contains(event.relatedTarget))timer=setInterval(()=>select(selected+1),6000)});feature.addEventListener("touchstart",event=>{startX=event.changedTouches[0].clientX;pause()},{passive:true});feature.addEventListener("touchend",event=>{if(startX===null)return;const delta=event.changedTouches[0].clientX-startX;if(Math.abs(delta)>35){select(selected+(delta<0?1:-1));resume()}startX=null},{passive:true});select(selected);timer=setInterval(()=>select(selected+1),6000)})</script>'''
    return f'''<section class="recap-playground"><h1>Kids Playscape Rebuild Phase 2 Saturday July 25 2026</h1><div class="recap-playground-grid">{first}</div></section><section class="recap-vbs"><h2>Vacation Bible School June 15–18 2026</h2><div class="recap-vbs-feature">{gallery}</div>{controls}<div class="recap-thumbnails">{thumbs}</div></section>{script}'''


def render_missions_page(groups: list[dict], up: str) -> str:
    cards = []
    assets = [f"assets/production/{name}" for name in ("035.png","036.png","037.jpg","038.jpg","039.png","040.jpg","041.png","042.png","043.jpg","044.jpg","045.png","046.png")]
    image_index = 0
    for group in groups:
        if not group.get("heading"):
            continue
        title = group["heading"]["text"]
        paragraphs = "".join(f'<p>{linkify(item["text"])}</p>' for item in group["items"] if item["tag"] == "p" and not item["text"].startswith("http"))
        link = next((item["text"] for item in group["items"] if item["tag"] == "p" and item["text"].startswith("http")), "")
        link_html = f'<p class="mission-url">{linkify(link)}</p>' if link else ""
        image = image_tag(assets[image_index], title, up) if image_index < len(assets) else ""
        image_index += 1
        responsive_image_class = "mission-responsive-image" if image_index - 1 in {2, 3} else ""
        cards.append(f'<article class="mission-card {responsive_image_class}"><h2>{esc(title)}</h2>{image}<div>{paragraphs}{link_html}</div></article>')
    intro = next((item["text"] for g in groups for item in g["items"] if item["tag"] == "p"), "")
    hero = image_tag("assets/012.jpg", "People joining hands in prayer.", up)
    return f'<section class="mission-hero">{hero}<div><h1>Missions</h1><p>{esc(intro)}</p></div></section><section class="mission-grid"><h2>Outreach Missions We Support</h2><div class="mission-cards">{"".join(cards)}</div></section>'


def render_core_values_page(groups: list[dict], up: str) -> str:
    cards = []
    for group, path in zip(groups[:2], ("assets/010.jpg", "assets/011.jpg")):
        title = group.get("heading", {}).get("text", "")
        paragraphs = [item["text"] for item in group["items"] if item["tag"] == "p"]
        full_copy = "".join(f'<p>{esc(text)}</p>' for text in paragraphs)
        copy = full_copy
        cards.append(f'<section class="values-card">{image_tag(path,title,up)}<div><h2>{esc(title)}</h2>{copy}</div></section>')
    quote = next((g for g in groups[2:] if g.get("heading")), None)
    quote_html = ""
    if quote:
        text = quote["heading"]["text"]
        cite = next((item["text"] for item in quote["items"] if item["tag"] == "p"), "")
        quote_html = f'<section class="values-quote" aria-label="Scripture quotation"><blockquote>{esc(text)}</blockquote><p>{esc(cite)}</p></section>'
    return f'<h1 class="values-title">Core Values</h1><section class="values-grid">{"".join(cards)}</section>{quote_html}'


def render_staff_page(content: list[dict], images: list[dict], up: str) -> str:
    people = [
        ("Pastor Doreen Gibbons - Lead Pastor", "Doreen"),
        ("Beverly Alt - Music Director", "Beverly"),
        ("Kate McIver - Pianist", "Kate"),
        ("Ray Freeman - Deacons Leader", "Ray"),
        ("Greg Gibbons - Leader of Prayer Ministry", "Greg"),
        ('"Heavenly" Choir - Small but mighty', "Choir"),
    ]
    descriptions = {}
    person_for_paragraph = {
        "doreen": "Doreen", "beverly": "Beverly", "kate": "Kate",
        "ray freeman": "Ray", "greg gibbons": "Greg", "heavenly": "Choir",
    }
    for item in content:
        text = item["text"]
        if item["tag"] != "p":
            continue
        sample = text.casefold()[:180]
        match = next((key for label, key in person_for_paragraph.items() if label in sample), None)
        if match and match not in descriptions:
            descriptions[match] = text
    cards = []
    for i, (name, match) in enumerate(people):
        path = images[i]["path"] if i < len(images) else ""
        photo = image_tag(path, name, up) if path else ""
        description = descriptions.get(match, "")
        copy = ""
        if description:
            copy = f'<p>{esc(description)}</p>'
        cards.append(f'<article class="staff-card">{photo}<h2>{esc(name)}</h2>{copy}</article>')
    return f'<h1 class="route-label">Staff</h1><section class="staff-grid">{"".join(cards)}</section>'


def render_history_page(content: list[dict], up: str) -> str:
    paragraphs = []
    history = [item["text"] for item in content if item["tag"] == "p"]
    for i, text in enumerate(history):
        if i == 0 and "They described themselves as" in text:
            lead, quote = text.split("They described themselves as", 1)
            paragraphs.append(f'<p>{esc(lead)}<em>They described themselves as{esc(quote)}</em></p>')
        elif i == 1 and " Joe West – Former Pastor" in text:
            quote, author = text.rsplit(" Joe West – Former Pastor", 1)
            paragraphs.append(f'<p><em>{esc(quote)}</em> Joe West – Former Pastor{esc(author)}</p>')
        else:
            paragraphs.append(f'<p>{esc(text)}</p>')
    return f'<h1 class="route-label">Church History</h1><section class="history-panel">{image_tag("assets/013.jpg","Black and white drawing of the original Pleasant Ridge church in winter", up)}<div>{"".join(paragraphs)}</div></section>'


def render_small_groups_page(groups: list[dict], up: str, page_title: str) -> str:
    citation = groups[0]["items"][0]["text"] if groups and groups[0]["items"] else "Hebrews 10:24-25"
    intro = next((g for g in groups if (g.get("heading") or {}).get("text", "").casefold() == "small group bible studies"), {})
    intro_text = "".join(f'<p>{esc(item["text"])}</p>' for item in intro.get("items", []) if item["tag"] == "p")
    meetings = [g for g in groups if (g.get("heading") or {}).get("text", "").lstrip("\u200b ").casefold().startswith(("men's small group", "women's small group", "women's circle"))]
    blocks = []
    for group in meetings:
        heading = (group.get("heading") or {}).get("text", "").lstrip("\u200b ")
        copy = "".join(f'<p>{esc(item["text"])}</p>' for item in group["items"] if item["tag"] == "p")
        normalized = heading.casefold()
        if normalized.startswith("men's small group"):
            picture = image_tag("assets/production/085.jpg", "Men’s Small Group Bible study meeting in the church library", up)
        elif normalized.startswith("women's small group"):
            picture = image_tag("assets/production/086.jpg", "Women’s Small Group meeting in the church fellowship room", up)
        elif normalized.startswith("women's circle"):
            picture = image_tag("assets/production/053.jpg", "Women’s Fellowship sign", up)
        else:
            picture = ""
        anchor = ' id="womens-fellowship"' if normalized.startswith("women's circle") else ""
        blocks.append(f'<section class="small-meeting"{anchor}><h3>{esc(heading)}</h3>{picture}<div>{copy}</div></section>')
    return f'<section class="small-hero"><h1>{esc(page_title)}</h1><p class="small-citation">{esc(citation)}</p></section><section class="small-intro"><div><h2>Small Group Bible Studies</h2>{intro_text}</div>{image_tag("assets/production/052.jpg","Small group gathered for Bible study and prayer",up)}</section><h2 class="small-section-title">Adult Small Groups</h2><section class="small-meetings">{"".join(blocks)}</section>'


def render_find_peace_page(content: list[dict], images: list[dict], up: str) -> str:
    topics = {"all have sinned", "the wages of sin", "the gift of god", "confess jesus as lord", "results of salvation", "sharing the good news"}
    cards = []
    current = None
    for item in content:
        if item["tag"] == "h4" and item["text"].casefold() in topics:
            if current: cards.append(current)
            current = {"title": item["text"], "items": []}
        elif current and item["tag"] == "p": current["items"].append(item["text"])
    if current: cards.append(current)
    html_cards = []
    image_by_title = {
        "all have sinned": "assets/015.png",
        "the wages of sin": "assets/016.jpg",
        "the gift of god": "assets/017.jpg",
        "confess jesus as lord": "assets/018.jpg",
        "results of salvation": "assets/019.jpg",
        "sharing the good news": "assets/020.jpg",
    }
    for card in cards:
        path = image_by_title.get(card["title"].casefold(), "")
        img = image_tag(path, card["title"], up) if path else ""
        copy = "".join(f'<p>{esc(text)}</p>' for text in card["items"])
        html_cards.append(f'<article class="peace-card"><h2>{esc(card["title"])}</h2>{img}<div>{copy}</div></article>')
    return f'<h1 class="route-label">Salvation in Christ</h1><section class="peace-grid">{"".join(html_cards)}</section><section class="peace-contact"><h2>Contact Us</h2><p><strong>Church Service: Sunday mornings, 9 a.m.</strong></p><h3>We would love to talk with you about faith in Jesus</h3><button type="button" class="open-peace-form" aria-expanded="false" aria-controls="peace-contact-form">Tell me more about faith in Jesus</button><form id="peace-contact-form" class="local-preview-form" data-integration="activity-accounts:prcc-contact" data-submission-state="not-connected" hidden><label>Email*<input name="email" type="email" autocomplete="email" required></label><label>Message<textarea name="message" rows="5" required></textarea></label><button type="submit">Preview message</button><p class="submission-note" aria-live="polite">This preview validates locally and does not send messages.</p></form><p>Pleasant Ridge Christian Church</p><p>2049 Pleasant Ridge Road, Greensboro, NC 27410</p></section>'


def render_weekly_page(groups: list[dict], up: str) -> str:
    quote_group = groups[0] if groups else {}
    quote = (quote_group.get("heading") or {}).get("text", "")
    citation = next((item["text"] for item in quote_group.get("items", []) if item["tag"] == "p"), "Acts 20:28")
    weekly = next((g for g in groups if (g.get("heading") or {}).get("text", "").casefold() == "weekly message"), {})
    sneak = next((g for g in groups if "sneak peek" in (g.get("heading") or {}).get("text", "").casefold()), {})
    traditions = [g for g in groups if g not in (quote_group, weekly, sneak) and (g.get("heading") or {}).get("text", "").casefold() not in {"words to encourage", "words of encouragement", "traditions explained"}]
    encouragement = next((g for g in groups if any(label in (g.get("heading") or {}).get("text", "").casefold() for label in ("words to encourage", "words of encouragement"))), {})
    weekly_copy = "".join(f'<p>{esc(item["text"])}</p>' for item in weekly.get("items", []) if item["tag"] == "p")
    sneak_copy = "".join(f'<p>{esc(item["text"])}</p>' for item in sneak.get("items", []) if item["tag"] == "p")
    traditions_copy = "".join(render_group(g, "weekly-update", up) for g in traditions)
    encouragement_copy = "".join(f'<p>{esc(item["text"])}</p>' for item in encouragement.get("items", []) if item["tag"] == "p")
    return f'<h1 class="route-label">Weekly Update</h1><section class="weekly-hero">{image_tag("assets/production/047.jpg","Shepherd watching a flock of sheep",up)}<blockquote>{esc(quote)}<cite>{esc(citation)}</cite></blockquote></section><section class="weekly-message"><h2>Weekly Message</h2><div class="weekly-message-main">{image_tag("assets/production/048.jpg","Weekly message graphic",up)}<div class="weekly-message-copy">{weekly_copy}</div></div><aside>{image_tag("assets/production/049.jpg","Sunday sermon sneak peek graphic",up)}<div><h3>Sermon Sneak Peek</h3>{sneak_copy}</div></aside></section><div class="weekly-spacer"></div><section class="weekly-traditions">{image_tag("assets/production/050.jpg","Candle in the church",up)}<h2>Traditions Explained</h2>{traditions_copy}</section><section class="weekly-encouragement"><h2>Words to Encourage</h2><div>{image_tag("assets/production/051.jpg","Bible verse about trusting the Lord",up)}<div><h3>Words of encouragement</h3>{encouragement_copy}</div></div></section>'


def render_prayer_page(groups: list[dict], up: str, page_title: str) -> str:
    citation = groups[0]["items"][0]["text"] if groups and groups[0]["items"] else "Acts 2:42"
    priority = next((g for g in groups if (g.get("heading") or {}).get("text", "").casefold() == "prayer priority"), {})
    meetings = next((g for g in groups if (g.get("heading") or {}).get("text", "").casefold() == "prayer meetings"), {})
    priority_copy = "".join(f'<p>{esc(item["text"])}</p>' for item in priority.get("items", []) if item["tag"] == "p")
    meetings_copy = "".join(f'<p>{esc(item["text"])}</p>' for item in meetings.get("items", []) if item["tag"] == "p")
    return f'<section class="prayer-hero"><h1>{esc(page_title)}</h1><p>{esc(citation)}</p></section><section class="prayer-ministry"><h2>Prayer Ministry</h2><div class="prayer-priority">{image_tag("assets/production/064.png","Devote yourselves to prayer",up)}<div><h3>Prayer Priority</h3>{priority_copy}</div></div></section><section class="prayer-meetings">{image_tag("assets/production/076.jpg","Lord hear our prayers",up)}<div><h2>Prayer Meetings</h2>{meetings_copy}</div></section><section class="prayer-request"><h2>Prayer Request</h2><form class="local-preview-form" data-integration="activity-accounts:prcc-prayer-request" data-submission-state="not-connected"><label>Name<input name="name" autocomplete="name"></label><label>Email*<input name="email" type="email" autocomplete="email" required></label><label><span class="visually-hidden">Prayer request</span><textarea name="message" rows="5" placeholder="Prayer request" required></textarea></label><button type="submit">Preview request</button><p class="submission-note" aria-live="polite">This preview validates locally and does not send requests.</p></form><div class="prayer-request-notes"><p>Feel free to share your name and email address if you would like someone to contact you</p><p><strong>All prayer requests are held in strictest confidence</strong></p></div></section>'


def render_children_page(groups: list[dict], up: str, page_title: str) -> str:
    citation = groups[0]["items"][0]["text"] if groups and groups[0]["items"] else "Matthew 19:14"
    cards = []
    program_images = ["assets/production/054.jpg", "assets/production/055.jpg", "assets/production/056.jpg"]
    child_groups = [g for g in groups if g.get("heading")][:3]
    for i, group in enumerate(child_groups):
        title = group.get("heading", {}).get("text", "").lstrip("\u200b ")
        copy = "".join(f'<p>{esc(item["text"])}</p>' for item in group["items"] if item["tag"] in {"p", "li"})
        picture = image_tag(program_images[i], title, up)
        cards.append(f'<article class="children-card"><h3>{esc(title)}</h3>{picture}<div class="children-copy">{copy}</div></article>')
    vbs_group = next((g for g in groups if (g.get("heading") or {}).get("text", "").lstrip("\u200b ").casefold() in {"vacation bible school", "vcation bible school"}), None)
    vbs_intro = "".join(f'<p>{esc(item["text"])}</p>' for item in (vbs_group or {}).get("items", []) if item["tag"] == "p")
    vbs_groups = []
    for group in groups:
        heading = (group.get("heading") or {}).get("text", "").lstrip("\u200b ").casefold()
        if heading.startswith(("scuba", "true north", "rainforest falls")):
            vbs_groups.append(group)
    vbs_cards = []
    for group in vbs_groups[:3]:
        title = group["heading"]["text"].lstrip("\u200b ")
        copy = "".join(f'<p>{esc(item["text"])}</p>' for item in group["items"] if item["tag"] == "p")
        vbs_cards.append(f'<article><h3>{esc(title)}</h3>{copy}</article>')
    gallery = [f"assets/production/{name}.jpg" for name in ("059", "060", "061", "062", "063")]
    gallery_main = "".join(f'<img data-slide="{i}" src="{up}{esc(path)}" alt="Rainforest Falls VBS gallery image {i+1}" loading="eager">' for i, path in enumerate(gallery))
    gallery_thumbs = "".join(f'<button type="button" data-slide="{i}" aria-label="Show Rainforest Falls photo {i+1}">{image_tag(path, "", up)}</button>' for i, path in enumerate(gallery))
    controls = '<div class="carousel-controls"><button type="button" data-carousel-step="-1" aria-label="Previous Vacation Bible School photo">‹</button><button type="button" data-carousel-step="1" aria-label="Next Vacation Bible School photo">›</button></div>'
    script = '''<script>(()=>{const stage=document.querySelector(".children-gallery-main");if(!stage)return;const slides=[...stage.querySelectorAll("[data-slide]")],buttons=[...document.querySelectorAll(".children-gallery-thumbs button")],steps=[...document.querySelectorAll(".children-gallery-title [data-carousel-step]")];let active=0,timer,startX=null;function show(n){active=(n+slides.length)%slides.length;slides.forEach((s,i)=>{const d=(i-active+slides.length)%slides.length;s.dataset.position=d===0?"active":d===slides.length-1?"previous":d===1?"next":"hidden"});buttons.forEach((b,i)=>b.setAttribute("aria-current",String(i===active)))}function resume(){clearInterval(timer);timer=setTimeout(()=>{clearInterval(timer);timer=setInterval(()=>show(active+1),6000)},12000)}function pause(){clearInterval(timer)}buttons.forEach((b,i)=>b.addEventListener("click",()=>{show(i);resume()}));steps.forEach(b=>b.addEventListener("click",()=>{show(active+Number(b.dataset.carouselStep));resume()}));stage.addEventListener("mouseenter",pause);stage.addEventListener("mouseleave",()=>timer=setInterval(()=>show(active+1),6000));stage.addEventListener("focusin",pause);stage.addEventListener("focusout",e=>{if(!stage.contains(e.relatedTarget))timer=setInterval(()=>show(active+1),6000)});stage.addEventListener("touchstart",e=>{startX=e.changedTouches[0].clientX;pause()},{passive:true});stage.addEventListener("touchend",e=>{if(startX===null)return;const delta=e.changedTouches[0].clientX-startX;if(Math.abs(delta)>35){show(active+(delta<0?1:-1));resume()}startX=null},{passive:true});show(0);timer=setInterval(()=>show(active+1),6000)})()</script>'''
    return f'<section class="children-hero"><blockquote><h1>{esc(page_title)}</h1><cite>{esc(citation)}</cite></blockquote>{image_tag("assets/014.jpg","Jesus welcoming children",up)}</section><section class="children-programs"><h2>Ministries for Children and Youth</h2><div class="children-grid">{"".join(cards)}</div></section><section class="children-vbs">{image_tag("assets/production/057.jpg","Children at Vacation Bible School",up)}<div class="children-vbs-intro"><h2>Vacation Bible School</h2>{vbs_intro}</div><div class="children-vbs-cards">{"".join(vbs_cards)}</div></section><section class="children-gallery-title"><h2>Rainforest Falls - VBS 2026</h2><div class="children-gallery-main">{gallery_main}</div>{controls}<div class="children-gallery-thumbs">{gallery_thumbs}</div></section>{script}'


def render_giving_page(page: dict, up: str) -> str:
    target = next((link.get("source_url", "") for link in page.get("external_links", []) if link.get("source_url", "").startswith("https://")), "#")
    return f'<section class="giving-hero" style="background-image:url(\'{up}assets/production/074.jpg\')"><h1>Online Donation</h1><a href="{esc(target)}" target="_blank" rel="noopener noreferrer">Donate Online</a></section>'


def render_safe_form(title: str, note: str = "") -> str:
    note_html = f'<p>{esc(note)}</p>' if note else ""
    return f'<section class="page-section form-preview"><h2>{esc(title)}</h2>{note_html}<form onsubmit="return false"><label>Name<input name="name" autocomplete="name"></label><label>Email<input name="email" type="email" autocomplete="email"></label><label>Message<textarea name="message" rows="5"></textarea></label><button type="button" disabled>Send</button></form><p class="recaptcha-note">This staging preview never sends submissions.</p></section>'


def nav_markup(up: str) -> str:
    def link(label, path):
        href = up + path
        return f'<a href="{esc(href)}">{esc(label)}</a>'
    about_links = "".join(link(label, path) for label, path in ABOUT)
    more_items = [("Find Peace in Christ", "find-peace-in-christ/"), ("Online Giving", "online-giving/"), ("Sermons", "sermons/"), ("Event Calendar", "event-calendar/"), ("Event Recap", "event-recap/")]
    more_links = "".join(link(label, path) for label, path in more_items)
    desktop = f'<nav class="desktop-nav" aria-label="Main navigation">{link("Home", "index.html")}<details data-nav-menu><summary>About <span aria-hidden="true">⌄</span></summary><div class="menu-panel">{about_links}</div></details>{link("Weekly Update","weekly-update/")}{link("Small Groups","small-groups/")}{link("Children and Youth","children-and-youth/")}{link("Prayer","prayer/")}<details data-nav-menu><summary>More <span aria-hidden="true">⌄</span></summary><div class="menu-panel">{more_links}</div></details></nav>'
    mobile = f'<div class="mobile-menu"><details data-nav-menu><summary aria-label="Open navigation"><span></span><span></span><span></span></summary><nav aria-label="Main navigation">{link("Home","index.html")}<details data-nav-menu><summary>About</summary>{about_links}</details>{link("Weekly Update","weekly-update/")}{link("Small Groups","small-groups/")}{link("Children and Youth","children-and-youth/")}{link("Prayer","prayer/")}<details data-nav-menu><summary>More</summary>{more_links}</details></nav></details></div>'
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
        if len(sys.argv) > 1 and slug != sys.argv[1].strip("/"):
            continue
        if slug == "index":
            continue
        folder = ROOT / slug
        folder.mkdir(parents=True, exist_ok=True)
        up = "../"
        title, content = content_for(page)
        document_title = page.get("page_title") or title
        groups = groups_for(content)
        images = image_records(slug, inventory, local)
        special = {"contact-us", "online-giving", "event-calendar", "sermons", "event-recap", "missions", "core-values", "children-and-youth", "ministry-staff", "church-history", "small-groups", "find-peace-in-christ", "weekly-update", "prayer"}
        if groups and images and slug not in special:
            # Distribute the observed source images across actual heading groups in source order.
            for i, image in enumerate(images):
                groups[min(i, len(groups)-1)]["images"].append(image)
        sections = "".join(render_group(g, slug, up) for g in groups)
        body = f'<div class="page-heading"><h1>{esc(title)}</h1></div><article>{sections}</article>'
        if slug == "prayer": body = f'<article>{render_prayer_page(groups, up, title)}</article>'
        elif slug == "faqs": body = f'<article>{render_faq_page(content)}</article>'
        elif slug == "weekly-update": body = f'<article>{render_weekly_page(groups, up)}</article>'
        elif slug == "find-peace-in-christ": body = f'<article>{render_find_peace_page(content, images, up)}</article>'
        if slug == "contact-us": body = f'<article>{render_contact_page()}</article>'
        elif slug == "online-giving": body = f'<article>{render_giving_page(page, up)}</article>'
        elif slug == "event-calendar": body = f'<article><h1 class="sr-only">Event Calendar</h1>{render_calendar_page(groups)}</article>'
        elif slug == "sermons": body = f'<article>{render_sermons_page()}</article>'
        elif slug == "event-recap": body = f'<article>{render_recap_page(images, up)}</article>'
        elif slug == "missions": body = f'<article>{render_missions_page(groups, up)}</article>'
        elif slug == "core-values": body = f'<article>{render_core_values_page(groups, up)}</article>'
        elif slug == "children-and-youth": body = f'<article>{render_children_page(groups, up, title)}</article>'
        elif slug == "ministry-staff": body = f'<article>{render_staff_page(content, images, up)}</article>'
        elif slug == "church-history": body = f'<article>{render_history_page(content, up)}</article>'
        elif slug == "small-groups": body = f'<article>{render_small_groups_page(groups, up, title)}</article>'
        output=f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="description" content="{esc(document_title)} — Pleasant Ridge Christian Church in Greensboro, North Carolina"><title>{esc(document_title)} | Pleasant Ridge Christian Church</title><link rel="icon" type="image/svg+xml" href="{up}favicon.svg"><link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin><link href="https://fonts.googleapis.com/css2?family=Adamina&family=Poppins:wght@400;500;600;700&display=swap" rel="stylesheet"><link rel="stylesheet" href="{up}pages.css"><script src="{up}nav.js" defer></script></head><body class="page-{esc(slug)}"><a class="skip" href="#main">Skip to content</a>{nav_markup(up)}<main id="main" class="page-main">{body}</main><footer class="page-footer"><small>Copyright © 2026 Pleasant Ridge Christian Church · All rights reserved.</small><a class="facebook-link" href="https://www.facebook.com/profile.php?id=100089013843748" target="_blank" rel="noopener noreferrer" aria-label="Facebook"><svg aria-hidden="true" viewBox="0 0 24 24"><path d="M13.4 21v-8h2.7l.4-3.1h-3.1v-2c0-.9.3-1.5 1.6-1.5h1.7V3.6c-.3 0-1.3-.1-2.4-.1-2.4 0-4.1 1.5-4.1 4.2v2.3H7.5v3.1h2.7v8z"/></svg></a></footer></body></html>'''
        (folder/"index.html").write_text(output,encoding="utf-8")
        counts.append({"route":"/"+slug+"/","content_blocks":len(content),"images":len(images),"groups":len(groups),"custom_renderer":slug in special,"safe_form_preview":slug in {"contact-us", "prayer", "find-peace-in-christ"}})
    print(json.dumps({"pages_rendered":len(counts),"routes":counts},indent=2,ensure_ascii=False))

if __name__ == "__main__": main()
