"""
reddit_cache.py v2 -- Fetch WSB data with CORRECT pagination.

PullPush returns posts newest-first (descending). To paginate through a full day:
  - Start with before=day_end (get newest first)
  - After each batch, set before = min(created_utc) - 1 to get older posts
  - Stop when batch returns < size OR oldest post is before day_start

Schema:
    mentions(date TEXT, ticker TEXT, mention_count INT, avg_score REAL, post_count INT)
    fetch_log(period TEXT PRIMARY KEY, sub_count INT, comment_count INT, fetched_at TEXT)

Usage:
    python3 runner/reddit_cache.py --start 2023-01-01 --end 2023-06-30
"""

import re
import sys
import time
import sqlite3
import argparse
import requests
from datetime import datetime, timedelta, timezone
from pathlib import Path
from collections import defaultdict

WORKSPACE = Path(__file__).parent.parent
DB_PATH = WORKSPACE / "reddit_mentions.db"
PULLPUSH_BASE = "https://api.pullpush.io/reddit/search"

TICKER_UNIVERSE = {
    "A","AA","AAL","AAPL","ABBV","ABNB","ABT","ACGL","ACN","ADBE","ADI","ADM",
    "ADSK","AEE","AEP","AES","AFL","AIG","AIZ","AJG","AKAM","ALB","ALGN","ALK",
    "ALL","ALLE","AMAT","AMCR","AMD","AME","AMGN","AMP","AMT","AMZN","ANET",
    "ANSS","AON","AOS","APA","APD","APH","APTV","ARE","ATO","AVGO","AVB","AVY",
    "AWK","AXON","AXP","AZO","BA","BAC","BALL","BAX","BBWI","BBY","BDX","BEN",
    "BIIB","BIO","BK","BKNG","BLK","BMY","BR","BRK","BRKB","BSX","BWA","BX",
    "C","CARR","CAT","CB","CBOE","CBRE","CCL","CDAY","CDW","CE","CF","CFG",
    "CI","CINF","CL","CLX","CMA","CME","CMG","CMI","CMS","COF","COO","COP",
    "COR","COST","CPB","CPRT","CPT","CRL","CRM","CRWD","CSCO","CSX","CTAS",
    "CTLT","CTRA","CTSH","CTVA","CVS","CVX","CZR","D","DAL","DD","DE","DFS",
    "DG","DGX","DHI","DHR","DIS","DLR","DLTR","DOC","DOV","DPZ","DRI","DTE",
    "DUK","DVA","DVN","DXC","EA","EBAY","ECL","ED","EFX","EG","EIX","EL","ELV",
    "EMN","EMR","ENPH","EQR","EQT","ES","ESS","ETN","ETR","EVRG","EW","EXC",
    "EXPD","EXPE","EXR","F","FANG","FAST","FCX","FDS","FDX","FE","FFIV","FI",
    "FICO","FIS","FISV","FIX","FLT","FMC","FOX","FOXA","FRT","FTNT","GD","GE",
    "GEHC","GEN","GILD","GIS","GL","GLW","GM","GOOGL","GOOG","GPC","GPN","GS",
    "GWW","HAL","HAS","HBAN","HCA","HD","HES","HIG","HII","HLT","HOLX","HON",
    "HPE","HPQ","HRL","HSIC","HST","HSY","HUBB","HUM","HWM","IBM","ICE","IDXX",
    "IEX","IFF","ILMN","INTC","INTU","IP","IPG","IQV","IR","IRM","IT","ITW",
    "IVZ","J","JBHT","JBL","JCI","JKHY","JNJ","JNPR","JPM","K","KEYS","KHC",
    "KIM","KLAC","KMB","KMI","KMX","KO","KR","L","LDOS","LEN","LH","LHX","LIN",
    "LKQ","LLY","LMT","LNT","LOW","LRCX","LULU","LYFT","LYB","LYV","MA","MAA",
    "MAR","MAS","MCK","MCO","MDLZ","MDT","META","MET","MKC","MLM","MMC","MMM",
    "MNST","MO","MOH","MOS","MPC","MPWR","MRK","MRNA","MS","MSCI","MSFT","MSI",
    "MTB","MTD","MU","NCLH","NEE","NEM","NET","NFLX","NI","NKE","NOC","NTRS",
    "NVDA","NWS","NWSA","NXPI","O","ODFL","OKE","OMC","ON","ORCL","OTIS","OXY",
    "PAYX","PCAR","PCG","PEG","PEP","PFE","PG","PGR","PH","PHM","PKG","PLD",
    "PM","PNC","POOL","PPG","PPL","PRU","PSA","PSX","PWR","PYPL","QCOM",
    "RCL","REG","REGN","RF","RJF","RL","RMD","ROK","ROL","ROP","RSG","RTX",
    "SBAC","SBUX","SCHW","SEE","SHW","SJM","SLB","SNA","SNPS","SO","SPG",
    "SPGI","SRE","STT","STX","STZ","SWK","SWKS","SYF","SYK","SYY","T","TDG",
    "TDY","TECH","TEL","TER","TFC","TFX","TGT","TJX","TMO","TMUS","TPR","TRGP",
    "TRMB","TROW","TRV","TSCO","TSLA","TSN","TT","TTWO","TXN","TXT","TYL",
    "UAL","UDR","UHS","ULTA","UNH","UNP","UPS","URI","USB","V","VFC","VLO",
    "VMC","VRSK","VRSN","VRTX","VTR","VTRS","VZ","WAB","WAT","WBA","WBD","WDC",
    "WELL","WFC","WHR","WM","WMB","WMT","WRB","WRK","WST","WTW","WY","WYNN",
    "XEL","XYL","YUM","ZBH","ZBRA","ZTS",
    # WSB favorites
    "GME","AMC","BB","BBBY","KOSS","EXPR","NOK","NAKD","SLV",
    "COIN","HOOD","RBLX","RIVN","LCID","SOFI","PLTR","OPEN","SOUN",
    "NVAX","BNTX","MSTR","AFRM","UPST","LMND","DDOG","SNOW",
    "OKTA","TWLO","VEEV","BILL","HUBS","ZI","APP","IONQ","QBTS","RKLB","SPCE",
    # ETFs/indices commonly discussed
    "SOXS","SOXL","TQQQ","UVXY","VIXY","VXX","SVXY","LABD","LABU",
    "SPXL","SPXS","TECL","TECS","QLD","QID","SSO","SDS","UPRO","SPXU",
    "UDOW","SDOW","NUGT","DUST","JNUG","JDST",
    "SPY","QQQ","IWM","DIA","GLD","EEM","HYG","TLT","IAU",
    "SKLZ","CLOV","MVIS","OCGN","GOVX","ASTS","SMCI","ARM","AI","DELL",
}

EXCLUDE_WORDS = {
    "A","I","AM","AN","AS","AT","BE","BY","DO","FOR","GO","HE","HI",
    "IF","IN","IS","IT","ME","MY","NO","OF","OK","ON","OR","SO","TO",
    "UP","US","WE","ANY","ARE","BUT","CAN","DID","END","FEW","GET",
    "GOT","HAD","HAS","HIM","HIS","HOW","ITS","LET","MAY","NEW","NOT",
    "NOW","ONE","OUT","OUR","PUT","SAY","SEE","SHE","THE","TOO","TWO",
    "WAS","WHO","WHY","YET","YOU",
    "CEO","CFO","COO","CTO","IPO","FDA","SEC","FED","EPS","ATH","ATL",
    "AMA","IMO","EOD","EOM","EOY","YOY","QOQ","MOM","YTD","MTD",
    "OTC","OTM","ITM","ATM","OI","IV","DTE","RH","WSB","DD","TA","FA",
    "TDA","ETH","BTC","NFT","DAO",
    "USA","USD","EUR","GBP","JPY","CAD","AUD","UK","EU","UN","NATO",
    "OP","FOMO","YOLO","FUD","BTFD","HODL","LOL","WTF","FYI","DIY",
    "ETA","TLDR","EDIT","INFO","AFAIK","IIRC","FWIW","LMAO",
    "MON","TUE","WED","THU","FRI","SAT","SUN",
    "JAN","FEB","MAR","APR","JUN","JUL","AUG","SEP","OCT","NOV","DEC",
    "LINK","LIKE","LONG","PUTS","CALL","CALLS","HOLD","SELL","BUYS",
    "BULL","BEAR","CASH","LOSS","GAIN","WHEN","THEN","THIS","THAT",
    "WITH","FROM","BEEN","HAVE","WILL","JUST","SOME","THEY","THEM",
    "WERE","WHAT","ALSO","INTO","THAN","ONLY","BOTH","OVER","SUCH",
    "SAME","WELL","MAKE","TAKE","GIVE","KNOW","COME","BACK","VERY",
    "MUCH","STILL","EVERY","ABOUT","AFTER","AGAIN","BEING","BELOW",
    "COULD","DOING","FIRST","FOUND","GOING","GREAT","LARGE","LATER",
    "LOWER","MONEY","NEVER","OTHER","PRICE","RALLY","SINCE","SMALL",
    "STOCK","THEIR","THERE","THESE","THOSE","THREE","TODAY","TRADE",
    "UNDER","UNTIL","USING","WHERE","WHICH","WHILE","WORTH","WOULD",
    "YEARS","STOCKS","SHARE","SHARES","SHORT","DAILY","WEEK","MONTH",
    "YEAR","HIGH","LOWS","HIGHS","DOWN","NEXT","LAST","LOOK","GOOD",
    "BEST","REAL","EVEN","NEED","WANT","OPEN","PUTS",
}

TICKER_UNIVERSE -= EXCLUDE_WORDS


def extract_tickers(text):
    if not text or text in ("[removed]", "[deleted]"):
        return set()
    up = text.upper()
    found = set()
    for m in re.finditer(r'\$([A-Z]{1,5})\b', up):
        t = m.group(1)
        if t in TICKER_UNIVERSE:
            found.add(t)
    for m in re.finditer(r'\b([A-Z]{2,5})\b', up):
        t = m.group(1)
        if t in TICKER_UNIVERSE:
            found.add(t)
    return found


def init_db(db_path):
    conn = sqlite3.connect(str(db_path))
    conn.execute("""CREATE TABLE IF NOT EXISTS mentions (
        date TEXT NOT NULL, ticker TEXT NOT NULL,
        mention_count INTEGER NOT NULL DEFAULT 0,
        avg_score REAL NOT NULL DEFAULT 0,
        post_count INTEGER NOT NULL DEFAULT 0,
        PRIMARY KEY (date, ticker))""")
    conn.execute("""CREATE TABLE IF NOT EXISTS fetch_log (
        period TEXT PRIMARY KEY, sub_count INTEGER,
        comment_count INTEGER, fetched_at TEXT)""")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_mt ON mentions(ticker)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_md ON mentions(date)")
    conn.commit()
    return conn


def fetch_pullpush(endpoint, before, after, size=100, retries=3):
    """Fetch from PullPush. Returns newest-first list."""
    url = (f"{PULLPUSH_BASE}/{endpoint}/"
           f"?subreddit=wallstreetbets&size={size}"
           f"&after={after}&before={before}")
    for attempt in range(retries):
        try:
            resp = requests.get(url, timeout=30,
                                headers={"User-Agent": "WSB-Research-Bot/1.0"})
            if resp.status_code == 429:
                wait = int(resp.headers.get("Retry-After", 60))
                print(f"    Rate limited, waiting {wait}s...")
                time.sleep(wait)
                continue
            if resp.status_code == 200:
                return resp.json().get("data", [])
            print(f"    HTTP {resp.status_code}")
            time.sleep(2 ** attempt)
        except Exception as e:
            print(f"    Error: {e}, retry {attempt+1}/{retries}")
            time.sleep(2 ** attempt)
    return []


def collect_endpoint(endpoint, day_start, day_end, ticker_scores, ticker_post_ids,
                     delay, text_key="title+selftext"):
    """
    Paginate through all posts for one endpoint (submission or comment) for one day.
    Returns count of posts collected.
    PullPush is newest-first. We paginate backward:
      before = day_end -> get newest batch
      before = min(created_utc) - 1 -> get older batch
      stop when min(created_utc) <= day_start OR batch < size
    """
    before = day_end + 1
    after = day_start - 1
    seen_ids = set()
    total_count = 0
    max_batches = 50  # safety limit

    for batch_num in range(max_batches):
        posts = fetch_pullpush(endpoint, before=before, after=after, size=100)
        if not posts:
            break
        new_posts = [p for p in posts if p.get("id") not in seen_ids]
        if not new_posts:
            break

        for post in new_posts:
            seen_ids.add(post.get("id"))
            if text_key == "title+selftext":
                text = (post.get("title", "") + " " + post.get("selftext", ""))
            else:
                text = post.get("body", "")
            tickers = extract_tickers(text)
            score = post.get("score", 0) or 0
            pid = post.get("id", "")
            for t in tickers:
                ticker_scores[t].append(score)
                ticker_post_ids[t].add(pid)

        total_count += len(new_posts)

        # Advance: get the oldest timestamp in this batch to paginate backward
        min_ts = min(p.get("created_utc", before) for p in new_posts)
        before = min_ts  # exclusive upper bound for next batch

        time.sleep(delay)

        # Stop if we've exhausted the day window or batch was partial
        if len(new_posts) < 100 or min_ts <= day_start:
            break

    return total_count


def fetch_day(date_str, conn, delay=0.5):
    """Fetch all submissions+comments for one day. Returns (sub_count, comment_count) or None."""
    dt = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    day_start = int(dt.timestamp())
    day_end = int((dt + timedelta(days=1)).timestamp()) - 1

    cur = conn.execute("SELECT period FROM fetch_log WHERE period=?", (date_str,))
    if cur.fetchone():
        return None

    ticker_scores = defaultdict(list)
    ticker_post_ids = defaultdict(set)

    sub_count = collect_endpoint("submission", day_start, day_end,
                                 ticker_scores, ticker_post_ids, delay,
                                 text_key="title+selftext")
    comment_count = collect_endpoint("comment", day_start, day_end,
                                     ticker_scores, ticker_post_ids, delay,
                                     text_key="body")

    for ticker, scores in ticker_scores.items():
        avg_score = sum(scores) / len(scores) if scores else 0.0
        post_count = len(ticker_post_ids[ticker])
        mention_count = len(scores)
        conn.execute("""INSERT OR REPLACE INTO mentions (date, ticker, mention_count, avg_score, post_count)
            VALUES (?, ?, ?, ?, ?)""",
            (date_str, ticker, mention_count, avg_score, post_count))

    conn.execute("""INSERT OR REPLACE INTO fetch_log (period, sub_count, comment_count, fetched_at)
        VALUES (?, ?, ?, ?)""",
        (date_str, sub_count, comment_count, datetime.now(timezone.utc).isoformat()))
    conn.commit()
    return sub_count, comment_count


def fetch_range(start, end, db_path=DB_PATH, delay=0.5, verbose=True):
    conn = init_db(db_path)
    current = datetime.strptime(start, "%Y-%m-%d")
    end_dt = datetime.strptime(end, "%Y-%m-%d")
    total_sub = total_comment = 0
    days_done = days_skip = 0

    while current <= end_dt:
        ds = current.strftime("%Y-%m-%d")
        result = fetch_day(ds, conn, delay=delay)
        if result is None:
            if verbose:
                print(f"  {ds} -- skip (cached)")
            days_skip += 1
        else:
            sc, cc = result
            total_sub += sc
            total_comment += cc
            days_done += 1
            if verbose:
                print(f"  {ds} -- {sc} subs, {cc} comments")
        current += timedelta(days=1)

    conn.close()
    print(f"\nDone. Days: {days_done} new, {days_skip} skipped")
    print(f"Total: {total_sub} submissions, {total_comment} comments")
    return total_sub, total_comment


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", default="2023-01-01")
    parser.add_argument("--end", default="2023-06-30")
    parser.add_argument("--db", default=str(DB_PATH))
    parser.add_argument("--delay", type=float, default=0.5)
    args = parser.parse_args()
    print(f"Fetching WSB: {args.start} to {args.end}")
    fetch_range(args.start, args.end, Path(args.db), delay=args.delay)
