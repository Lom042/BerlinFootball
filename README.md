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

- **`scraper_fussballde.py`** — targets `fussball.de` for tiers 4–7,
  organized league football only (no pub/five-a-side teams):
  - **Regionalliga Nordost** (tier 4)
  - **NOFV-Oberliga Nord** (tier 5)
  - **Berlin-Liga** (tier 6, Berlin-only)
  - **Landesliga**, 2 staffeln (tier 7)

  All five are live and verified. **Deliberately stops at Landesliga** -
  Bezirksliga (tier 8) alone is 3 separate staffeln in Berlin, and
  Kreisliga A/B/C (tiers 9–11) split into even more (Kreisliga A alone
  has at least 4 groups), each needing its own real URL individually
  found and verified. Weighed the effort against the payoff and decided
  Landesliga - still real, organized league football - is a sensible
  floor rather than chasing a dozen+ small district groups.

  **Architecture note:** this file used to be one hand-typed entry per
  *club*. That worked down to Berlin-Liga (tier 6, a few dozen clubs
  total) but doesn't scale into Landesliga and below, where there are
  hundreds of clubs reshuffled every season by promotion and relegation.
  It's now organized as one entry per league *staffel* instead - tiers
  4–6 still ship a real, current known-club list as a sanity check, but
  Landesliga (tier 7) deliberately doesn't hand-type any clubs; those
  come from the scrape itself.

  **Turned out NOT to be JS-rendered** - the page is server-rendered and
  scrapeable via stdlib `html.parser`, no Playwright needed.

  **Real bug found and fixed:** the listing page's date column is only
  populated for a handful of near-term matchdays - most matchday blocks
  have a blank date cell. An earlier version carried the last real date
  forward for blank rows, which meant a whole league's fixtures could
  end up wrongly stamped with the same date (this is what happened to
  Oberliga Nordost's Tennis Borussia fixtures before the fix). Fixed by
  fetching each Berlin-home fixture's own match page instead of trusting
  the listing page for date - which also delivers real kickoff time and
  a real per-fixture venue address as a bonus, both previously deferred
  as "would need a per-match fetch."

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

**`scraper_fussballde.py`** → verified and live for all 5 staffeln it
targets (Regionalliga Nordost, Oberliga Nordost, Berlin-Liga, Landesliga
1 & 2 — tiers 4–7). To add another staffel, find its real
`/spielplan/.../staffel/<ID>-G` URL (WebSearch, or a known club's
current-season team page), add it to `LEAGUES` with `verified: False`,
confirm via **Actions → debug-fussballde → Run workflow**, then flip it
to `True`.

**Stadium addresses** → each match's own fussball.de page now gives a
real, per-fixture venue + street address (via a Google Maps link) - see
`fetch_match_detail()`. The hand-typed `VENUE_ADDRESSES_BY_CLUB` lookup
tables in both scraper files are fallback-only now, same approach as the
cinema addresses in BerlinKino, used only if a match page doesn't have
one.

**Kickoff times** → also pulled from each match's own page (the
"Anpfiff" kickoff marker). Not always available for fixtures far out on
the calendar - fussball.de tends to confirm times closer to matchday.

**Deliberately not covered:** Bezirksliga and Kreisliga (tiers 8–11) -
see the note in `scraper_fussballde.py` above the `LEAGUES` dict for
why. Landesliga (tier 7) is the current floor.

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
- Promotion and relegation reshuffle tier 4–7 rosters every summer —
  the `known_clubs` lists (tiers 4–6) need a re-check each season, and
  it's exactly why Landesliga (tier 7) doesn't hand-type a roster at all.
