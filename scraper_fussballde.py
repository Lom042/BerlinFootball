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

# Berlin clubs to track in Regionalliga Nordost / Oberliga / Kreisliga.
# Add more here as coverage expands - each needs its fussball.de club slug.
BERLIN_LOWER_LEAGUE_CLUBS = {
    "BFC Dynamo": "bfc-dynamo-berlin",
    "Viktoria 1889 Berlin": "viktoria-1889-berlin",
    "Tennis Borussia Berlin": "tennis-borussia-berlin",
    "VSG Altglienicke": "vsg-altglienicke",
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

    for name, slug in clubs.items():
        if not slug:
            log(f"No slug configured for '{name}', skipping.")
            continue
        url = f"https://www.fussball.de/verein/{slug}/-"
        log(f"Fetching {url}")
        try:
            html = fetch_page(url)
            log(f"  got {len(html)} bytes")
            log(f"  first 500 chars:\n{html[:500]}")
            log("  --- send this output back so the real parsing logic can be written ---")
        except Exception as e:
            log(f"  failed: {e}")


if __name__ == "__main__":
    main()
