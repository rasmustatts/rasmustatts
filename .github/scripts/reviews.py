"""Hämtar Google-recensioner för Rasmustatts via Places API (New) och skriver in dem i index.html.

Körs dagligen av .github/workflows/reviews.yml. Nyckeln läses från GOOGLE_PLACES_KEY (repo-secret)
och hamnar aldrig på hemsidan. Om inget hittas lämnas sidan orörd.
"""
import html
import json
import os
import re
import sys
import urllib.request

KEY = os.environ.get("GOOGLE_PLACES_KEY", "").strip()
PLACE_ID = os.environ.get("PLACE_ID", "").strip()
QUERIES = ["Rasmustatts", "Rasmustatts Piteå", "Rasmustatts tatuering Piteå"]
PAGE = "index.html"
STAR = ('<svg width="18" height="18" viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3.5l2.6 5.3 5.9.9-4.3 4.1 '
        '1 5.8-5.2-2.7-5.2 2.7 1-5.8-4.3-4.1 5.9-.9z" fill="{fill}"/></svg>')


def call(url, body=None, mask=""):
    req = urllib.request.Request(url, data=json.dumps(body).encode() if body else None,
                                 method="POST" if body else "GET")
    req.add_header("X-Goog-Api-Key", KEY)
    req.add_header("X-Goog-FieldMask", mask)
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        print("HTTP", e.code, e.read().decode()[:500])
        sys.exit(1)


def find_place():
    for q in QUERIES:
        res = call("https://places.googleapis.com/v1/places:searchText",
                   {"textQuery": q, "languageCode": "sv", "regionCode": "SE"},
                   "places.id,places.displayName")
        for p in res.get("places", []):
            name = p.get("displayName", {}).get("text", "")
            print(f"Sökning '{q}': {name} ({p['id']})")
            if "rasmustatts" in name.lower().replace(" ", ""):
                return p["id"]
    return None


def short_name(full):
    parts = full.split()
    return parts[0] if len(parts) < 2 else f"{parts[0]} {parts[-1][0]}."


def stars(n):
    return "".join(STAR.format(fill="#FF4D1F" if i < n else "#3A3A3A") for i in range(5))


def card(r):
    text = (r.get("originalText") or r.get("text") or {}).get("text", "").strip()
    name = short_name(r.get("authorAttribution", {}).get("displayName", "Google-användare"))
    n = int(r.get("rating", 5))
    when = r.get("relativePublishTimeDescription", "")
    meta = " · ".join(x for x in [when, "Google"] if x)
    return (
        '<figure class="rev">\n'
        f'<div style="display:flex;gap:2px" role="img" aria-label="{n} av 5 stjärnor">{stars(n)}</div>\n'
        f'<blockquote style="margin:0;font-size:20px;line-height:1.5;color:#F2EEE6">”{html.escape(text)}”</blockquote>\n'
        '<figcaption style="display:flex;flex-wrap:wrap;justify-content:space-between;gap:8px 16px;align-items:center">'
        f'<span style="font-weight:600">{html.escape(name)}</span>'
        f'<span class="mono" style="color:#A39E95">{html.escape(meta)}</span></figcaption>\n'
        '</figure>\n'
    )


def main():
    if not KEY:
        print("GOOGLE_PLACES_KEY saknas – hoppar över.")
        return
    pid = PLACE_ID or find_place()
    if not pid:
        print("Hittade ingen plats för Rasmustatts. Lägg in PLACE_ID som repo-variabel.")
        return
    print("Place ID:", pid)
    d = call(f"https://places.googleapis.com/v1/places/{pid}?languageCode=sv",
             mask="displayName,rating,userRatingCount,reviews")
    reviews = [r for r in d.get("reviews", []) if (r.get("originalText") or r.get("text") or {}).get("text")]
    reviews.sort(key=lambda r: r.get("publishTime", ""), reverse=True)
    print(f"{d.get('displayName', {}).get('text')}: betyg {d.get('rating')} ({d.get('userRatingCount')} st), "
          f"{len(reviews)} med text")
    if not reviews:
        print("Inga recensioner med text – sidan lämnas orörd.")
        return
    page = open(PAGE, encoding="utf-8").read()
    new = re.sub(r"(<!--REVIEWS:START-->\n).*?(<!--REVIEWS:END-->)",
                 lambda m: m.group(1) + "".join(card(r) for r in reviews) + m.group(2), page, flags=re.S)
    if d.get("rating"):
        rating = f"{float(d['rating']):.1f}".replace(".", ",")
        new = re.sub(r"(<!--RATING:START-->).*?(<!--RATING:END-->)", lambda m: m.group(1) + rating + m.group(2), new)
    if new != page:
        open(PAGE, "w", encoding="utf-8").write(new)
        print("index.html uppdaterad.")
    else:
        print("Inga ändringar.")


if __name__ == "__main__":
    main()
