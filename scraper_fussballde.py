"""
Scrapes fussball.de for Berlin men's football below 3. Liga: Regionalliga
Nordost down through Kreisliga C (tiers 4-11).

STATUS: UNVERIFIED. fussball.de's competition/fixture pages are heavily
JS-rendered (same situation the Yorck/CinemaxX scrapers were in in
BerlinKino before those got fixed against real HTML), so this
requests-based version is a first attempt and likely needs Playwright
instead. Not wired into the scheduled workflow yet - only the manual
`debug-fussballde` Actions job touches this.

ARCHITECTURE CHANGE from the old version of this file: this used to be
one entry per *club*, hand-typed and re-typed every time coverage grew.
That doesn't scale past Berlin-Liga - Landesliga/Bezirksliga/Kreisliga
between them are hundreds of clubs, reshuffled every season by
promotion and relegation. So this version is one entry per *league
staffel* instead: each entry points at that staffel's fixture list page,
and the clubs + fixtures + venues are meant to be discovered FROM that
page by the scraper, not typed in ahead of time.

The trade-off: tiers 4-6 below still ship real, current club rosters
(carried over from before, still worth keeping as a sanity-check list
once the league-page scraper works). Tiers 7-11 intentionally do NOT
list clubs - there's no reliable way to hand-maintain that many teams,
and that was exactly the problem being solved here. Once a debug run
against a real staffel page comes back, `parse_league_page()` below is
where the actual selectors go, and it should discover every club and
fixture on that page automatically.

To help get this working:
  1. Run: python scraper_fussballde.py --debug --league "regionalliga-nordost"
  2. Paste me the output (or open an issue with it)
  3. I'll fix the parsing logic against real output, same as the Yorck fix,
     and once one league works the same selectors likely carry over to
     the rest since they're all fussball.de pages of the same type.

Run: python scraper_fussballde.py [--debug] [--league "<key>"]
"""
import json
import os
import sys
import urllib.request

DEBUG = "--debug" in sys.argv
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")

# Every fixture from this scraper is men's football - explicit so a
# gender mixup can never happen silently (see README).
GENDER = "M"

# One entry per league *staffel* (tier 4 = highest below 3. Liga).
# `url` is a best-guess fussball.de competition page and is UNVERIFIED -
# confirm/fix via --debug before trusting any of these.
# `known_clubs` is only a sanity-check list for tiers where rosters are
# stable and small enough to hand-maintain (4-6). For 7-11 it's
# deliberately empty: those clubs should come FROM the scrape, not a
# hand-typed list, because that's the part that doesn't scale.
LEAGUES = {
    "regionalliga-nordost": {
        "tier": 4,
        "label": "REGIONALLIGA NORDOST",
        "url": "https://www.fussball.de/wettbewerb/regionalliga-nordost/-",
        "known_clubs": ["BFC Dynamo", "VSG Altglienicke", "Tasmania Berlin", "Viktoria 1889 Berlin"],
    },
    "oberliga-nordost": {
        "tier": 5,
        "label": "OBERLIGA NORDOST",
        "url": "https://www.fussball.de/wettbewerb/oberliga-nordost/-",
        "known_clubs": [
            "Berliner AK 07", "SV Lichtenberg 47", "Hertha 03 Zehlendorf",
            "Tennis Borussia Berlin", "TuS Makkabi Berlin", "Eintracht Mahlsdorf",
            "SC Staaken", "SV Sparta Lichtenberg", "Füchse Berlin Reinickendorf",
        ],
    },
    "berlin-liga": {
        "tier": 6,
        "label": "BERLIN-LIGA",
        "url": "https://www.fussball.de/wettbewerb/berlin-liga/-",
        "known_clubs": [
            "Blau-Weiss 90 Berlin", "1. FC Wilmersdorf", "SC Charlottenburg",
            "Spandauer Kickers", "SSC Südwest", "Polar Pinguin", "Fortuna Biesdorf",
            "VSG Altglienicke II", "SFC Stern 1900", "SV Empor Berlin",
            "TSV Mariendorf 1897", "Frohnauer SC", "Türkiyemspor Berlin",
        ],
    },
    "landesliga-1": {
        "tier": 7,
        "label": "LANDESLIGA STAFFEL 1",
        "url": "https://www.fussball.de/wettbewerb/landesliga-1-berlin/-",
        "known_clubs": [],
    },
    "landesliga-2": {
        "tier": 7,
        "label": "LANDESLIGA STAFFEL 2",
        "url": "https://www.fussball.de/wettbewerb/landesliga-2-berlin/-",
        "known_clubs": [],
    },
    "bezirksliga-1": {
        "tier": 8,
        "label": "BEZIRKSLIGA STAFFEL 1",
        "url": "https://www.fussball.de/wettbewerb/bezirksliga-1-berlin/-",
        "known_clubs": [],
    },
    "bezirksliga-2": {
        "tier": 8,
        "label": "BEZIRKSLIGA STAFFEL 2",
        "url": "https://www.fussball.de/wettbewerb/bezirksliga-2-berlin/-",
        "known_clubs": [],
    },
    "bezirksliga-3": {
        "tier": 8,
        "label": "BEZIRKSLIGA STAFFEL 3",
        "url": "https://www.fussball.de/wettbewerb/bezirksliga-3-berlin/-",
        "known_clubs": [],
    },
    "kreisliga-a": {
        "tier": 9,
        "label": "KREISLIGA A",
        "url": "https://www.fussball.de/wettbewerb/kreisliga-a-berlin/-",
        "known_clubs": [],
    },
    "kreisliga-b": {
        "tier": 10,
        "label": "KREISLIGA B",
        "url": "https://www.fussball.de/wettbewerb/kreisliga-b-berlin/-",
        "known_clubs": [],
    },
    "kreisliga-c": {
        "tier": 11,
        "label": "KREISLIGA C",
        "url": "https://www.fussball.de/wettbewerb/kreisliga-c-berlin/-",
        "known_clubs": [],
    },
}

# Best-effort ground addresses for the tier 4-6 clubs above, same pattern
# as the cinema addresses in BerlinKino. Amateur ground addresses aren't
# as well-documented as pro stadiums - treat these as a starting point to
# verify, not a guaranteed-correct source. Tiers 7-11 have no hand-typed
# addresses at all: those need to come from whatever venue info the real
# fussball.de fixture page exposes, once the scraper is working.
VENUE_ADDRESSES = {
    "Sportforum Berlin": "Conrad-Blenkle-Straße 33, 13405 Berlin",
    "Sportpark Altglienicke": "Rudolf-Seiffert-Straße 30, 12524 Berlin",
    "Werner-Seelenbinder-Sportpark": "Oderstraße 182, 12049 Berlin",
    "Poststadion": "Rathenower Str. 42, 10559 Berlin",
    "Mommsenstadion": "Waldschulallee 34, 14055 Berlin",
    "Rehwiese": "Potsdamer Chaussee 4, 14109 Berlin",
    "Stadion Reinickendorf": "Egellsstraße, 13407 Berlin",
    "Stadion Staaken": "Reimerweg 30, 13593 Berlin",
    "Poststadion Nebenplatz": "Rathenower Str. 42, 10559 Berlin",
    "Stadion Rathenower Straße": "Rathenower Str. 42, 10559 Berlin",
    "Sportplatz Mariendorf": "Motzener Straße 20, 12277 Berlin",
}


def log(*args):
    if DEBUG:
        print(*args)


def fetch_page(url):
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; berlin-football-fixtures/1.0; +https://github.com)"
        },
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        return resp.read().decode("utf-8", errors="replace")


def parse_league_page(html, league_key, league_info):
    """
    Meant to pull every fixture (with clubs, kickoff, venue) out of one
    staffel's fussball.de page. NOT YET IMPLEMENTED - the real markup is
    needed first (see module docstring / --debug instructions). Returns
    [] until then so this scraper fails safe instead of guessing.
    """
    log(f"  parse_league_page() has no real selectors yet for {league_key} - "
        f"send a --debug output for this league so it can be written.")
    return []


def main():
    league_filter = None
    if "--league" in sys.argv:
        league_filter = sys.argv[sys.argv.index("--league") + 1]

    leagues = {league_filter: LEAGUES.get(league_filter)} if league_filter else LEAGUES

    if not DEBUG:
        print(
            "This scraper is unverified against live fussball.de pages.\n"
            "Run with --debug --league \"<key>\" first (see LEAGUES for valid "
            "keys) and share the output before relying on this for real data."
        )
        return

    for key, info in leagues.items():
        if not info:
            log(f"No entry configured for '{key}', skipping.")
            continue
        log(f"Fetching {info['url']} ({info['label']}, tier {info['tier']})")
        try:
            html = fetch_page(info["url"])
            log(f"  got {len(html)} bytes")
            log(f"  first 500 chars:\n{html[:500]}")
            log("  --- send this output back so the real parsing logic can be written ---")
            fixtures = parse_league_page(html, key, info)
            log(f"  parsed {len(fixtures)} fixture(s)")
        except Exception as e:
            log(f"  failed: {e}")


if __name__ == "__main__":
    main()
