# Energy & Finance Wall

A fully autonomous, single-page live market dashboard for a 65-inch office display
(UAE / Abu Dhabi). Oil, gold & silver, UAE + US stocks, crypto, prediction-market
odds, news, and a 10-country intel layer - all times in GST.

Live at: `https://<your-username>.github.io/<repo-name>/`

## Files
- `index.html` - the entire dashboard (self-contained)
- `scripts/fetch_data.py` - data robot (keyless public sources)
- `.github/workflows/update-data.yml` - runs the robot every 20 minutes
- `background.jpg` - ambient backdrop (add your own image; optional)
- `data.json` - written automatically by the robot; do not edit

## One-time setup
1. Settings -> Pages -> Deploy from a branch -> `main` / root.
2. Settings -> Actions -> General -> Workflow permissions -> **Read and write**.
3. Actions tab -> "Update dashboard data" -> **Run workflow** (primes data.json).
4. Optional: add `background.jpg` (16:9, dark, subtle) to the repo root.
5. Open the Pages URL on the display laptop, press **Present** once.

After that it runs itself: prices/headlines refresh every 20 min server-side,
the page hot-reloads every 10 min, crypto and prediction odds update live in
the browser, and the wall self-reloads nightly at 04:00 GST.

## Live vs sample
LIVE from day one: crypto, Polymarket odds, Fear & Greed, FX (incl. PKR/EGP/SAR),
gold, silver, Brent, WTI, US indices & mega-caps, FTSE/Nikkei/Shanghai, headlines.
Still SAMPLE (marked on screen): Murban, ADX/DFM & UAE company prices, and
non-US country stocks - pending a dedicated scraping/provider session.

Not investment advice. Data sources: Stooq, open.er-api.com, Google News RSS,
CoinGecko, Polymarket, alternative.me, Frankfurter/ECB.
