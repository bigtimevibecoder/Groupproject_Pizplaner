"""
Interactive Swiss day-hike finder.

Reads routes.csv (produced by scrape_schweizmobil.py) and lets you filter
hikes by your starting location, drive time, hike duration, difficulty,
and distance. Returns the best matches with description and SchweizMobil
link.

Drive time is estimated from straight-line distance ÷ 50 km/h. Trailhead
coordinates are geocoded once via OpenStreetMap's Nominatim service and
then cached in geocode_cache.json.

Run:
    python3 find_route.py
"""

import csv
import json
import math
import os
import sys
import time
import requests

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_FILE = os.path.join(BASE_DIR, "routes.csv")
CACHE_FILE = os.path.join(BASE_DIR, "geocode_cache.json")

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
HEADERS = {"User-Agent": "hiking-finder educational project (zino.maier@gmail.com)"}

# Average effective driving speed on Swiss roads (mix of motorway/cantonal/mountain).
AVG_DRIVE_KMH = 50.0

# Difficulty levels available in the CSV (from gradeText)
TRAIL_TYPES = ["Wanderweg", "Bergwanderweg", "Alpinwanderweg"]


# --------------------------- geocoding helpers --------------------------- #


def load_cache():
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE) as f:
            return json.load(f)
    return {}


def save_cache(cache):
    with open(CACHE_FILE, "w") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)


def geocode(place, cache):
    """Return (lat, lon) for a place name, with caching. None if not found."""
    if not place:
        return None
    if place in cache:
        return tuple(cache[place]) if cache[place] else None

    # Bias to Switzerland for trailheads, but fall back to free search.
    for params in (
        {"q": place, "countrycodes": "ch,li", "format": "json", "limit": 1},
        {"q": place, "format": "json", "limit": 1},
    ):
        try:
            resp = requests.get(NOMINATIM_URL, params=params, headers=HEADERS, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            if data:
                latlon = (float(data[0]["lat"]), float(data[0]["lon"]))
                cache[place] = latlon
                save_cache(cache)
                time.sleep(1.0)  # Nominatim policy: max 1 req/sec
                return latlon
        except Exception as e:
            print(f"    geocode failed for {place!r}: {e}")

    cache[place] = None
    save_cache(cache)
    return None


def haversine_km(a, b):
    """Great-circle distance between (lat1,lon1) and (lat2,lon2) in km."""
    R = 6371.0
    lat1, lon1 = map(math.radians, a)
    lat2, lon2 = map(math.radians, b)
    dlat, dlon = lat2 - lat1, lon2 - lon1
    h = math.sin(dlat/2)**2 + math.cos(lat1)*math.cos(lat2)*math.sin(dlon/2)**2
    return 2 * R * math.asin(math.sqrt(h))


# ------------------------------- ui helpers ------------------------------ #


def fmt_duration(minutes):
    minutes = int(minutes)
    h, m = divmod(minutes, 60)
    return f"{h}h{m:02d}" if h else f"{m}min"


def ask(prompt, default=None, parser=str):
    suffix = f" [{default}]" if default is not None else ""
    while True:
        raw = input(f"{prompt}{suffix}: ").strip()
        if not raw:
            return default
        try:
            return parser(raw)
        except (ValueError, TypeError):
            print(f"  Invalid input, try again.")


def ask_optional_float(prompt):
    raw = input(f"{prompt} (Enter to skip): ").strip()
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError:
        print("  Skipping — couldn't parse.")
        return None


# ------------------------------- main flow ------------------------------- #


def load_routes():
    if not os.path.exists(CSV_FILE):
        sys.exit(f"❌ {CSV_FILE} not found. Run scrape_schweizmobil.py first.")
    with open(CSV_FILE, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    # Coerce numerics
    for r in rows:
        r["distance_km"] = float(r["distance_km"]) if r["distance_km"] else 0.0
        r["duration_min"] = int(r["duration_min"]) if r["duration_min"] else 0
        r["elevation_gain_m"] = int(float(r["elevation_gain_m"])) if r["elevation_gain_m"] else 0
    return rows


def collect_inputs(num_routes):
    print("\n" + "=" * 60)
    print("  🥾  PIZPLANER: Your Swiss Day-hike finder")
    print("=" * 60)
    print(f"  Database: {num_routes} day hikes from SchweizMobil.")
    print("=" * 60 + "\n")

    # 1. Starting location
    print("YOUR STARTING LOCATION")
    location = ask("City or address", default="St. Gallen")
    print()

    # 2. Drive time
    print("DRIVE TIME")
    max_drive = ask("Max drive time to trailhead (minutes)", default=90, parser=int)
    print()

    # 3. Hike duration
    print("HIKE DURATION")
    target = ask("Target hike duration (hours)", default=4.0, parser=float)
    tol = ask("Tolerance ±hours", default=1.5, parser=float)
    target_min = int(target * 60)
    tol_min = int(tol * 60)
    print(f"  → looking for hikes between "
          f"{fmt_duration(max(0, target_min - tol_min))} and "
          f"{fmt_duration(target_min + tol_min)}")
    print()

    # 4. Difficulty
    print("DIFFICULTY (Swiss SAC trail type)")
    print("  1. Wanderweg          — easy, well-marked yellow trails")
    print("  2. Bergwanderweg      — mountain trails (sure-footedness)")
    print("  3. Alpinwanderweg     — alpine trails (experience required)")
    print("  4. Any                — no restriction")
    choice = ask("Choose 1-4", default="4")
    trail_type = None
    if choice == "1": trail_type = "Wanderweg"
    elif choice == "2": trail_type = "Bergwanderweg"
    elif choice == "3": trail_type = "Alpinwanderweg"
    print()

    # 5. Distance cap
    print("DISTANCE")
    max_distance = ask_optional_float("Max distance in km")
    print()

    # 6. Result count
    n_results = ask("How many results to show", default=5, parser=int)
    print()

    return {
        "location": location,
        "max_drive_min": max_drive,
        "target_min": target_min,
        "tol_min": tol_min,
        "trail_type": trail_type,
        "max_distance": max_distance,
        "n_results": n_results,
    }


def filter_and_score(routes, criteria, user_coords, cache):
    """Apply filters, attach drive_min, and return matches sorted by best fit."""
    target = criteria["target_min"]
    tol = criteria["tol_min"]
    matches = []

    print(f"Computing drive times for {len(routes)} routes (cached after first run)...\n")

    for i, r in enumerate(routes, 1):
        # Duration filter (cheap)
        if abs(r["duration_min"] - target) > tol:
            continue

        # Distance filter (cheap)
        if criteria["max_distance"] and r["distance_km"] > criteria["max_distance"]:
            continue

        # Difficulty filter (cheap)
        if criteria["trail_type"]:
            if criteria["trail_type"] not in r["difficulty"]:
                continue

        # Geocode trailhead start (cached). The "start" half of the region.
        start = (r["region"].split("→")[0]).strip()
        start = start.split("(")[0].strip()  # drop parenthetical like "(Gaflei, FL)"
        coords = geocode(start, cache)
        if not coords:
            continue

        crow_km = haversine_km(user_coords, coords)
        drive_min = round(crow_km / AVG_DRIVE_KMH * 60)
        if drive_min > criteria["max_drive_min"]:
            continue

        r = dict(r)
        r["drive_min"] = drive_min
        r["crow_km"] = round(crow_km, 1)
        r["duration_diff"] = abs(r["duration_min"] - target)
        matches.append(r)

    # Sort: best duration match first, then shortest drive
    matches.sort(key=lambda r: (r["duration_diff"], r["drive_min"]))
    return matches


def print_route(r, idx):
    print(f"\n{idx}. {r['name']}")
    print(f"   📍 {r['region']}")
    print(f"   🚗 ~{fmt_duration(r['drive_min'])} drive (~{r['crow_km']} km straight-line)")
    print(f"   🥾 {r['distance_km']:.0f} km | "
          f"{fmt_duration(r['duration_min'])} | "
          f"+{r['elevation_gain_m']} m | {r['difficulty']}")
    desc = r["description"]
    if len(desc) > 250:
        desc = desc[:247].rsplit(" ", 1)[0] + "..."
    print(f"   {desc}")
    if r.get("url"):
        print(f"   🔗 {r['url']}")


def main():
    try:
        routes = load_routes()
        criteria = collect_inputs(len(routes))

        cache = load_cache()
        print("Geocoding your location...")
        user_coords = geocode(criteria["location"], cache)
        if not user_coords:
            sys.exit(f"❌ Could not geocode {criteria['location']!r}.")
        print(f"  → {criteria['location']} = {user_coords[0]:.4f}, {user_coords[1]:.4f}\n")

        matches = filter_and_score(routes, criteria, user_coords, cache)

        if not matches:
            print("\n😕  No routes match all your criteria.")
            print("   Try a longer drive time, wider duration tolerance, or a different difficulty.\n")
            return

        n = min(criteria["n_results"], len(matches))
        print("\n" + "=" * 60)
        print(f"  TOP {n} MATCHES (of {len(matches)} candidates)")
        print("=" * 60)
        for i, r in enumerate(matches[:n], 1):
            print_route(r, i)
        print("\n" + "=" * 60)
        print("Happy hiking! 🏔️\n")

    except KeyboardInterrupt:
        print("\nCancelled.\n")


if __name__ == "__main__":
    main()
