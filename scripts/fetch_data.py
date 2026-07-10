#!/usr/bin/env python3
"""
Energy & Finance Wall - data pipeline v3.
Primary source: yfinance library (handles Yahoo's cookie/crumb anti-bot handshake).
Fallbacks: raw Yahoo chart API, then Stooq. FX: open.er-api.com. News: Google News RSS.
"""
import csv, io, json, os, time, urllib.request, urllib.parse, datetime
import xml.etree.ElementTree as ET

UA = {'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/126 Safari/537.36'}
OUT = os.path.join(os.path.dirname(__file__), '..', 'data.json')

def get(url, timeout=25):
    req = urllib.request.Request(url, headers=UA)
    return urllib.request.urlopen(req, timeout=timeout).read().decode('utf-8', errors='ignore')

# ---- Yahoo Finance (primary) ----
YAHOO_ASSETS = {
    'GC=F': 'GOLD', 'SI=F': 'SILVER', 'BZ=F': 'BRENT', 'CL=F': 'WTI',
    '^GSPC': 'SPX', '^DJI': 'DJI', '^IXIC': 'NDX',
    'NVDA': 'NVDA', 'AAPL': 'AAPL', 'MSFT': 'MSFT', 'TSLA': 'TSLA',
}
YAHOO_UAE = {  # candidate symbols - misses are logged, not fatal
    'FAB.AD': 'FAB', 'ADNOCGAS.AD': 'ADNOCGAS', 'ALDAR.AD': 'ALDAR',
    'EAND.AD': 'EAND', 'EMAAR.DU': 'EMAAR', 'EMIRATESNBD.DU': 'ENBD',
}
FLAGSHIPS = {  # aligned with the dashboard's company order per country
    'cn': ['0700.HK', '9988.HK', '1211.HK', '1398.HK'],
    'in': ['RELIANCE.NS', 'TCS.NS', 'HDFCBANK.NS', 'INFY.NS'],
    'sa': ['2222.SR', '1120.SR', '2010.SR', '7010.SR'],
    'gb': ['SHEL.L', 'AZN.L', 'HSBA.L', 'BP.L'],
    'jp': ['7203.T', '6758.T', '8306.T', '7974.T'],
    'eg': ['COMI.CA', 'SWDY.CA', 'TMGH.CA', 'HRHO.CA'],
    'tr': ['THYAO.IS', 'KCHOL.IS', 'BIMAS.IS', 'ASELS.IS'],
    'id': ['BBCA.JK', 'BMRI.JK', 'TLKM.JK', 'ASII.JK'],
}
YAHOO_COUNTRY = {
    '^FTSE': 'gb', '^N225': 'jp', '000001.SS': 'cn', '^NSEI': 'in',
    '^TASI.SR': 'sa', 'XU100.IS': 'tr', '^JKSE': 'id', '^KSE': 'pk', '^CASE30': 'eg',
}
def yahoo(sym):
    url = ('https://query1.finance.yahoo.com/v8/finance/chart/'
           + urllib.parse.quote(sym) + '?range=1d&interval=1d')
    m = json.loads(get(url))['chart']['result'][0]['meta']
    price = m.get('regularMarketPrice')
    prev = m.get('chartPreviousClose') or m.get('previousClose') or price
    if price is None:
        raise ValueError('no price')
    chg = round((price - prev) / prev * 100, 2) if prev else 0.0
    return {'price': round(float(price), 4), 'chg': chg}

def yf_quote(sym):
    import yfinance as yf
    fi = yf.Ticker(sym).fast_info
    price = float(fi.last_price)
    if not price or price <= 0:
        raise ValueError('zero/empty price')
    prev = float(fi.previous_close or price)
    return {'price': round(price, 4),
            'chg': round((price - prev) / prev * 100, 2) if prev else 0.0}

def yahoo_all():
    assets, countries = {}, {}
    try:
        import yfinance  # noqa: F401
        grab = yf_quote
        print('using yfinance', yfinance.__version__)
    except ImportError:
        grab = yahoo
        print('yfinance unavailable, using raw HTTP')
    for sym, key in YAHOO_ASSETS.items():
        try:
            assets[key] = grab(sym)
        except Exception as e:
            print('miss', sym, repr(e)[:90])
            try:
                assets[key] = yahoo(sym)
            except Exception:
                pass
        time.sleep(0.3)
    for sym, cc in YAHOO_COUNTRY.items():
        try:
            countries[cc] = grab(sym)
        except Exception as e:
            print('miss', sym, repr(e)[:90])
        time.sleep(0.3)
    for sym, key in YAHOO_UAE.items():
        try:
            assets[key] = grab(sym)
            print('UAE hit:', sym)
        except Exception as e:
            print('UAE miss', sym, repr(e)[:70])
        time.sleep(0.3)
    flagships = {}
    for cc, syms in FLAGSHIPS.items():
        row = []
        for sym in syms:
            try:
                row.append(grab(sym))
            except Exception as e:
                print('flagship miss', sym, repr(e)[:70]); row.append(None)
            time.sleep(0.25)
        flagships[cc] = row
    return assets, countries, flagships

# ---- Stooq (fallback for anything Yahoo missed) ----
STOOQ_ASSETS = {'xauusd': 'GOLD', 'xagusd': 'SILVER', 'cb.f': 'BRENT', 'cl.f': 'WTI',
                '^spx': 'SPX', '^dji': 'DJI', '^ndq': 'NDX',
                'nvda.us': 'NVDA', 'aapl.us': 'AAPL', 'msft.us': 'MSFT', 'tsla.us': 'TSLA'}
def stooq_fill(assets):
    missing = [s for s, k in STOOQ_ASSETS.items() if k not in assets]
    if not missing:
        return assets
    try:
        url = 'https://stooq.com/q/l/?s=' + ','.join(missing) + '&f=sd2t2ohlcv&h&e=csv'
        for r in csv.DictReader(io.StringIO(get(url))):
            try:
                c = float(r['Close']); o = float(r['Open'])
                assets[STOOQ_ASSETS[r['Symbol'].lower()]] = {
                    'price': round(c, 4), 'chg': round((c - o) / o * 100, 2)}
            except (ValueError, KeyError, ZeroDivisionError):
                pass
    except Exception as e:
        print('stooq failed:', e)
    return assets

# ---- FX ----
def fx():
    try:
        d = json.loads(get('https://open.er-api.com/v6/latest/USD'))
        want = ['INR','PKR','PHP','EGP','TRY','IDR','JPY','CNY','SAR','GBP','EUR']
        return {k: round(d['rates'][k], 4) for k in want if k in d.get('rates', {})}
    except Exception as e:
        print('fx failed:', e); return {}

# ---- News ----
TOPICS = [('GOLD','gold price'),('OIL','oil price OPEC'),('ADX','Abu Dhabi stock market'),
          ('US','US stock market'),('BTC','bitcoin'),
          ('CHINA','China economy markets'),('INDIA','India economy markets'),
          ('SAUDI','Saudi Tadawul economy'),('UK','UK economy FTSE'),
          ('JAPAN','Japan Nikkei economy'),('PAKISTAN','Pakistan economy KSE'),
          ('EGYPT','Egypt economy'),('TURKIYE','Turkey economy lira'),
          ('INDONESIA','Indonesia economy markets')]
def news(query, n=2):
    try:
        url = ('https://news.google.com/rss/search?q=' + urllib.parse.quote(query)
               + '&hl=en-US&gl=US&ceid=US:en')
        root = ET.fromstring(get(url))
        items = []
        for it in root.iter('item'):
            t = (it.findtext('title') or '')[:110]
            if t:
                items.append({'t': t, 'u': it.findtext('link') or ''})
            if len(items) >= n:
                break
        return items
    except Exception as e:
        print('news failed for', query, e); return []

def main():
    today = datetime.date.today().isoformat()
    prev = {}
    if os.path.exists(OUT):
        try: prev = json.load(open(OUT))
        except Exception: prev = {}

    assets, countries, flagships = yahoo_all()
    assets = stooq_fill(assets)

    wire, newsmap = [], {}
    for tag, q in TOPICS:
        items = news(q); newsmap[tag] = items
        if items: wire.append([tag, items[0]['t']])

    hist = prev.get('history', {})
    for k, q in assets.items():
        h = hist.get(k, [])
        if not h or h[-1]['d'] != today: h.append({'d': today, 'p': q['price']})
        else: h[-1]['p'] = q['price']
        hist[k] = h[-400:]

    marks = prev.get('marks', {})
    TAGMAP = {'GOLD':'GOLD','SILVER':'GOLD','BRENT':'OIL','WTI':'OIL','SPX':'US','NDX':'US','DJI':'US'}
    for k, q in assets.items():
        if abs(q.get('chg', 0)) >= 2.0:
            top = newsmap.get(TAGMAP.get(k, 'US'), [])
            if top:
                m = marks.get(k, [])
                if not m or m[-1]['d'] != today:
                    m.append({'d': today, 'chg': q['chg'], 't': top[0]['t']}); marks[k] = m[-40:]

    out = {'updated': datetime.datetime.utcnow().isoformat() + 'Z',
           'assets': assets, 'countries': countries, 'flagships': flagships, 'fx': fx(),
           'news': wire, 'newsFull': newsmap, 'history': hist, 'marks': marks}
    json.dump(out, open(OUT, 'w'), separators=(',', ':'))
    print('wrote data.json:', len(assets), 'assets |', len(countries), 'country indices |', sum(1 for r in flagships.values() for x in r if x), 'flagship stocks |', len(wire), 'headlines')

if __name__ == '__main__':
    main()
