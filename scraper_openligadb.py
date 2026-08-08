"""
Scrapes api.openligadb.de for fixtures involving Berlin-based clubs.

Covers: Bundesliga (bl1), 2. Bundesliga (bl2), 3. Liga (bl3).
This is a clean JSON API - no HTML parsing, no scraping fragility.
Writes data/<date>.json for the next 14 days + data/index.json.

Berlin clubs that can appear in these leagues:
  - Hertha BSC (bl1/bl2)
  - 1. FC Union Berlin (bl1/bl2)
  - Any Berlin club promoted into 3. Liga (currently checked by name match)

Run: python scraper_openligadb.py [--debug]
"""
import json
import os
import sys
from datetime import datetime, timedelta, date
import urllib.request

API_BASE = "https://api.openligadb.de"
LEAGUES = ["bl1", "bl2", "bl3"]  # Bundesliga, 2. Bundesliga, 3. Liga
SEASON = str(date.today().year if date.today().month >= 7 else date.today().year - 1)

# Name fragments used to detect a Berlin-based club in the API's team names
BERLIN_CLUB_MARKERS = ["Berlin", "Hertha", "Union"]

DEBUG = "--debug" in sys.argv
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")


def log(*args):
    if DEBUG:
        print(*args)


def fetch_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "berlin-football-fixtures/1.0"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8"))


def is_berlin_club(team_name):
    return any(marker in team_name for marker in BERLIN_CLUB_MARKERS)


def fetch_league_matches(league):
    url = f"{API_BASE}/getmatchdata/{league}/{SEASON}"
    log(f"Fetching {url}")
    try:
        matches = fetch_json(url)
    except Exception as e:
        log(f"  failed: {e}")
        return []
    log(f"  got {len(matches)} matches for {league}")
    return matches


def normalize(match, league):
    home = match.get("team1", {}).get("teamName", "")
    away = match.get("team2", {}).get("teamName", "")
    kickoff = match.get("matchDateTime")  # ISO string
    return {
        "date": kickoff.split("T")[0] if kickoff else None,
        "time": kickoff.split("T")[1][:5] if kickoff else None,
        "home_team": home,
        "away_team": away,
        "league": league.upper(),
        "venue": match.get("location", {}).get("locationCity", "") if match.get("location") else "",
        "source": "openligadb",
    }


def main():
    os.makedirs(DATA_DIR, exist_ok=True)
    all_matches = []

    for league in LEAGUES:
        matches = fetch_league_matches(league)
        for m in matches:
            home = m.get("team1", {}).get("teamName", "")
            away = m.get("team2", {}).get("teamName", "")
            if is_berlin_club(home) or is_berlin_club(away):
                norm = normalize(m, league)
                if norm["date"]:
                    all_matches.append(norm)

    log(f"Total Berlin-related matches found: {len(all_matches)}")

    # Group by date, write today + next 14 days that have data
    by_date = {}
    for m in all_matches:
        by_date.setdefault(m["date"], []).append(m)

    today = date.today()
    written_dates = []
    for offset in range(0, 14):
        d = (today + timedelta(days=offset)).isoformat()
        if d in by_date:
            existing = []
            existing_path = os.path.join(DATA_DIR, f"{d}.json")
            if os.path.exists(existing_path):
                with open(existing_path) as f:
                    existing = json.load(f)
            # merge, replacing any prior openligadb entries for this date
            merged = [x for x in existing if x.get("source") != "openligadb"] + by_date[d]
            with open(existing_path, "w") as f:
                json.dump(merged, f, indent=2, ensure_ascii=False)
            written_dates.append(d)

    index_path = os.path.join(DATA_DIR, "index.json")
    existing_index = []
    if os.path.exists(index_path):
        with open(index_path) as f:
            existing_index = json.load(f)
    combined_index = sorted(set(existing_index) | set(written_dates))
    with open(index_path, "w") as f:
        json.dump(combined_index, f, indent=2)

    print(f"OpenLigaDB: wrote {len(written_dates)} date file(s), {len(all_matches)} matches total.")


if __name__ == "__main__":
    main()
