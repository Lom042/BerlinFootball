"""
Scrapes fussball.de for Berlin clubs in Regionalliga Nordost and below
(BFC Dynamo, Viktoria 1889 Berlin, Tennis Borussia Berlin, VSG Altglienicke,
and all the way down to Kreisliga level).

STATUS: UNVERIFIED. fussball.de's fixture pages are heavily JS-rendered
(similar situation to the Yorck/CinemaxX scrapers in BerlinKino), so this
requests-based version is a first attempt and likely needs Playwright
instead. Not wired into the scheduled workflow yet.

To help get this working:
  1. Run: python scraper_fussballde.py --debug --club "BFC Dynamo"
  2. Paste me the output (or open an issue with it)
  3. I'll fix the parsing logic against real output, same as the Yorck fix

Run: python scraper_fussballde.py [--debug] [--club "Club Name"]
"""
import json
import os
import sys
import urllib.request

DEBUG = "--debug" in sys.argv
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")

# Berlin clubs to track below 3. Liga, organized by division. This is
# organized league football only (deliberately excludes pub/five-a-side
# teams). Built from the current 2026-27 season rosters where available;
# promotion/relegation shifts clubs between these lists every summer, so
# this needs a re-check each season. Add more here as coverage expands -
# each needs its real fussball.de club slug confirmed via a debug run
# (slugs below are best-guess and unverified).
BERLIN_LOWER_LEAGUE_CLUBS = {
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

    # Berlin-Liga (tier 6, Berlin-only)
    "Blau-Weiss 90 Berlin": ("blau-weiss-90-berlin", "BERLIN-LIGA"),
    "1. FC Wilmersdorf": ("1-fc-wilmersdorf", "BERLIN-LIGA"),
    "SC Charlottenburg": ("sc-charlottenburg", "BERLIN-LIGA"),
    "Spandauer Kickers": ("fsv-spandauer-kickers", "BERLIN-LIGA"),
    "SSC Südwest": ("ssc-suedwest-berlin", "BERLIN-LIGA"),
    "Polar Pinguin": ("polar-pinguin-berlin", "BERLIN-LIGA"),
    "Fortuna Biesdorf": ("fortuna-biesdorf", "BERLIN-LIGA"),
    "VSG Altglienicke II": ("vsg-altglienicke-ii", "BERLIN-LIGA"),
    "SFC Stern 1900": ("sfc-stern-1900", "BERLIN-LIGA"),
    "SV Empor Berlin": ("sv-empor-berlin", "BERLIN-LIGA"),
    "TSV Mariendorf 1897": ("tsv-mariendorf-1897", "BERLIN-LIGA"),
    "Frohnauer SC": ("frohnauer-sc", "BERLIN-LIGA"),
    "Türkiyemspor Berlin": ("tuerkiyemspor-berlin", "BERLIN-LIGA"),
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


def main():
    club_filter = None
    if "--club" in sys.argv:
        club_filter = sys.argv[sys.argv.index("--club") + 1]

    clubs = {club_filter: BERLIN_LOWER_LEAGUE_CLUBS.get(club_filter)} if club_filter else BERLIN_LOWER_LEAGUE_CLUBS

    if not DEBUG:
        print(
            "This scraper is unverified against live fussball.de pages.\n"
            "Run with --debug --club \"<name>\" first and share the output "
            "before relying on this for real data."
        )
        return

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


if __name__ == "__main__":
    main()
