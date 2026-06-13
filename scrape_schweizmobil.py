"""
Scrape Swiss hiking routes from SchweizMobil's public JSON API.

Each Wanderland route is split into "Etappen" (stages) — those are the
actual day-long hikes. We fetch every stage of every national and regional
route, keep the ones that qualify as a single-day hike, and write them to
routes.csv.

Filters:
    - distance        >=  8 km
    - estimated duration <= 10 hours

CSV columns:
    name, region, distance_km, elevation_gain_m,
    difficulty, duration_min, description, route_number, url

Run:
    python3 scrape_schweizmobil.py
"""

import csv
import time
import requests
import os

BASE_URL = "https://schweizmobil.ch/api/4"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (educational hiking-finder project)",
    "Referer": "https://www.schweizmobil.ch/",
}
LANG = "de"                  # "en", "fr", "it" also work

MIN_DISTANCE_KM = 8
MAX_DURATION_MIN = 10 * 60   # 10 hours
MAX_RESULTS = 300           # cap output size
OUTPUT_FILE = "data/routes.csv"
SLEEP_BETWEEN_CALLS = 0.3    # be polite to the API


# ------------------------------ helpers ------------------------------ #


def fetch_json(path):
    """GET an endpoint and return parsed JSON."""
    resp = requests.get(f"{BASE_URL}{path}", headers=HEADERS, timeout=30)
    resp.raise_for_status()
    return resp.json()


def fetch_route_list(category):
    """List of all hiking routes in a category (national / regional / local)."""
    print(f"  Fetching '{category}' route list...")
    return fetch_json(f"/routes/hike/{category}?lang={LANG}")


def fetch_stage(route_number, segment_number):
    """Detail for one stage. segment_number=0 is the full route."""
    return fetch_json(
        f"/route_or_segment/hike/{route_number}/{segment_number}?lang={LANG}"
    )


def naismith_minutes(distance_km, ascent_m):
    """Naismith's rule: 5 km/h + 1 h per 600 m climb. Used as fallback."""
    return round((distance_km / 5.0 + (ascent_m or 0) / 600.0) * 60)


def format_difficulty(detail):
    """Combine SchweizMobil's three difficulty fields into one label."""
    parts = []
    if detail.get("gradeText"):
        parts.append(detail["gradeText"])
    if detail.get("grade"):
        parts.append(f"technical: {detail['grade']}")
    if detail.get("fitness"):
        parts.append(f"fitness: {detail['fitness']}")
    return " | ".join(parts) if parts else "unknown"


def clean_text(s):
    """Trim and collapse whitespace; SchweizMobil uses non-breaking spaces."""
    if not s:
        return ""
    return " ".join(s.replace("\u00a0", " ").split())


def stage_to_row(stage, parent_title):
    """Convert a stage detail dict to one CSV row."""
    distance_km = stage.get("length") or 0
    ascent_m = stage.get("ascent") or 0

    # SchweizMobil's hikingTime is hours (float) on stages, often None on full routes
    hours = stage.get("hikingTime")
    if hours:
        duration_min = round(hours * 60)
    else:
        duration_min = naismith_minutes(distance_km, ascent_m)

    start = stage.get("start") or ""
    end = stage.get("end") or ""
    region = f"{start} → {end}" if start and end else (start or end)

    seg = stage.get("segmentNumber", 0)
    name = (
        f"{parent_title} – Etappe {seg}" if seg else parent_title
    )

    description = clean_text(
        stage.get("description") or stage.get("abstract") or ""
    )

    route_number = stage.get("routeNumber")
    url = (
        f"https://www.schweizmobil.ch/{LANG}/wanderland/route-{route_number}"
        if route_number is not None else ""
    )

    return {
        "name": name,
        "region": region,
        "distance_km": distance_km,
        "elevation_gain_m": ascent_m,
        "difficulty": format_difficulty(stage),
        "duration_min": duration_min,
        "description": description,
        "route_number": route_number,
        "url": url,
    }


def passes_filters(row):
    return (
        row["distance_km"] >= MIN_DISTANCE_KM
        and row["duration_min"] <= MAX_DURATION_MIN
    )


# ----------------------------- main scrape ---------------------------- #


def collect_stages(categories=("regional", "local")):
    """
    Yield one row per *standalone* day hike.

    We deliberately skip routes that are split into Etappen (stages > 1)
    because those are sub-segments of multi-day trails like Via Alpina.
    Only routes that are a single hike on their own (stages == 1) are kept.
    """
    for cat in categories:
        for route in fetch_route_list(cat):
            route_number = route["routeNumber"]
            stages = route.get("stages") or 1
            title = route.get("title", f"Route {route_number}")

            if stages > 1:
                continue  # multi-day trail — not a standalone day hike

            try:
                stage = fetch_stage(route_number, 0)
            except requests.HTTPError as e:
                print(f"    skip {title}: {e}")
                continue
            yield stage_to_row(stage, title)
            time.sleep(SLEEP_BETWEEN_CALLS)


def main():
    print("Scraping SchweizMobil hiking stages (single-day hikes)...\n")

    rows = []
    for row in collect_stages():
        if not passes_filters(row):
            continue
        rows.append(row)
        h, m = divmod(row["duration_min"], 60)
        print(
            f"  [{len(rows):>3}]  "
            f"{row['name'][:55]:<55}  "
            f"{row['distance_km']:>4} km  "
            f"{h}h{m:02d}"
        )
        if len(rows) >= MAX_RESULTS:
            print(f"\n  Hit cap of {MAX_RESULTS} routes, stopping.")
            break

    fieldnames = [
        "name", "region", "distance_km", "elevation_gain_m",
        "difficulty", "duration_min", "description",
        "route_number", "url",
    ]
    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"\n✅ Saved {len(rows)} day hikes to {OUTPUT_FILE}")
    print(f"   (filters: ≥{MIN_DISTANCE_KM} km, ≤{MAX_DURATION_MIN//60} h)")


if __name__ == "__main__":
    main()
