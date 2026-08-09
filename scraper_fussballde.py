"""
Scrapes fussball.de for Berlin men's football below 3. Liga: Regionalliga
Nordost down through Landesliga (tiers 4-7), plus two cup competitions
(DFB-Pokal and the Berlin Landespokal - see CUPS below).

Deliberately stops at Landesliga rather than continuing into Bezirksliga/
Kreisliga (tiers 8-11) - see the note above the LEAGUES dict for why.

CUPS ARE STRUCTURALLY DIFFERENT FROM LEAGUES - worth understanding before
touching CUPS below. A league staffel is one flat table covering the
whole season. A cup competition is a knockout: several separate rounds
(Qualifikation, 1. Hauptrunde, Achtelfinale, ...), each its own staffel
page with its own ID, drawn one round at a time as the previous round
finishes. There's no single page listing every round's fixtures at once.

The competition-level URL (ending `-C`, e.g. the one under "DFB-Pokal" in
the site's own league picker) isn't itself a fixture list - fetching it
redirects (a real HTTP redirect, which Python's urllib follows
automatically) to whichever round is CURRENTLY active, ending `-R`
instead. That means CUPS entries below can just point at the stable `-C`
URL and this file never needs to know or track which round is live -
fussball.de's own redirect handles that for us, every single run. No
extra "find the next round" logic needed.

Confirmed at time of writing: both cups' current round has zero fixtures
because this season's draw hasn't been published yet ("Leider wurden zu
deiner Eingabe keine Treffer gefunden" on the page) - that's expected,
not a bug. `collect_league()` handles an empty page the same as any
other: zero raw fixtures in, zero written out. Once each competition's
first-round draw is published, real fixtures should start appearing on
the next scheduled run with no code change required.

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

KNOWN BUG, FOUND AND FIXED (real user report - worth understanding since
it's a subtle one): the listing page's "Datum | Zeit" column is only
populated with a real date link for a handful of near-term matchdays -
most matchday blocks, especially further into the season, have a
completely BLANK date cell in the initial HTML (no text, no link at
all - presumably filled in client-side for a "load more" view this
scraper never triggers). The original version of this file assumed
every matchday block carried its own date link and fell back to
"carry forward the last date seen" for rows without one - so once it
hit a blank stretch, EVERY fixture in that stretch silently got
stamped with whichever real date happened to appear earlier in the
document. On a page with only one real date link on it (which is
common for the less-imminent leagues), that meant literally every
fixture returned the same date - which is exactly what surfaced as
"all of Tennis Borussia's fixtures show Sun 04 Oct" on the live site.

FIX: stop trusting the listing page for date entirely. Fetch each
Berlin-home fixture's own `/spiel/.../spiel/<MATCHID>` detail page
instead (fetch_match_detail() below) - every match page reliably has
its own real date (via a breadcrumb link back to its matchday), its
real kickoff time ("Anpfiff HH:MM Uhr"), and a Google Maps link with
its exact venue + street address, all as plain text/hrefs regardless
of how blank the listing page's date column was. This also incidentally
delivers the real kickoff time and a real per-fixture venue address,
both previously deferred as "would need a per-match fetch, not done in
this pass" - since that fetch was already unavoidable to get a
trustworthy date, it made no sense not to pull time/venue from the same
page while we're there. Costs one extra HTTP request per Berlin-home
fixture per run (a few dozen to ~150 today) - acceptable for a job that
only runs twice a day, with a short pause between requests below so
it's not hammering fussball.de.

Also confirmed on the live pages at time of writing: fussball.de was
showing a site-wide "technische Probleme" (technical issues) banner and
the schedule was flagged "vorläufige Spiele" (provisional, not yet
approved by the league admin) - scores were blank for that reason,
which is expected pre-season, not a parsing bug.

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
import time as time_module
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
    "Berlin", "Hertha", "Union Berlin", "BFC",
    "Lichtenberg", "Zehlendorf", "Mahlsdorf", "Staaken", "Reinickendorf",
    "Wilmersdorf", "Charlottenburg", "Spandau", "Biesdorf", "Altglienicke",
    "Mariendorf", "Frohnau",
]
# NOTE: "Union" on its own is deliberately NOT a marker - it's an
# extremely common generic name fragment in German amateur football
# (e.g. "SG Union Klosterfelde" in Brandenburg, nothing to do with
# Berlin). A real false positive from bare "Union" showed up the first
# time this ran against Oberliga Nordost - "Union Berlin" is specific
# enough to still catch 1. FC Union Berlin without that risk.

# One entry per league *staffel* (tier 4 = highest below 3. Liga).
# `known_clubs` is only a sanity-check list for tiers where rosters are
# stable and small enough to hand-maintain (4-6) - it plays no part in
# filtering anymore, that's BERLIN_MARKERS' job now. Landesliga (tier 7)
# leaves it empty: those clubs come FROM the scrape, not a hand-typed
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
        # Confirmed via --debug: real season data, 84 Berlin home
        # fixtures after fixing the "Union" false-positive marker.
        "url": "https://www.fussball.de/spielplan/nofv-oberliga-nord-deutschland-oberliga-herren-saison2627-deutschland/-/staffel/0316DLRBJC00000AVS5489BUVSBBVPEU-G",
        "verified": True,
        "known_clubs": [
            "Berliner AK 07", "SV Lichtenberg 47", "Hertha 03 Zehlendorf",
            "Tennis Borussia Berlin", "TuS Makkabi Berlin", "Eintracht Mahlsdorf",
            "SC Staaken", "SV Sparta Lichtenberg", "Füchse Berlin Reinickendorf",
        ],
    },
    "berlin-liga": {
        "tier": 6,
        "label": "BERLIN-LIGA",
        # Confirmed via --debug: 269 Berlin home fixtures, dates vary
        # correctly across the season, real clubs match the known list.
        "url": "https://www.fussball.de/spielplan/herren-berlin-liga-berlin-berlin-liga-herren-saison2627-berlin/-/staffel/0317AFL2VO000008VS5489BUVSBBVPEU-G",
        "verified": True,
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
        # Confirmed via --debug: 105 Berlin home fixtures, dates vary
        # correctly across the season, real Landesliga clubs.
        "url": "https://www.fussball.de/spielplan/herren-landesliga-st1-berlin-landesliga-herren-saison2627-berlin/-/staffel/0317AFVR84000006VS5489BUVSBBVPEU-G",
        "verified": True,
        "known_clubs": [],
    },
    "landesliga-2": {
        "tier": 7,
        "label": "LANDESLIGA STAFFEL 2",
        # Confirmed via --debug: 75 Berlin home fixtures, dates vary
        # correctly across the season, real Landesliga clubs.
        "url": "https://www.fussball.de/spielplan/herren-landesliga-st2-berlin-landesliga-herren-saison2627-berlin/-/staffel/0317AFVREC000003VS5489BUVSBBVPEU-G",
        "verified": True,
        "known_clubs": [],
    },
}

# DELIBERATELY NOT GOING BELOW TIER 7 (Landesliga). Bezirksliga (tier 8)
# alone is 3 separate staffeln in Berlin, and Kreisliga A/B/C (tiers
# 9-11) split into even more - at least 4 groups for Kreisliga A alone -
# each one its own staffel needing its own real URL found and verified.
# Weighed the effort against the payoff and decided Landesliga is a
# sensible floor for this project: still real organized league football,
# without chasing a dozen+ small district groups. If this ever changes,
# the pattern for adding a new staffel is the same as every entry above:
# find its real "/spielplan/.../staffel/<ID>-G" URL (via WebSearch, or a
# known club's team page for the current season, since fussball.de's own
# league browser is a JS dropdown that can't be queried directly), add
# it here with `verified: False`, confirm via
# `--debug --league "<key>"`, then flip to True.

# Cup competitions - see the "CUPS ARE STRUCTURALLY DIFFERENT" module
# docstring section above before touching this. `url` is the STABLE
# competition-level "-C" page for each cup, which fussball.de redirects
# to whichever round is currently active - not a specific round's page,
# so this dict never needs manual updates as the tournament progresses.
# `tier` here is a display/sort weight, not a real league tier (cups
# aren't part of the pyramid) - both sit ahead of Bundesliga so they
# stand out, and `is_cup: True` tells the frontend to show a "CUP" tag
# instead of a nonsensical "Tier 0".
CUPS = {
    "dfb-pokal": {
        "tier": 0,
        "label": "DFB-POKAL",
        "is_cup": True,
        "url": "https://www.fussball.de/spielplan/dfb-pokal-deutschland-dfb-pokal-herren-saison2627-deutschland/-/staffel/0316JUJV90000000VS5489BTVU7GTVLE-C",
        "verified": True,
        "known_clubs": [],
    },
    "berlin-pokal": {
        "tier": 0.5,
        "label": "BERLIN-POKAL",
        "is_cup": True,
        # "Cosy Wasch-Landespokal 1.Herren" - the Berlin regional cup.
        "url": "https://www.fussball.de/spielplan/cosy-wasch-landespokal-1herren-berlin-berlin-pokal-herren-saison2627-berlin/-/staffel/031CI7P4GS000000VS5489BUVUR5FS5A-C",
        "verified": True,
        "known_clubs": [],
    },
}

# FALLBACK ONLY. Each match's own page now gives a real, per-fixture
# venue + address via a Google Maps link (see fetch_match_detail()) -
# this hand-typed table is only used on the rare fixture where that
# page doesn't have one. Same pattern as the cinema addresses in
# BerlinKino. Keyed by club name.
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
    "Blau Weiß 1890 Berlin": ("Poststadion Nebenplatz", "Rathenower Str. 42, 10559 Berlin"),
    "SC Charlottenburg": ("Mommsenstadion", "Waldschulallee 34, 14055 Berlin"),
    "Türkiyemspor Berlin": ("Stadion Rathenower Straße", "Rathenower Str. 42, 10559 Berlin"),
    "TSV Mariendorf 1897": ("Sportplatz Mariendorf", "Motzener Straße 20, 12277 Berlin"),
}

# Official club websites (NOT fussball.de) - so fans can find ticket
# info, club news etc. straight from the source. First-team Berlin clubs
# only, tiers 4-7 (matches the same "no reserve teams" scope decision as
# everywhere else in this project) - hand-researched and verified one at
# a time, same approach as VENUE_ADDRESSES_BY_CLUB above. Keyed by
# substring match against the scraped team name, so e.g. "VSG
# Altglienicke" here also matches a scraped "VSG Altglienicke II" - fine,
# it's still the right club's site, just not a dedicated reserve-team page
# (reserve teams don't get one).
#
# "Berlin Türkspor" is deliberately NOT in this dict - confirmed to be a
# real, distinct Berlin club (not the same as Türkiyemspor Berlin below),
# but no genuine independent website could be found for it. Leaving it
# out means the frontend just shows no link for that club, rather than
# guessing at a URL that might be wrong.
#
# "Türkiyemspor Berlin" and "Türkiyemspor Berlin 1978" both point at the
# same site - confirmed via matching fussball.de club ID that these are
# the same real-world club appearing under two different name strings in
# scraped data (likely first team vs. second team), not two clubs.
CLUB_WEBSITES = {
    "BFC Dynamo": "https://bfc.com",
    "VSG Altglienicke": "https://www.vsg-altglienicke.de",
    "Tasmania Berlin": "https://www.sv-tasmania-berlin.de",
    "BFC Preussen": "https://bfc-preussen.de",
    "Berliner AK 07": "https://www.bak07.de",
    "SV Lichtenberg 47": "https://www.lichtenberg47.de",
    "Hertha 03 Zehlendorf": "https://www.h03.de",
    "Tennis Borussia Berlin": "https://www.tebe.de",
    "TuS Makkabi Berlin": "https://tus-makkabi.de",
    "Eintracht Mahlsdorf": "https://bsv-eintracht-mahlsdorf.de",
    "SC Staaken": "https://sc-staaken.de/",
    "SV Sparta Lichtenberg": "https://sv-sparta.de/",
    "Füchse Berlin Reinickendorf": "https://www.fuechse-berlin-reinickendorf.de/",
    "Blau-Weiss 90 Berlin": "https://www.blauweiss90berlin.de/",
    # Same club, fussball.de's own formal name for it - "Blau-Weiss 90"
    # is the common/hand-typed name used in known_clubs above, but the
    # scraper pulls team names straight off fussball.de, which lists
    # this one under its full registered name instead. Real gap found
    # via a live fixture ("Sp.Vg. Blau Weiß 1890 Berlin" showing no
    # club link) - both keys point at the same site.
    "Blau Weiß 1890 Berlin": "https://www.blauweiss90berlin.de/",
    "1. FC Wilmersdorf": "https://fcwilmersdorf.de/",
    "SC Charlottenburg": "https://www.scc-berlin-fussball.de/",
    "Spandauer Kickers": "https://www.spaki-berlin.de/",
    "SSC Südwest": "https://sscsuedwest.de/",
    "Polar Pinguin": "https://www.polar-pinguin.berlin/",
    "Fortuna Biesdorf": "https://www.fortuna-biesdorf.de/",
    "SFC Stern 1900": "https://www.stern1900.de/",
    "SV Empor Berlin": "https://www.empor-berlin.de/",
    "Türkiyemspor Berlin 1978": "https://tuerkiyemspor.com/",
    "Türkiyemspor Berlin": "https://tuerkiyemspor.com/",
    "TSV Mariendorf 1897": "https://tsvmariendorf97.de/",
    "Frohnauer SC": "https://www.frohnauersc.de/",
    "Viktoria 1889 Berlin": "https://viktoria1889.berlin/",
    "Berliner SC": "https://www.berlinersc-fussball.de/",
    "Croatia Berlin": "http://sdcroatia.de/",
    "BFC Meteor 06": "https://meteor06.de/",
    "Friedenauer TSC": "https://www.friedenauertsc-berlin.de/",
    "Spandauer FC Veritas": "https://www.sfcv96.de/",
    "Charlottenburg-Wilmersdorf 03": "https://www.sfcw03.de/",
    "Berliner Amateure": "https://www.berlineramateure.de/",
    "FC Schöneberg": "https://1fcschoeneberg1913.de/",
    "Steglitzer SC Südwest 1947": "https://www.ssc1947.de/",
    "FC Internationale Berlin": "https://www.inter-berlin.de/",
    "Delay Sports Berlin": "https://www.delaysports-berlin.de/",
    "Köpenicker FC": "https://www.koepenickerfc.de/",
    "Pfeffersport": "https://pfeffersport.de/",
    "SSC Teutonia 99": "https://www.ssc-teutonia.de/",
    "Berlin Hilalspor": "https://hilalspor-berlin.de/",
    "Berolina Stralau": "https://www.berolina-stralau.de/",
    "FSV Hansa 07": "https://www.hansa07.de/",
    "Hürtürkel": "https://www.hurturkel.com/",
    # Tiers 1-3 (also covered in scraper_openligadb.py, kept here too so
    # any fixture that happens to route through this file still resolves).
    "Hertha BSC": "https://www.herthabsc.com",
    "Union Berlin": "https://www.fc-union-berlin.de",
}


def get_club_website(team_name):
    for club, url in CLUB_WEBSITES.items():
        if club in team_name:
            return url
    return ""


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
    two stable URL patterns rather than CSS classes (see module
    docstring for why): team links and per-fixture match-detail links.

    Deliberately does NOT try to read a date off this page anymore - see
    the module docstring's "KNOWN BUG, FOUND AND FIXED" section for why
    that turned out to be unreliable. Date (plus time and venue) comes
    from fetch_match_detail() against each fixture's own page instead.
    """

    def __init__(self):
        super().__init__()
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


MATCH_MAPS_RE = re.compile(
    r'href="https://www\.google\.[a-z.]+/maps\?q=[^"]*"[^>]*>(.*?)</a>', re.S
)
# Tolerant of a bit of markup between "Anpfiff" and the time, and
# between the time and "Uhr" - real markup nesting around these two
# words isn't confirmed (only seen via a markdown-converted fetch, which
# collapses tags), so this errs on the side of a wider, cheap window
# rather than an exact adjacency assumption that might not hold in the
# actual raw HTML a plain urllib request gets back.
ANPFIFF_TIME_RE = re.compile(r"Anpfiff.{0,300}?(\d{1,2}:\d{2}).{0,80}?Uhr", re.S)
TAG_RE = re.compile(r"<[^>]+>")


def fetch_match_detail(url):
    """
    Fetch one fixture's own page for its real date, kickoff time, and
    venue - see the module docstring's "KNOWN BUG, FOUND AND FIXED"
    section for why the listing page's date can't be trusted. Every
    match page reliably has:
      - a breadcrumb link back to its own matchday, e.g.
        `.../spieldatum/2026-08-07/staffel/...` - reuses SPIELDATUM_RE.
      - a kickoff time as plain text near the word "Anpfiff", e.g.
        "Anpfiff ... 20:15Uhr".
      - a Google Maps link whose visible text is the full venue,
        typically "<pitch type>, <ground name>, <street>, <plz+city>",
        e.g. "Rasenplatz, Mommsenstadion NR1, Waldschulallee 34-42,
        14055 Berlin" - split on the last two comma-separated parts to
        get a street address, the rest becomes the venue name.
    Returns {} (and every field falls back downstream) if the fetch
    itself fails - this only ever affects one fixture, not the whole run.
    """
    try:
        html = fetch_page(url)
    except Exception as e:
        log(f"    match detail fetch failed for {url}: {e}")
        return {}

    match_date = None
    m = SPIELDATUM_RE.search(html)
    if m:
        match_date = m.group(1)

    kickoff_time = None
    m = ANPFIFF_TIME_RE.search(html)
    if m:
        kickoff_time = m.group(1)

    venue, venue_address = "", ""
    m = MATCH_MAPS_RE.search(html)
    if m:
        raw_text = " ".join(TAG_RE.sub(" ", m.group(1)).split())
        parts = [p.strip() for p in raw_text.split(",") if p.strip()]
        if len(parts) >= 2:
            venue_address = ", ".join(parts[-2:])
            venue = ", ".join(parts[:-2]) or parts[0]
        elif parts:
            venue = parts[0]

    return {
        "date": match_date,
        "time": kickoff_time,
        "venue": venue,
        "venue_address": venue_address,
    }


def normalize_fixture(raw, detail, league_key, league_info):
    venue = detail.get("venue") or ""
    venue_address = detail.get("venue_address") or ""
    if not venue_address:
        # Fallback only - shouldn't normally trigger since the match
        # page itself almost always has a Maps link (see
        # fetch_match_detail).
        for club, (v, addr) in VENUE_ADDRESSES_BY_CLUB.items():
            if club in raw["home_team"]:
                venue, venue_address = v, addr
                break
    return {
        "date": detail["date"],
        "time": detail.get("time"),
        "home_team": raw["home_team"],
        "away_team": raw["away_team"],
        "league": league_info["label"],
        "league_tier": league_info["tier"],
        "is_cup": bool(league_info.get("is_cup", False)),
        "gender": GENDER,
        "matchday": "",
        "venue": venue,
        "venue_address": venue_address,
        "home_team_website": get_club_website(raw["home_team"]),
        "away_team_website": get_club_website(raw["away_team"]),
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

    # Filter to Berlin HOME fixtures BEFORE doing any per-match fetches -
    # keeps the extra network cost limited to fixtures we actually want.
    candidates = [f for f in raw_fixtures if is_berlin_fixture(f["home_team"], f["away_team"])]
    log(f"  {len(candidates)} are Berlin home fixtures - fetching each match page for its real date/time/venue")

    berlin_fixtures = []
    for f in candidates:
        detail = fetch_match_detail(f["match_url"])
        time_module.sleep(0.3)  # polite pause - one request per fixture
        if not detail.get("date"):
            log(f"    skip (no real date found on match page): {f['home_team']} vs {f['away_team']}")
            continue
        berlin_fixtures.append(normalize_fixture(f, detail, key, info))

    log(f"  {len(berlin_fixtures)} confirmed with a real date:")
    for f in berlin_fixtures[:10]:
        log(f"    {f['date']} {f['time'] or '(no time)'}  {f['home_team']} vs {f['away_team']}  ({f['league']})")
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
    #
    # REAL BUG FOUND (user report - "played games still show up"): this
    # function was reconciling every candidate date except it never
    # actually dropped ones already in the past - scraper_openligadb.py
    # already had a `if d < today_iso: continue` guard for exactly this
    # reason, this file just never got the same guard. Fixed by adding
    # it here too, so a date that's already happened gets its file
    # removed (via the `elif os.path.exists(path): os.remove(path)`
    # branch below, since it's skipped before ever landing in `written`)
    # on the next run after it passes, same as openligadb.
    today_iso = date.today().isoformat()
    candidate_dates = sorted(set(existing_index) | set(by_date))
    written = []
    for d in candidate_dates:
        if d < today_iso:
            path = os.path.join(DATA_DIR, f"{d}.json")
            if os.path.exists(path):
                os.remove(path)
            continue
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

    # CUPS is a separate dict from LEAGUES (see the module docstring for
    # why cups need different handling), but merged here so --league
    # works identically for both, and a plain run without --league
    # covers everything verified across leagues AND cups in one pass.
    all_entries = {**LEAGUES, **CUPS}
    leagues = {league_filter: all_entries.get(league_filter)} if league_filter else all_entries

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
