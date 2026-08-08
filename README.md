# Berlin Football

A free, ad-free, non-commercial fixtures board for football in Berlin —
every club based in the city, from Bundesliga down through the amateur
leagues, in one place. Installable to your phone's home screen the same
way as BerlinKino (Share → Add to Home Screen).

**Scope: men's league football only, for now.** Every fixture carries an
explicit `gender` field ("M") for exactly this reason — so that if
women's football is ever added, it's a new, clearly-labeled category
rather than something that can get silently mixed in with men's
fixtures. (An earlier demo build paired Hertha BSC against Union Berlin
as if they shared a league — they don't, Union's in Bundesliga and
Hertha's in 2. Bundesliga. That was a tier mistake, not a gender one, but
it's the reason gender is now explicit rather than assumed.)

## How it's built

- **`index.html`** — the whole frontend. One file, no build step. Ships
  with demo data (tier-correct fixtures, not a real head-to-head) so it
  works the moment you open it, and switches to live data automatically
  once `data/index.json` exists next to it.

  Sort/display hierarchy: **date → league (by real tier, not
  alphabetically) → team.** Pick a date from the pills up top; underneath
  it, each league's fixtures sit together as one block with the league
  name and tier directly above its own matches — not as a separate badge
  floating off to the side, disconnected from the teams it belongs to.
  Each fixture also shows its venue plus the venue's street address where
  known, and a matchday tag where the source provides one.

- **`scraper_openligadb.py`** — pulls from `api.openligadb.de`, a free,
  open JSON API covering Bundesliga, 2. Bundesliga, and 3. Liga (tiers
  1–3). No HTML scraping needed here, so this one's reliable out of the
  box. Filters to matches involving Berlin clubs (Hertha, Union, or any
  Berlin club that reaches 3. Liga). Also pulls matchday and finished
  status where OpenLigaDB provides them, and attaches a street address
  for the two Berlin top-flight grounds it can produce (Olympiastadion,
  Alte Försterei) via a small hardcoded lookup — OpenLigaDB itself only
  gives a city/stadium name, not a street address.

- **`scraper_fussballde.py`** — targets `fussball.de` for tiers 4–11,
  organized league football only (no pub/five-a-side teams):
  - **Regionalliga Nordost** (tier 4)
  - **NOFV-Oberliga Nord** (tier 5)
  - **Berlin-Liga** (tier 6, Berlin-only)
  - **Landesliga**, 2 staffeln (tier 7)
  - **Bezirksliga**, 3 staffeln (tier 8)
  - **Kreisliga A / B / C** (tiers 9–11 — closest to pub-league territory
    while still being organized league football)

  **Architecture note:** this file used to be one hand-typed entry per
  *club*. That worked down to Berlin-Liga (tier 6, a few dozen clubs
  total) but doesn't scale into Landesliga/Bezirksliga/Kreisliga, where
  there are hundreds of clubs reshuffled every season by promotion and
  relegation. It's now organized as one entry per league *staffel*
  instead — tiers 4–6 still ship a real, current known-club list as a
  sanity check, but tiers 7–11 deliberately don't hand-type any clubs;
  those need to be discovered from each staffel's fixture page directly.

  **Unverified** — the site is JS-rendered, so this plain-requests
  version is a first pass and likely needs Playwright instead. Not wired
  into the scheduled workflow yet. `parse_league_page()` has no real
  selectors in it until a debug run against a real page comes back.

- **`.github/workflows/update-fixtures.yml`** — runs the OpenLigaDB
  scraper twice a day and commits fresh data automatically.

- **`.github/workflows/debug-fussballde.yml`** — separate, manual-only
  workflow to help verify the fussball.de scraper. Pick a league from
  the dropdown, run it, and send me the log output.

## Get it live (same as BerlinKino)

1. Create a new **public** GitHub repo, push these files.
2. **Settings → Pages** → source: `main` branch, root.
3. **Settings → Actions → General → Workflow permissions** → "Read and
   write permissions".
4. Done — `update-fixtures.yml` runs automatically at 08:00 and 20:00
   Berlin time.

Trigger the fixtures update manually any time from **Actions → Update
Berlin football fixtures → Run workflow**.

## Coverage: what's actually in here

**`scraper_openligadb.py`** → confident. Clean API, covers Hertha BSC,
1. FC Union Berlin, and any Berlin club in the top 3 divisions (tiers
1–3). Matchday and finished-status included where available.

**`scraper_fussballde.py`** → unverified for all 8 staffeln it targets
(tiers 4–11). To help fix it: **Actions → debug-fussballde → Run
workflow**, pick a league from the dropdown, then send me the output —
real HTML from a real page is what's needed to write correct selectors
(or confirm it needs Playwright for JS rendering). Once one staffel's
selectors work, the same ones likely carry over to the rest since
they're all the same page type on fussball.de.

**Stadium addresses** → hardcoded lookup tables in both scraper files,
same approach as the cinema addresses in BerlinKino. Covers the grounds
for every tier 1–6 club currently listed. Best-effort, worth spot-
checking — amateur ground addresses aren't as reliably documented as
pro stadiums. Tiers 7–11 have no hardcoded addresses; those should come
from whatever venue info the real fussball.de page exposes once that
scraper is verified, rather than being hand-typed too.

**Not yet covered:** anything below Kreisliga C (i.e. actual pub/
five-a-side football — deliberately out of scope), and any Berlin club
not yet added to the tier 4–6 `known_clubs` lists in
`scraper_fussballde.py`.

## Team badges

Real club crests are trademarked, so the app doesn't display any actual
logos. Instead, each team gets a small generated monogram (initials in a
colored circle) — gives visual structure without any copyright risk.

## Other things worth knowing

- Both scrapers depend on their source's structure staying stable — if
  either site redesigns, the affected scraper needs updating.
- Respectful scraping: real User-Agent, no aggressive polling, twice a
  day via schedule only for the verified scraper; the fussball.de debug
  workflow is manual-only and only runs when someone actually triggers
  it.
- Promotion and relegation reshuffle tier 4–11 rosters every summer —
  the `known_clubs` lists (tiers 4–6) need a re-check each season, and
  it's exactly why tiers 7–11 don't hand-type rosters at all.
