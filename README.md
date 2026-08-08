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
- **`scraper_fussballde.py`** — targets `fussball.de` for the three
  divisions below 3. Liga, organized league football only (no pub/
  five-a-side teams). Current 2026–27 rosters:
  - **Regionalliga Nordost** (tier 4): BFC Dynamo, VSG Altglienicke,
    Tasmania Berlin
  - **NOFV-Oberliga Nord** (tier 5): Berliner AK 07, SV Lichtenberg 47,
    Hertha 03 Zehlendorf, Tennis Borussia Berlin, TuS Makkabi Berlin,
    Eintracht Mahlsdorf, SC Staaken, SV Sparta Lichtenberg, Füchse
    Berlin Reinickendorf
  - **Berlin-Liga** (tier 6, Berlin-only): Blau-Weiss 90 Berlin, 1. FC
    Wilmersdorf, SC Charlottenburg, Spandauer Kickers, SSC Südwest,
    Polar Pinguin, Fortuna Biesdorf, VSG Altglienicke II, SFC Stern
    1900, SV Empor Berlin, TSV Mariendorf 1897, Frohnauer SC,
    Türkiyemspor Berlin

  **Unverified** — the site is JS-rendered, so this plain-requests
  version is a first pass and likely needs Playwright instead. Not wired
  into the scheduled workflow yet. Also worth knowing: promotion and
  relegation reshuffle these three lists every summer, so this roster
  needs a re-check each season.
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
BerlinKino at first. To help fix it: **Actions → debug-fussballde → Run
workflow**, then send me the output — real HTML from the real page is
what's needed to write correct selectors (or confirm it needs Playwright
for JS rendering).

**Not yet covered:** Kreisliga-level and below in most cases (fussball.de
does list these, but coverage depends on the scraper above working),
and any Berlin club not yet added to `BERLIN_LOWER_LEAGUE_CLUBS` in
`scraper_fussballde.py` — that list is easy to extend once the scraper
itself is confirmed working.

## Team badges

Real club crests are trademarked, so the app doesn't display any actual
logos. Instead, each team gets a small generated monogram (initials in a
colored circle) — gives visual structure without any copyright risk.

## Other things worth knowing

- Both scrapers depend on their source's structure staying stable — if
  either site redesigns, the affected scraper needs updating.
- Respectful scraping: real User-Agent, no aggressive polling, twice a
  day via schedule only.
