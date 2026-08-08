name: debug-fussballde

# Manual-only. Fetches one real fussball.de league page and prints the
# raw HTML so real selectors can be written into parse_league_page() in
# scraper_fussballde.py. Doesn't touch data/ and never commits anything -
# scraper_fussballde.py stays out of the scheduled update-fixtures.yml
# job until it's actually verified against real output from this run.
#
# Run it from: Actions → debug-fussballde → Run workflow, pick a league
# key from the dropdown, then paste the job's log output back so the
# parsing logic can be fixed against real markup.

on:
  workflow_dispatch:
    inputs:
      league:
        description: "League key (see LEAGUES in scraper_fussballde.py)"
        required: true
        default: "regionalliga-nordost"
        type: choice
        options:
          - regionalliga-nordost
          - oberliga-nordost
          - berlin-liga
          - landesliga-1
          - landesliga-2
          - dfb-pokal
          - berlin-pokal

jobs:
  debug-fussballde:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Debug fetch against a fussball.de league page
        run: python scraper_fussballde.py --debug --league "${{ github.event.inputs.league }}"
