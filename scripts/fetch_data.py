#!/usr/bin/env python3
"""
Energy & Finance Wall - data pipeline.
Runs on GitHub Actions every 20 minutes, writes data.json next to index.html.
v1 strategy: keyless public sources first (Stooq CSV, open.er-api.com, Google News RSS).
Optional keyed providers can be added later without changing the dashboard.
"""
import csv, io, json, os, urllib.request, urllib.parse, datetime
import xml.etree.ElementTree as ET

UA = {'User-Agent': 'Mozilla/5.0 (EnergyFinanceWall pipeline)'}
OUT = os.path.join(os.path.dirname(__file__), '..', 'data.json')

def get(url, timeout=30):
    req = urllib.request.Request(url, headers=UA)
    return urllib.request.urlopen(req, timeout=timeout).read().decode('utf-8', errors='ignore')

# ---- 1) Prices via Stooq (no key). symbol -> dashboard asset key ----
STOOQ_ASSETS = {
    'xauusd': 'GOLD', 'xagusd': 'SILVER',
    'cb.f': 'BRENT', 'cl.f': 'WTI',
    '^spx': 'SPX', '^dji': 'DJI', '^ndq': 'NDX',
    'nvda.us': 'NVDA', 'aapl.us': 'AAPL', 'msft.us': 'MSFT', 'tsla.us': 'TSLA',
}
# country indices where Stooq has coverage (others stay sample until a scrape session)
STOOQ_COUNTRY = {'^ukx': 'gb', '^nkx': 'jp', '^shc': 'cn'}

def stooq(symbols):
    url = 'https://stooq.com/q/l/?s=' + ','.join(symbols) + '&f=sd2t2ohlcv&h&e=csv'
    out = {}
    try:
        for r in csv.DictReader(io.StringIO(get(url))):
            try:
                c = float(r['Close']); o = float(r['Open'])
                out[r['Symbol'].lower()] = {'price': round(c, 4), 'chg': round((c - o) / o * 100, 2)}
            except (ValueError, KeyError, ZeroDivisionError):
                pass
    except Exception as e:
        print('stooq failed:', e)
    return out

# ---- 2) FX via open.er-api.com (no key) ----
def fx():
    try:
        d = json.loads(get('https://open.er-api.com/v6/latest/USD'))
        want = ['INR','PKR','PHP','EGP','TRY','IDR','JPY','CNY','SAR','GBP','EUR']
        return {k: round(d['rates'][k], 4) for k in want if k in d.get('rates', {})}
    except Exception as e:
        print('fx failed:', e); return {}

# ---- 3) News via Google News RSS (no key) ----
TOPICS = [
    ('GOLD', 'gold price'), ('OIL', 'oil price OPEC'), ('ADX', 'Abu Dhabi stock market'),
    ('US', 'US stock market'), ('BTC', 'bitcoin'), ('INDIA', 'India economy markets'),
    ('SAUDI', 'Saudi Tadawul economy'), ('EGYPT', 'Egypt economy'),
    ('TURKIYE', 'Turkey economy lira'), ('JAPAN', 'Japan Nikkei economy'),
]
def news(query, n=2):
    try:
        url = ('https://news.google.com/rss/search?q=' + urllib.parse.quote(query)
               + '&hl=en-US&gl=US&ceid=US:en')
        root = ET.fromstring(get(url))
        items = []
        for it in root.iter('item'):
            title = (it.findtext('title') or '')[:110]
            if title:
                items.append({'t': title, 'u': it.findtext('link') or ''})
            if len(items) >= n:
                break
        return items
    except Exception as e:
        print('news failed for', query, e); return []

def main():
    today = datetime.date.today().isoformat()
    prev = {}
    if os.path.exists(OUT):
        try:
            prev = json.load(open(OUT))
        except Exception:
            prev = {}

    quotes = stooq(list(STOOQ_ASSETS) + list(STOOQ_COUNTRY))
    assets = {STOOQ_ASSETS[s]: q for s, q in quotes.items() if s in STOOQ_ASSETS}
    countries = {STOOQ_COUNTRY[s]: q for s, q in quotes.items() if s in STOOQ_COUNTRY}

    wire, newsmap = [], {}
    for tag, q in TOPICS:
        items = news(q)
        newsmap[tag] = items
        if items:
            wire.append([tag, items[0]['t']])

    # history: one point per asset per day, keep last 400
    hist = prev.get('history', {})
    for k, q in assets.items():
        h = hist.get(k, [])
        if not h or h[-1]['d'] != today:
            h.append({'d': today, 'p': q['price']})
        else:
            h[-1]['p'] = q['price']
        hist[k] = h[-400:]

    # self-writing historian: big daily move -> attach today's top headline
    marks = prev.get('marks', {})
    TAGMAP = {'GOLD': 'GOLD', 'SILVER': 'GOLD', 'BRENT': 'OIL', 'WTI': 'OIL',
              'SPX': 'US', 'NDX': 'US', 'DJI': 'US'}
    for k, q in assets.items():
        if abs(q.get('chg', 0)) >= 2.0:
            top = newsmap.get(TAGMAP.get(k, 'US'), [])
            if top:
                m = marks.get(k, [])
                if not m or m[-1]['d'] != today:
                    m.append({'d': today, 'chg': q['chg'], 't': top[0]['t']})
                    marks[k] = m[-40:]

    out = {
        'updated': datetime.datetime.utcnow().isoformat() + 'Z',
        'assets': assets, 'countries': countries, 'fx': fx(),
        'news': wire, 'newsFull': newsmap, 'history': hist, 'marks': marks,
    }
    json.dump(out, open(OUT, 'w'), separators=(',', ':'))
    print('wrote data.json:', len(assets), 'assets,', len(countries), 'country indices,',
          len(wire), 'headlines')

if __name__ == '__main__':
    main()
