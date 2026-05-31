import re
import requests
from datetime import date


def fetch_live_prices() -> dict:
    prices  = {}
    headers = {"User-Agent": "Mozilla/5.0"}

    gold_patterns = [
        r'([\d,]+\.?\d*)\s*PKR\s*per\s*gram',
        r'per gram[^<]*?(\d[\d,]*\.?\d*)',
        r'"price":\s*([\d.]+)',
    ]
    rate_patterns = [
        r'1\s*(?:USD|GBP|US Dollar|British Pound)[^<\d]*([\d,]+\.?\d+)\s*PKR',
        r'([\d,]+\.?\d+)\s*PKR',
    ]

    try:
        r = requests.get("https://goldpricez.com/pk/gram", headers=headers, timeout=10)
        for pat in gold_patterns:
            m = re.search(pat, r.text)
            if m:
                val = float(m.group(1).replace(",", ""))
                if val > 10_000:
                    prices["gold"] = val
                    break
    except Exception as e:
        print(f"  Warning: could not fetch gold price ({e})")

    for key, url in [
        ("usd", "https://wise.com/us/currency-converter/usd-to-pkr-rate"),
        ("gbp", "https://wise.com/us/currency-converter/gbp-to-pkr-rate"),
    ]:
        try:
            r = requests.get(url, headers=headers, timeout=10)
            for pat in rate_patterns:
                m = re.search(pat, r.text)
                if m:
                    val = float(m.group(1).replace(",", ""))
                    if val > 50:
                        prices[key] = val
                        break
        except Exception as e:
            print(f"  Warning: could not fetch {key}/PKR rate ({e})")

    prices.setdefault("gold", 40_626.33)
    prices.setdefault("usd",  278.46)
    prices.setdefault("gbp",  374.83)

    print(f"  Gold: PKR {prices['gold']:,.2f}/g | USD: {prices['usd']} | GBP: {prices['gbp']}")
    return prices


def fetch_pakistan_cpi_series() -> dict:
    """
    Fetches Pakistan annual CPI (World Bank FP.CPI.TOTL, base 2010=100) and
    interpolates to monthly via compound growth between adjacent annual values.
    Months beyond the last published year are extrapolated at the most recent
    known annual growth rate. Returns {} if the API is unreachable.
    """
    headers = {"User-Agent": "Mozilla/5.0"}
    url     = (
        "https://api.worldbank.org/v2/country/PK/indicator/FP.CPI.TOTL"
        "?format=json&per_page=30&mrv=30"
    )
    try:
        resp = requests.get(url, headers=headers, timeout=15)
        data = resp.json()
    except Exception as e:
        print(f"  Warning: could not fetch CPI from World Bank ({e})")
        return {}

    if len(data) < 2 or not data[1]:
        return {}

    annual = {
        int(e["date"]): e["value"]
        for e in data[1]
        if e.get("value") is not None
    }
    if len(annual) < 2:
        return {}

    today        = date.today()
    sorted_years = sorted(annual.keys())
    last, prev   = sorted_years[-1], sorted_years[-2]
    tail_rate    = (annual[last] / annual[prev]) - 1

    result = {}
    for year in range(sorted_years[0], today.year + 1):
        for month in range(1, 13):
            if year == today.year and month > today.month:
                break
            month_key = f"{year}-{month:02d}"

            if year in annual and (year - 1) in annual:
                rate = (annual[year] / annual[year - 1]) - 1
                cpi  = annual[year - 1] * ((1 + rate) ** (month / 12))
            elif year > last:
                months_ahead = (year - last) * 12 + month
                cpi = annual[last] * ((1 + tail_rate) ** (months_ahead / 12))
            elif year in annual:
                cpi = annual[year]
            else:
                continue

            result[month_key] = round(cpi, 2)

    if result:
        latest_m = max(result)
        print(f"  CPI: {len(result)} months (World Bank 2010=100, {latest_m}={result[latest_m]})")
    return result
