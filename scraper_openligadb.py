"""
Scrapes api.openligadb.de for fixtures involving Berlin-based clubs.

Covers: Bundesliga (bl1), 2. Bundesliga (bl2), 3. Liga (bl3) — men's
football only (OpenLigaDB's men's league codes; women's Bundesliga has
its own separate codes and is deliberately out of scope for this
project for now — see the `gender` field on every fixture, and the
README for why that's called out explicitly).

This is a clean JSON API - no HTML parsing, no scraping fragility.
Writes data/<date>.json for every remaining fixture in the season (today
onward - no artificial cutoff) + data/index.json. An earlier version of
this capped output at "today + 14 days," which silently hid real
fixtures further out (e.g. a match 3 weeks away just wouldn't appear
until the window slid close enough to catch it) - removed since the
dataset here is tiny (a handful of Berlin clubs, not the whole league)
so there's no real cost to keeping the full remaining schedule.

Berlin clubs that can appear in these leagues:
  - Hertha BSC (bl1/bl2 - currently bl2)
  - 1. FC Union Berlin (bl1/bl2 - currently bl1)
  - Any Berlin club promoted into 3. Liga (currently checked by name match)

Because Hertha and Union sit in different tiers as of the 2025-26/2026-27
seasons, they cannot appear as each other's opponent in real league data.
If you ever see them paired as opponents in this project's data, that's a
bug, not news of a promotion/relegation swap - check SEASON and the two
clubs' actual current divisions before trusting it.

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

# Every fixture in this project carries an explicit gender so tier/gender
# mixups (like men's vs women's Hertha-Union) can't happen silently. This
# scraper only ever touches OpenLigaDB's men's league codes above, so it's
# hardcoded here rather than inferred.
GENDER = "M"

# OpenLigaDB's `location` field is usually just a city, not a street
# address. Ground addresses for the Berlin clubs likely to show up here
# are hardcoded below, same approach as the cinema addresses in BerlinKino.
# Best-effort / worth spot-checking before treating as authoritative.
VENUE_ADDRESSES = {
    "Olympiastadion Berlin": "Olympischer Platz 3, 14053 Berlin",
    "Stadion An der Alten Försterei": "Hämmerlingstraße 61, 12559 Berlin",
}

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


def is_home_fixture_in_berlin(home_team):
    """
    HOME team only, deliberately - this project shows fixtures PLAYED IN
    Berlin, not every fixture a Berlin club is involved in. A Berlin
    club playing away is a real match, just not one happening in Berlin.
    """
    return is_berlin_club(home_team)


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
    location = match.get("location") or {}
    venue = location.get("locationStadium") or location.get("locationCity") or ""
    group = match.get("group") or {}
    return {
        "date": kickoff.split("T")[0] if kickoff else None,
        "time": kickoff.split("T")[1][:5] if kickoff else None,
        "home_team": home,
        "away_team": away,
        "league": league.upper(),
        "league_tier": {"bl1": 1, "bl2": 2, "bl3": 3}[league],
        "gender": GENDER,
        "matchday": group.get("groupName", ""),
        "finished": bool(match.get("matchIsFinished")),
        "venue": venue,
        "venue_address": VENUE_ADDRESSES.get(venue, ""),
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
            if is_home_fixture_in_berlin(home):
                norm = normalize(m, league)
                if norm["date"]:
                    all_matches.append(norm)

    log(f"Total Berlin-related matches found: {len(all_matches)}")

    by_date = {}
    for m in all_matches:
        by_date.setdefault(m["date"], []).append(m)

    index_path = os.path.join(DATA_DIR, "index.json")
    existing_index = []
    if os.path.exists(index_path):
        with open(index_path) as f:
            existing_index = json.load(f)

    # IMPORTANT: reconcile every date this source has EVER written
    # (existing_index), not just dates that still have a match this run
    # (by_date). Otherwise a date that used to qualify - e.g. before the
    # home-only filter existed, when an away fixture counted - but no
    # longer does, never gets revisited again, and its stale openligadb
    # entry just sits in the file forever even after the filter logic
    # is fixed. This was a real bug: tightening is_home_fixture_in_berlin
    # alone didn't remove already-written away fixtures until this
    # reconciliation was added.
    today_iso = date.today().isoformat()
    candidate_dates = sorted(set(existing_index) | set(by_date))
    written_dates = []
    for d in candidate_dates:
        if d < today_iso:
            continue
        existing_path = os.path.join(DATA_DIR, f"{d}.json")
        existing = []
        if os.path.exists(existing_path):
            with open(existing_path) as f:
                existing = json.load(f)
        # merge: drop ALL prior openligadb entries for this date, then
        # add back only what THIS run actually found (empty list if none)
        merged = [x for x in existing if x.get("source") != "openligadb"] + by_date.get(d, [])
        if merged:
            with open(existing_path, "w") as f:
                json.dump(merged, f, indent=2, ensure_ascii=False)
            written_dates.append(d)
        elif os.path.exists(existing_path):
            os.remove(existing_path)  # nothing left for this date at all

    with open(index_path, "w") as f:
        json.dump(sorted(written_dates), f, indent=2)

    print(f"OpenLigaDB: wrote {len(written_dates)} date file(s), {len(all_matches)} matches total.")


if __name__ == "__main__":
    main()
