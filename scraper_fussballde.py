"""
Scrapes fussball.de for Berlin men's football below 3. Liga: Regionalliga
Nordost down through Kreisliga C (tiers 4-11).

STATUS as of the first real debug run against "regionalliga-nordost":
the page IS server-rendered (not a JS shell - no Playwright needed) and
DOES contain real fixture data: match IDs, home/away team names+links,
and one date per match-block, all reachable via distinctive, stable
URL patterns in the raw HTML (`/mannschaft/.../team-id/...`,
`/spiel/.../spiel/<MATCHID>`, `.../spieldatum/YYYY-MM-DD/staffel/...`).
`parse_league_page()` below extracts fixtures using those URL patterns
via stdlib `html.parser` rather than guessing at CSS classes, since
those patterns should survive a markup redesign better than class names
would.

Known gaps, both confirmed against the live "regionalliga-nordost" page
at time of writing:
  - No kickoff TIME or VENUE on the listing page itself - only date.
    Getting those would mean fetching every individual
    `/spiel/.../spiel/<MATCHID>` detail page, one request per fixture,
    which this first pass deliberately doesn't do yet (see TIME/VENUE
    note in normalize_fixture()).
  - fussball.de was showing a site-wide "technische Probleme" (technical
    issues) banner and the schedule was flagged "vorläufige Spiele"
    (provisional, not yet approved by the league admin) - scores were
    all blank for that reason, which is expected pre-season, not a
    parsing bug.

Only "regionalliga-nordost" has a CONFIRMED real URL (found via search,
since fussball.de uses long opaque per-season competition IDs, not
guessable slugs). The other ten leagues below still have GUESSED
placeholder URLs and are marked `"verified": False` - each one needs
the same treatment: search "<league name> fussball.de Spielplan", grab
the real `/spielplan/.../staffel/<ID>-G` URL, verified via
--debug --league "<key>" the same way regionalliga-nordost was
confirmed, then flip its `"verified"` flag to True.

Run: python scraper_fussballde.py [--debug] [--league "<key>"]
  --debug        fetch + parse and print a summary, but never write data/
  (no flags)     fetch + parse + write data/ for every "verified" league
"""
import json
import os
import re
import sys
import urllib.request
from datetime import date
from html.parser import HTMLParser

DEBUG = "--debug" in sys.argv
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")

# Every fixture from this scraper is men's football - explicit so a
# gender mixup can never happen silently (see README).
GENDER = "M"

# Substring markers used to keep only fixtures involving a Berlin club.
# Broader than just "Berlin" because several Berlin clubs don't have
# "Berlin" in their name at all - either a historic name (BFC Dynamo,
# BFC Preussen), or a Berlin-district name used instead of the city name
# (e.g. fussball.de may list "Reinickendorfer Füchse" rather than
# "Füchse Berlin Reinickendorf", "SV Lichtenberg" rather than "... Berlin
# Lichtenberg"). District names below are all real districts/localities
# of clubs already tracked in this file's known_clubs lists - added
# proactively so lower-tier leagues don't silently miss a club just
# because of which name variant the page happens to use.
BERLIN_MARKERS = [
    "Berlin", "Hertha", "Union", "BFC",
    "Lichtenberg", "Zehlendorf", "Mahlsdorf", "Staaken", "Reinickendorf",
    "Wilmersdorf", "Charlottenburg", "Spandau", "Biesdorf", "Altglienicke",
    "Mariendorf", "Frohnau",
]

# One entry per league *staffel* (tier 4 = highest below 3. Liga).
# `known_clubs` is only a sanity-check list for tiers where rosters are
# stable and small enough to hand-maintain (4-6) - it plays no part in
# filtering anymore, that's BERLIN_MARKERS' job now. For 7-11 it's
# deliberately empty: those clubs come FROM the scrape, not a hand-typed
# list, because that's the part that doesn't scale.
LEAGUES = {
    "regionalliga-nordost": {
        "tier": 4,
        "label": "REGIONALLIGA NORDOST",
        "url": "https://www.fussball.de/spielplan/regionalliga-nordost-deutschland-regionalliga-nordost-herren-saison2627-deutschland/-/staffel/0316DK36HK000009VS5489BUVSBBVPEU-G",
        "verified": True,
        "known_clubs": [
            "BFC Dynamo", "VSG Altglienicke", "Tasmania Berlin", "BFC Preussen",
            "Hertha BSC II",
        ],
    },
    "oberliga-nordost": {
        "tier": 5,
        "label": "OBERLIGA NORDOST",
        # Real URL found via search (Oberliga Nordost splits into Nord/
        # Süd staffeln - Berlin's clubs are in Nord). Search turned up a
        # "/spieltag/" (single matchday) link rather than "/spielplan/"
        # (full season) - swapped to the full-season path, same staffel
        # ID, matching the URL shape that worked for regionalliga-nordost.
        # Not yet confirmed against a --debug run, still unverified.
        "url": "https://www.fussball.de/spielplan/nofv-oberliga-nord-deutschland-oberliga-herren-saison2627-deutschland/-/staffel/0316DLRBJC00000AVS5489BUVSBBVPEU-G",
        "verified": False,
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
        "verified": False,
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
        "verified": False,
        "known_clubs": [],
    },
    "landesliga-2": {
        "tier": 7,
        "label": "LANDESLIGA STAFFEL 2",
        "url": "https://www.fussball.de/wettbewerb/landesliga-2-berlin/-",
        "verified": False,
        "known_clubs": [],
    },
    "bezirksliga-1": {
        "tier": 8,
        "label": "BEZIRKSLIGA STAFFEL 1",
        "url": "https://www.fussball.de/wettbewerb/bezirksliga-1-berlin/-",
        "verified": False,
        "known_clubs": [],
    },
    "bezirksliga-2": {
        "tier": 8,
        "label": "BEZIRKSLIGA STAFFEL 2",
        "url": "https://www.fussball.de/wettbewerb/bezirksliga-2-berlin/-",
        "verified": False,
        "known_clubs": [],
    },
    "bezirksliga-3": {
        "tier": 8,
        "label": "BEZIRKSLIGA STAFFEL 3",
        "url": "https://www.fussball.de/wettbewerb/bezirksliga-3-berlin/-",
        "verified": False,
        "known_clubs": [],
    },
    "kreisliga-a": {
        "tier": 9,
        "label": "KREISLIGA A",
        "url": "https://www.fussball.de/wettbewerb/kreisliga-a-berlin/-",
        "verified": False,
        "known_clubs": [],
    },
    "kreisliga-b": {
        "tier": 10,
        "label": "KREISLIGA B",
        "url": "https://www.fussball.de/wettbewerb/kreisliga-b-berlin/-",
        "verified": False,
        "known_clubs": [],
    },
    "kreisliga-c": {
        "tier": 11,
        "label": "KREISLIGA C",
        "url": "https://www.fussball.de/wettbewerb/kreisliga-c-berlin/-",
        "verified": False,
        "known_clubs": [],
    },
}

# Best-effort ground addresses for the tier 4-6 clubs above, same pattern
# as the cinema addresses in BerlinKino. Amateur ground addresses aren't
# as well-documented as pro stadiums - treat these as a starting point to
# verify, not a guaranteed-correct source. Keyed by club name since venue
# isn't available from the listing page itself yet (see module docstring).
VENUE_ADDRESSES_BY_CLUB = {
    "BFC Dynamo": ("Sportforum Berlin", "Conrad-Blenkle-Straße 33, 13405 Berlin"),
    "VSG Altglienicke": ("Sportpark Altglienicke", "Rudolf-Seiffert-Straße 30, 12524 Berlin"),
    "Tasmania Berlin": ("Werner-Seelenbinder-Sportpark", "Oderstraße 182, 12049 Berlin"),
    "Berliner AK 07": ("Poststadion", "Rathenower Str. 42, 10559 Berlin"),
    "SV Lichtenberg 47": ("Poststadion", "Rathenower Str. 42, 10559 Berlin"),
    "Tennis Borussia Berlin": ("Mommsenstadion", "Waldschulallee 34, 14055 Berlin"),
    "TuS Makkabi Berlin": ("Mommsenstadion", "Waldschulallee 34, 14055 Berlin"),
    "Hertha 03 Zehlendorf": ("Rehwiese", "Potsdamer Chaussee 4, 14109 Berlin"),
    "Füchse Berlin Reinickendorf": ("Stadion Reinickendorf", "Egellsstraße, 13407 Berlin"),
    "SC Staaken": ("Stadion Staaken", "Reimerweg 30, 13593 Berlin"),
    "Blau-Weiss 90 Berlin": ("Poststadion Nebenplatz", "Rathenower Str. 42, 10559 Berlin"),
    "SC Charlottenburg": ("Mommsenstadion", "Waldschulallee 34, 14055 Berlin"),
    "Türkiyemspor Berlin": ("Stadion Rathenower Straße", "Rathenower Str. 42, 10559 Berlin"),
    "TSV Mariendorf 1897": ("Sportplatz Mariendorf", "Motzener Straße 20, 12277 Berlin"),
}

MANNSCHAFT_RE = re.compile(r"/mannschaft/[^\"'/]+/-/saison/\d+/team-id/([A-Za-z0-9]+)")
SPIEL_RE = re.compile(r"/spiel/[^\"'/]+/-/spiel/([A-Za-z0-9]+)")
SPIELDATUM_RE = re.compile(r"/spieldatum/(\d{4}-\d{2}-\d{2})/")


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


def clean_team_name(text):
    """
    Team link text on the listing page repeats the club name twice back
    to back (logo <a> + text <a>, e.g. "BFC Dynamo BFC Dynamo") - this
    collapses that back down to one clean name.
    """
    text = " ".join(text.split())
    words = text.split(" ")
    half = len(words) // 2
    if half and words[:half] == words[half:]:
        return " ".join(words[:half])
    return text


def is_berlin_fixture(home, away):
    """
    HOME team only, deliberately - this project shows fixtures being
    PLAYED IN Berlin, not every fixture a Berlin club is involved in.
    A Berlin club playing away (e.g. at a club elsewhere in Brandenburg
    or further out) is a real game, just not one happening in Berlin, so
    it's left out here rather than shown as if it were a local match.
    """
    return any(marker in home for marker in BERLIN_MARKERS)


class FixtureListParser(HTMLParser):
    """
    Walks the raw HTML in document order and reconstructs fixtures from
    three stable URL patterns rather than CSS classes (see module
    docstring for why): team links, per-fixture match-detail links, and
    the one date link at the start of each matchday block.
    """

    def __init__(self):
        super().__init__()
        self.current_date = None
        self.pending_teams = []  # [(href, text), ...] - collapsed, de-duped
        self.fixtures = []
        self._in_a = False
        self._a_href = ""
        self._a_text_parts = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "a":
            self._in_a = True
            self._a_href = attrs.get("href", "") or ""
            self._a_text_parts = []
            m = SPIELDATUM_RE.search(self._a_href)
            if m:
                self.current_date = m.group(1)
        elif tag == "img" and self._in_a:
            alt = attrs.get("alt")
            if alt:
                self._a_text_parts.append(alt)

    def handle_data(self, data):
        if self._in_a:
            self._a_text_parts.append(data)

    def handle_endtag(self, tag):
        if tag != "a" or not self._in_a:
            return
        href = self._a_href
        text = clean_team_name("".join(self._a_text_parts))
        self._in_a = False

        if MANNSCHAFT_RE.search(href):
            # De-dupe the logo-link + text-link pair that point at the
            # same team (same href appearing twice in a row).
            if not (self.pending_teams and self.pending_teams[-1][0] == href):
                self.pending_teams.append((href, text))
            return

        m = SPIEL_RE.search(href)
        if m and len(self.pending_teams) >= 2:
            match_id = m.group(1)
            (_, home_text), (_, away_text) = self.pending_teams[-2:]
            self.fixtures.append({
                "date": self.current_date,
                "home_team": home_text,
                "away_team": away_text,
                "match_id": match_id,
                "match_url": href if href.startswith("http") else f"https://www.fussball.de{href}",
            })
            self.pending_teams = []


def parse_league_page(html, league_key, league_info):
    parser = FixtureListParser()
    try:
        parser.feed(html)
    except Exception as e:
        log(f"  HTML parse error: {e}")
        return []
    return parser.fixtures


def normalize_fixture(raw, league_key, league_info):
    venue, venue_address = "", ""
    for club, (v, addr) in VENUE_ADDRESSES_BY_CLUB.items():
        if club in raw["home_team"]:
            venue, venue_address = v, addr
            break
    return {
        "date": raw["date"],
        # TIME/VENUE: not present on the listing page (see module
        # docstring) - would need one extra HTTP request per fixture to
        # each match's own page, not done in this pass. venue/address
        # above are a same-club guess from the home team's usual ground,
        # not confirmed for this specific fixture.
        "time": None,
        "home_team": raw["home_team"],
        "away_team": raw["away_team"],
        "league": league_info["label"],
        "league_tier": league_info["tier"],
        "gender": GENDER,
        "matchday": "",
        "venue": venue,
        "venue_address": venue_address,
        "source": "fussballde",
        "source_url": raw["match_url"],
    }


def collect_league(key, info):
    log(f"Fetching {info['url']} ({info['label']}, tier {info['tier']})")
    try:
        html = fetch_page(info["url"])
    except Exception as e:
        log(f"  failed: {e}")
        return []
    log(f"  got {len(html)} bytes")
    raw_fixtures = parse_league_page(html, key, info)
    log(f"  parsed {len(raw_fixtures)} total fixture(s) on the page")
    berlin_fixtures = [
        normalize_fixture(f, key, info)
        for f in raw_fixtures
        if is_berlin_fixture(f["home_team"], f["away_team"]) and f["date"]
    ]
    log(f"  {len(berlin_fixtures)} involve a Berlin club:")
    for f in berlin_fixtures[:10]:
        log(f"    {f['date']}  {f['home_team']} vs {f['away_team']}  ({f['league']})")
    return berlin_fixtures


def write_fixtures(all_fixtures):
    os.makedirs(DATA_DIR, exist_ok=True)
    by_date = {}
    for f in all_fixtures:
        by_date.setdefault(f["date"], []).append(f)

    index_path = os.path.join(DATA_DIR, "index.json")
    existing_index = []
    if os.path.exists(index_path):
        with open(index_path) as fh:
            existing_index = json.load(fh)

    # IMPORTANT: reconcile every date this source has EVER written
    # (existing_index), not just dates with a match this run (by_date).
    # Otherwise a date that used to qualify (e.g. before the home-only
    # filter) but no longer does never gets revisited, and its stale
    # fussballde entry sits in the file forever - same bug class as
    # scraper_openligadb.py had, fixed the same way here.
    candidate_dates = sorted(set(existing_index) | set(by_date))
    written = []
    for d in candidate_dates:
        path = os.path.join(DATA_DIR, f"{d}.json")
        existing = []
        if os.path.exists(path):
            with open(path) as fh:
                existing = json.load(fh)
        merged = [x for x in existing if x.get("source") != "fussballde"] + by_date.get(d, [])
        if merged:
            with open(path, "w") as fh:
                json.dump(merged, fh, indent=2, ensure_ascii=False)
            written.append(d)
        elif os.path.exists(path):
            os.remove(path)

    with open(index_path, "w") as fh:
        json.dump(sorted(written), fh, indent=2)
    return written


def main():
    league_filter = None
    if "--league" in sys.argv:
        league_filter = sys.argv[sys.argv.index("--league") + 1]

    leagues = {league_filter: LEAGUES.get(league_filter)} if league_filter else LEAGUES

    all_fixtures = []
    for key, info in leagues.items():
        if not info:
            log(f"No entry configured for '{key}', skipping.")
            continue
        if not DEBUG and not info.get("verified"):
            log(f"Skipping '{key}' - URL not yet verified (run --debug --league \"{key}\" first).")
            continue
        all_fixtures.extend(collect_league(key, info))

    if DEBUG:
        print(f"\nTotal Berlin fixtures parsed across requested league(s): {len(all_fixtures)}")
        return

    written = write_fixtures(all_fixtures)
    print(f"fussball.de: wrote {len(written)} date file(s), {len(all_fixtures)} Berlin fixture(s) total.")


if __name__ == "__main__":
    main()
