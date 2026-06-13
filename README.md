# PizPlaner 🥾

A two-script Python tool that scrapes hiking routes from the [SchweizMobil](https://www.schweizmobil.ch) public API and lets you interactively search for hikes that match your preferences — including starting location, drive time, duration, difficulty, and distance.

---

## Project Structure

| Script | Purpose |
|---|---|
| `scrape_schweizmobil.py` | Fetches hiking routes from the SchweizMobil API and saves them to `routes.csv` |
| `find_route.py` | Reads `routes.csv` and interactively helps you find a matching hike |

---

## Requirements

- Python 3.7 or higher
- [`requests`](https://pypi.org/project/requests/) library

```bash
pip install requests
```

---

## Quick Start

```bash
# 1. Fetch route data (or use the included routes.csv to skip this step)
python scrape_schweizmobil.py

# 2. Find a hike
python find_route.py
```

For the full project documentation, see [docs/Documentation_PizPlaner.pdf](docs/Documentation_PizPlaner.pdf).
