"""Privacy‑focused web search. Brave Search API (primary), DuckDuckGo fallback."""
import os, requests, json
from datetime import datetime, date
from pathlib import Path
from dotenv import load_dotenv

# Load .env so the module always sees the Brave key
load_dotenv(Path(__file__).resolve().parent / '.env')
load_dotenv(os.path.expanduser('~/.env'))

SEARCH_LOG = os.path.expanduser("~/web_search.log")
DAILY_CAP_FILE = os.path.expanduser("~/search_daily_count.json")

def _load_daily_count():
    today = date.today().isoformat()
    try:
        with open(DAILY_CAP_FILE) as f:
            data = json.load(f)
            if data.get("date") == today:
                return data.get("count", 0)
    except:
        pass
    return 0

def _increment_daily_count():
    today = date.today().isoformat()
    count = _load_daily_count() + 1
    with open(DAILY_CAP_FILE, "w") as f:
        json.dump({"date": today, "count": count}, f)
    return count

def _log(query, result):
    with open(SEARCH_LOG, "a") as f:
        f.write(f"{datetime.now().isoformat()} | {query} | {result}\n")

def _brave_search(query, max_results=3):
    api_key = os.getenv("BRAVE_SEARCH_API_KEY", "")
    if not api_key:
        _log(query, "Brave key missing")
        return []
    url = "https://api.search.brave.com/res/v1/web/search"
    headers = {
        "Accept": "application/json",
        "Accept-Encoding": "gzip",
        "X-Subscription-Token": api_key
    }
    params = {"q": query, "count": max_results, "country": "US", "search_lang": "en"}
    try:
        resp = requests.get(url, headers=headers, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        results = []
        for item in data.get("web", {}).get("results", []):
            results.append({
                "title": item.get("title", ""),
                "snippet": item.get("description", "")[:500]
            })
        return results
    except Exception as e:
        _log(query, f"Brave error: {e}")
        return []

def _ddg_search(query, max_results=3):
    try:
        from ddgs import DDGS
        results = []
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=max_results):
                results.append({
                    "title": r.get("title", ""),
                    "snippet": r.get("body", "")[:300]
                })
        return results
    except Exception as e:
        _log(query, f"DDG error: {e}")
        return []

def search(query, max_results=3, daily_limit=50):
    count = _load_daily_count()
    if count >= daily_limit:
        _log(query, f"Daily limit reached ({count})")
        return []
    results = _brave_search(query, max_results) or _ddg_search(query, max_results)
    if results:
        _increment_daily_count()
        _log(query, f"{len(results)} results (total today: {_load_daily_count()})")
    else:
        _log(query, "No results")
    if _load_daily_count() >= int(daily_limit * 0.8):
        try:
            import config
            token = config.BOT_TOKEN
            chat_id = config.CHAT_ID
            if token and chat_id:
                requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                              json={"chat_id": chat_id, "text": f"Web search usage warning: {_load_daily_count()}/{daily_limit} queries today."})
        except:
            pass
    return results
