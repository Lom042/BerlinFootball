# Berlin Football

A free, ad-free, non-commercial fixtures board for football in Berlin —
every club based in the city, from Bundesliga down through the amateur
leagues, in one place. Installable to your phone's home screen the same
way as BerlinKino (Share → Add to Home Screen).

## How it's built

- **`index.html`** — the whole frontend. One file, no build step. Ships
  with demo data (Hertha vs Union, plus two Regionalliga fixtures) so it
  works the moment you open it, and switches to live data automatically
  once `data/index.json` exists next to it.
- **`scraper_openligadb.py`** — pulls from `api.openligadb.de`, a free,
  open JSON API covering Bundesliga, 2. Bundesliga, and 3. Liga. No HTML
  scraping needed here, so this one's reliable out of the box. Filters to
  matches involving Berlin clubs (Hertha, Union, or any Berlin club that
  reaches 3. Liga).
- **`scraper_fussballde.py`** — targets `fussball.de` for everything
  below 3. Liga, organized league football only (no pub/five-a-side
  teams), plus the **Berliner Landespokal** (Berlin Cup):
  - **Regionalliga Nordost** (tier 4) and **NOFV-Oberliga Nord** (tier 5):
    named Berlin clubs, since these leagues span multiple German states —
    BFC Dynamo, VSG Altglienicke, Tasmania Berlin, Berliner AK 07, SV
    Lichtenberg 47, Hertha 03 Zehlendorf, Tennis Borussia Berlin, TuS
    Makkabi Berlin, Eintracht Mahlsdorf, SC Staaken, SV Sparta
    Lichtenberg, Füchse Berlin Reinickendorf
  - **Berlin-Liga** (tier 6), **Landesliga** (tier 7, 2 staffeln), and
    **Bezirksliga** (tier 8, 3 staffeln): these are Berlin-only
    competitions, so instead of typing out ~150 club names, the scraper
    pulls the full staffel table for each and takes every team in it —
    more complete, and doesn't silently miss a newly promoted club
  - **Berliner Landespokal**: the separate knockout cup, not a league
    season. This is what was missing before — on cup weekends, clubs
    skip their normal league fixture, so a site that only reads league
    tables shows a blank day even though 60+ cup matches are happening.
    178 clubs enter this season, Regionalliga Nordost down to Kreisliga
    C. Cup rounds get a `matchday` label like "Round 3" instead of a
    normal matchday number, and lower-tier clubs host higher-tier ones
    up to the quarter-final (so home team isn't always the "bigger" club)

  **Unverified** — both source sites are JS-rendered, so this
  plain-requests version is a first pass and likely needs Playwright
  instead. Not wired into the scheduled workflow yet. Also worth
  knowing: promotion and relegation reshuffle the named-club lists every
  summer, so those need a re-check each season (the staffel-pull leagues
  don't have this problem — they always fetch whoever's actually in the
  table).
- **`.github/workflows/update-fixtures.yml`** — runs the OpenLigaDB
  scraper twice a day and commits fresh data automatically. Includes a
  separate manual `debug-fussballde` job to help verify that scraper.

## Get it live (same as BerlinKino)

1. Create a new **public** GitHub repo, push these files.
2. **Settings → Pages** → source: `main` branch, root.
3. **Settings → Actions → General → Workflow permissions** → "Read and
   write permissions".
4. Done — the workflow runs automatically at 08:00 and 20:00 Berlin time.

Trigger manually any time from **Actions → Update Berlin football
fixtures → Run workflow**.

## Coverage: what's actually in here

**`scraper_openligadb.py`** → confident. Clean API, covers Hertha BSC,
1. FC Union Berlin, and any Berlin club in the top 3 divisions.

**`scraper_fussballde.py`** → unverified, same situation as Yorck was in
BerlinKino at first. Three things need checking separately:
```
python scraper_fussballde.py --debug --club "BFC Dynamo"
python scraper_fussballde.py --debug --staffel landesliga-1
python scraper_fussballde.py --debug --pokal
```
Send me the output from each (or open an issue with it) — real HTML
from the real pages is what's needed to write correct selectors, or
confirm it needs Playwright for JS rendering.

**Not yet covered:** Kreisliga A/B/C (tiers 9–11 — genuinely closer to
pub-league territory, deliberately stopped one tier above that at
Bezirksliga), and any Berlin club not yet added to `BERLIN_REGIONAL_CLUBS`
in `scraper_fussballde.py` for the two shared-with-other-states leagues.

## Data fields

Each match includes: `date`, `time`, `home_team`, `away_team`, `league`,
`gender` (currently always `"men"` — no women's leagues are covered yet),
`matchday` (a league matchday number, or a cup round like "Round 3" for
Landespokal fixtures), `venue`, and `venue_address`.

## Team badges

Real club crests are trademarked, so the app doesn't display any actual
logos. Instead, each team gets a small generated monogram (initials in a
colored circle) — gives visual structure without any copyright risk.

## Other things worth knowing

- Both scrapers depend on their source's structure staying stable — if
  either site redesigns, the affected scraper needs updating.
- Respectful scraping: real User-Agent, no aggressive polling, twice a
  day via schedule only.
