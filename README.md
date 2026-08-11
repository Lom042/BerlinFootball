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
  alphabetically) → team.** Each fixture also shows its venue plus the
  venue's street address where known, and a matchday tag where the
  source provides one.

  **Filters are all multi-select and mutually narrowing.** Date,
  league, district, and team each behave like the others: click a chip
  to toggle it on or off, and pick as many as you like in each category
  (e.g. two dates to cover a whole weekend, or two teams at once). Every
  filter narrows what the OTHER filters offer — pick a date and the
  league/district/team chips shrink to only what's actually on that
  day; pick a league and the calendar shrinks to only dates with a
  fixture in that league; same for district and team. A control never
  hides an option you've already selected, even if a later choice would
  otherwise rule it out, so you can always find your own picks again to
  deselect them. `matchesFilters()` in `index.html` is the single place
  all four filters get combined — every chip-rendering function calls
  it with its own dimension excluded to work out what to offer.

  Team search deliberately does NOT filter fixtures by substring as you
  type anymore (typing "hertha" alone won't narrow the list) — it only
  narrows a short suggestion list; you click a suggestion to add that
  exact team as a removable chip. That's what makes selecting more than
  one team possible, at the cost of the old "just start typing" instant
  filter feel.

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

  **Also covers two cup competitions** (`CUPS` in the same file, kept
  separate from `LEAGUES` since cups work differently - see below):
  - **DFB-Pokal** (national cup)
  - **Berlin-Pokal** ("Cosy Wasch-Landespokal", the Berlin regional cup)

  A cup isn't one flat season schedule like a league - it's a knockout
  played in separate rounds, each drawn only once the previous one
  finishes, with no single page listing every round at once. Rather than
  track "which round is currently live" ourselves, each `CUPS` entry
  points at the competition's stable overview URL, which fussball.de
  itself redirects to whichever round is currently active - so this file
  never needs manual updates as a tournament progresses. As of shipping
  this, neither cup's current round has a published draw yet, so both
  show zero fixtures for now - that's expected, not a bug, and fixtures
  should start appearing automatically once each draw is published.

  **Also links each club's own official website** (`CLUB_WEBSITES`, same
  file), separate from the fussball.de match page - so fans can find
  ticket info straight from the club rather than the fixtures aggregator.
  Scope: first-team Berlin clubs only, tiers 1–7 (Bundesliga down through
  Landesliga), no reserve/II/U23 sides. Hand-researched and verified one
  club at a time, same approach as `VENUE_ADDRESSES_BY_CLUB`. Two things
  worth knowing about the data:
  - **Berlin Türkspor** deliberately has no entry - confirmed to be a
    real, distinct Berlin club (not the same as Türkiyemspor Berlin
    below), but no genuine independent website could be found for it.
    Fixtures involving it just show no club link rather than a guessed
    URL.
  - **Türkiyemspor Berlin** and **Türkiyemspor Berlin 1978** both point
    at the same site (`tuerkiyemspor.com`) - confirmed via matching
    fussball.de club ID that these are the same real club appearing under
    two name strings in scraped data (likely first team vs. second team),
    not two separate clubs.
  `scraper_openligadb.py` carries its own small `CLUB_WEBSITES` (just
  Hertha BSC and Union Berlin) using the same lookup pattern, since tiers
  1–3 are a separate file. `index.html` renders it as a small "↗" link
  next to each team name that has one on file.

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

**`scraper_fussballde.py`** → verified and live for all 5 league staffeln
it targets (Regionalliga Nordost, Oberliga Nordost, Berlin-Liga,
Landesliga 1 & 2 — tiers 4–7), plus 2 cup competitions (DFB-Pokal,
Berlin-Pokal) that show zero fixtures until each one's current-round
draw is published. To add another league staffel, find its real
`/spielplan/.../staffel/<ID>-G` URL (WebSearch, or a known club's
current-season team page), add it to `LEAGUES` with `verified: False`,
confirm via **Actions → debug-fussballde → Run workflow**, then flip it
to `True`. Adding another cup follows the same verification step but
goes in `CUPS` instead, using the competition's stable `-C` overview URL
(not a specific round's `-R` URL).

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

**Played fixtures / past months disappearing:** two layers, so this
holds up even if a scrape run is delayed:
- Both scrapers prune any date before today when they write `data/` -
  `scraper_openligadb.py` always did this; `scraper_fussballde.py` had a
  real gap here (found via user report - past fixtures just stayed in
  the file forever) and now has the same `if d < today_iso` guard.
- `index.html` also drops any past date client-side on load
  (`dropPastDates()`), using the visitor's own local calendar day - a
  safety net for the gap between a match's day ending and the next
  twice-daily scrape actually removing it. A month with nothing left in
  it after that filter just stops showing up in the month pills - no
  separate "hide old months" logic needed, it falls out of the same fix.

**Club name variants:** fussball.de doesn't always use the same name for
a club that its `known_clubs` sanity list (or `CLUB_WEBSITES`/
`VENUE_ADDRESSES_BY_CLUB`) expects - e.g. "Blau-Weiss 90 Berlin" shows up
on some fixture pages under its full formal name, "Sp.Vg. Blau Weiß 1890
Berlin". When a club's site link or venue fallback goes missing on a
real fixture, check for exactly this before assuming something's broken
- add the alternate name as another dict key pointing at the same value.

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
