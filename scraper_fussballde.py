"""
Scrapes Berlin football below 3. Liga:
  - Regionalliga Nordost + NOFV-Oberliga Nord: named Berlin clubs only
    (these leagues span multiple German states)
  - Berlin-Liga, Landesliga (2 staffeln), Bezirksliga (3 staffeln):
    Berlin-only competitions, so every team in the staffel table is
    pulled automatically instead of hand-typed
  - Berliner Landespokal (the Berlin Cup): a separate knockout
    competition, not a league season, so it needs its own fetch. This
    is the piece that was missing - on cup weekends, clubs don't play
    their normal league fixture, so a site that only reads league
    tables shows nothing at all that day even though there are 60+
    cup matches happening. 178 clubs enter this season, from
    Regionalliga Nordost down to Kreisliga C.

STATUS: UNVERIFIED. Both source sites are JS-rendered (similar situation
to the Yorck/CinemaxX scrapers in BerlinKino), so this requests-based
version is a first attempt and likely needs Playwright instead.

To help get this working:
  1. Run: python scraper_fussballde.py --debug --club "BFC Dynamo"
     (checks the hand-typed regional clubs)
  2. Run: python scraper_fussballde.py --debug --staffel landesliga-1
     (checks the full-staffel pull for a Berlin-only league)
  3. Run: python scraper_fussballde.py --debug --pokal
     (checks the Landespokal Berlin cup fetch)
  4. Paste me the output (or open an issue with it)
  5. I'll fix the parsing logic against real output, same as the Yorck fix

Run: python scraper_fussballde.py [--debug] [--club "Name"] [--staffel <slug>] [--pokal]
"""
import json
import os
import sys
import urllib.request

DEBUG = "--debug" in sys.argv
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")

# Berlin clubs to track in Regionalliga Nordost / Oberliga Nord — these
# leagues span multiple German states, so only named Berlin clubs apply.
# Promotion/relegation reshuffles this every summer; re-check each season.
BERLIN_REGIONAL_CLUBS = {
    # Regionalliga Nordost (tier 4)
    "BFC Dynamo": ("bfc-dynamo-berlin", "REGIONALLIGA NORDOST"),
    "VSG Altglienicke": ("vsg-altglienicke", "REGIONALLIGA NORDOST"),
    "Tasmania Berlin": ("sv-tasmania-berlin", "REGIONALLIGA NORDOST"),

    # NOFV-Oberliga Nord (tier 5)
    "Berliner AK 07": ("berliner-ak-07", "OBERLIGA NORDOST"),
    "SV Lichtenberg 47": ("sv-lichtenberg-47", "OBERLIGA NORDOST"),
    "Hertha 03 Zehlendorf": ("hertha-03-zehlendorf", "OBERLIGA NORDOST"),
    "Tennis Borussia Berlin": ("tennis-borussia-berlin", "OBERLIGA NORDOST"),
    "TuS Makkabi Berlin": ("tus-makkabi-berlin", "OBERLIGA NORDOST"),
    "Eintracht Mahlsdorf": ("eintracht-mahlsdorf", "OBERLIGA NORDOST"),
    "SC Staaken": ("sc-staaken", "OBERLIGA NORDOST"),
    "SV Sparta Lichtenberg": ("sv-sparta-lichtenberg", "OBERLIGA NORDOST"),
    "Füchse Berlin Reinickendorf": ("fuechse-berlin-reinickendorf", "OBERLIGA NORDOST"),
}

# Berlin-only leagues: pull every team from the full staffel table instead
# of naming clubs individually — every club entered is automatically in
# scope. berliner-fussball.de/fussball.de slugs below are best-guess and
# unverified — confirm with --staffel <slug> --debug.
BERLIN_ONLY_STAFFELN = {
    "berlin-liga": "BERLIN-LIGA",
    "landesliga-1": "LANDESLIGA STAFFEL 1",
    "landesliga-2": "LANDESLIGA STAFFEL 2",
    "bezirksliga-1": "BEZIRKSLIGA STAFFEL 1",
    "bezirksliga-2": "BEZIRKSLIGA STAFFEL 2",
    "bezirksliga-3": "BEZIRKSLIGA STAFFEL 3",
}

# The Berliner Landespokal (Berlin Cup) — a knockout competition, not a
# league season. URL slug is best-guess/unverified pending a debug run.
LANDESPOKAL_URL = "https://www.fussball.de/wettbewerb/berlin-pokal-herren-berlin/-/staffel/berlin-pokal-2026-27"


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


def debug_club(club_filter):
    clubs = {club_filter: BERLIN_REGIONAL_CLUBS.get(club_filter)} if club_filter else BERLIN_REGIONAL_CLUBS
    for name, entry in clubs.items():
        if not entry:
            log(f"No entry configured for '{name}', skipping.")
            continue
        slug, league = entry
        url = f"https://www.fussball.de/verein/{slug}/-"
        log(f"Fetching {url} ({league})")
        try:
            html = fetch_page(url)
            log(f"  got {len(html)} bytes")
            log(f"  first 500 chars:\n{html[:500]}")
            log("  --- send this output back so the real parsing logic can be written ---")
        except Exception as e:
            log(f"  failed: {e}")


def debug_staffel(staffel_slug):
    league = BERLIN_ONLY_STAFFELN.get(staffel_slug)
    if not league:
        log(f"Unknown staffel slug '{staffel_slug}'. Options: {list(BERLIN_ONLY_STAFFELN)}")
        return
    # Placeholder URL pattern - real slug/path needs confirming against
    # the live site structure via this debug run.
    url = f"https://www.fussball.de/spieltag/{staffel_slug}-berlin/-/staffel/{staffel_slug}"
    log(f"Fetching {url} ({league})")
    try:
        html = fetch_page(url)
        log(f"  got {len(html)} bytes")
        log(f"  first 800 chars:\n{html[:800]}")
        log("  --- send this output back so the full-staffel parsing logic can be written ---")
    except Exception as e:
        log(f"  failed: {e}")


def debug_pokal():
    log(f"Fetching {LANDESPOKAL_URL} (LANDESPOKAL BERLIN)")
    try:
        html = fetch_page(LANDESPOKAL_URL)
        log(f"  got {len(html)} bytes")
        log(f"  first 800 chars:\n{html[:800]}")
        log("  --- send this output back so the cup-round parsing logic can be written ---")
        log("  Note: cup rounds need a 'round' label (e.g. 'Round 3') instead of a matchday number,")
        log("  and lower-tier clubs host higher-tier ones up to the quarter-final, so don't assume")
        log("  home_team is always the 'bigger' club.")
    except Exception as e:
        log(f"  failed: {e}")


def main():
    if not DEBUG:
        print(
            "This scraper is unverified against live fussball.de pages.\n"
            "Run with --debug (plus --club / --staffel / --pokal) first "
            "and share the output before relying on this for real data."
        )
        return

    if "--pokal" in sys.argv:
        debug_pokal()
        return

    if "--staffel" in sys.argv:
        debug_staffel(sys.argv[sys.argv.index("--staffel") + 1])
        return

    club_filter = None
    if "--club" in sys.argv:
        club_filter = sys.argv[sys.argv.index("--club") + 1]
    debug_club(club_filter)


if __name__ == "__main__":
    main()
