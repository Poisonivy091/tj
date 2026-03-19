import httpx

SEC_BASE = "https://efts.sec.gov/LATEST"
EDGAR_BASE = "https://data.sec.gov"
HEADERS = {
    "User-Agent": "TradingJournal/1.0 (contact@example.com)",
    "Accept": "application/json",
}


async def search_company_filings(ticker: str, form_type: str = "10-K", count: int = 5) -> list[dict]:
    """Search SEC EDGAR for recent filings (10-K, 10-Q, 8-K, etc.)."""
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{SEC_BASE}/search-index",
            params={
                "q": f"\"{ticker}\"",
                "dateRange": "custom",
                "forms": form_type,
                "from": "0",
                "size": str(count),
            },
            headers=HEADERS,
            timeout=15,
        )
        if resp.status_code != 200:
            return []
        data = resp.json()
    hits = data.get("hits", {}).get("hits", [])
    return [
        {
            "form_type": h.get("_source", {}).get("form_type", ""),
            "filed_at": h.get("_source", {}).get("file_date", ""),
            "description": h.get("_source", {}).get("display_names", [""])[0] if h.get("_source", {}).get("display_names") else "",
            "url": f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&company={ticker}&type={form_type}&dateb=&owner=include&count=5",
        }
        for h in hits
    ]


async def get_insider_trades(cik: str, count: int = 10) -> list[dict]:
    """Get recent insider trading filings (Form 4) from SEC EDGAR."""
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{SEC_BASE}/search-index",
            params={
                "q": f"\"{cik}\"",
                "forms": "4",
                "from": "0",
                "size": str(count),
            },
            headers=HEADERS,
            timeout=15,
        )
        if resp.status_code != 200:
            return []
        data = resp.json()
    hits = data.get("hits", {}).get("hits", [])
    return [
        {
            "filed_at": h.get("_source", {}).get("file_date", ""),
            "filer": h.get("_source", {}).get("display_names", [""])[0] if h.get("_source", {}).get("display_names") else "",
            "form_type": "4",
        }
        for h in hits
    ]


async def get_company_tickers_cik(ticker: str) -> str | None:
    """Resolve a ticker to a CIK number via SEC company tickers JSON."""
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{EDGAR_BASE}/submissions/CIK{ticker}.json",
            headers=HEADERS,
            timeout=10,
        )
        if resp.status_code == 200:
            data = resp.json()
            return data.get("cik", None)

    # Fallback: search full-text
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{SEC_BASE}/search-index",
            params={"q": f"\"{ticker}\"", "forms": "10-K", "size": "1"},
            headers=HEADERS,
            timeout=10,
        )
        if resp.status_code == 200:
            data = resp.json()
            hits = data.get("hits", {}).get("hits", [])
            if hits:
                return hits[0].get("_source", {}).get("ciks", [None])[0]
    return None
