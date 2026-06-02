import re
import requests
from datetime import date


def fetch_live_prices() -> dict:
    prices  = {}
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
        )
    }

    # goldpricez.com renders the live 24k PKR/gram into a #gold_price span and a
    # price_24K_Ounce cell (value is per-gram on the /gram page despite the id).
    # A JS price object (gold = USD/oz, global_usd_rate, global_unit_conv = g/oz)
    # is the formula fallback if the markup changes again.
    gold_patterns = [
        r'id=["\']gold_price["\'][^>]*>\s*=?\s*([\d,]+\.?\d*)',
        r'id=["\']price_24K_Ounce["\'][^>]*>\s*([\d,]+\.?\d*)',
    ]
    rate_patterns = [
        r'1\s*(?:USD|GBP|US Dollar|British Pound)[^<\d]*([\d,]+\.?\d+)\s*PKR',
        r'([\d,]+\.?\d+)\s*PKR',
    ]

    def _plausible_gold(v):
        return 10_000 < v < 1_000_000

    try:
        r = requests.get("https://goldpricez.com/pk/gram", headers=headers, timeout=10)
        for pat in gold_patterns:
            m = re.search(pat, r.text)
            if m:
                val = float(m.group(1).replace(",", ""))
                if _plausible_gold(val):
                    prices["gold"] = val
                    break
        # Formula fallback: spot USD/oz × USD-PKR × (troy-oz → gram conversion)
        if "gold" not in prices:
            g = re.search(r'gold\s*:\s*([\d.]+)', r.text)
            u = re.search(r'global_usd_rate\s*=\s*([\d.]+)', r.text)
            c = re.search(r'global_unit_conv\s*=\s*([\d.]+)', r.text)
            if g and u and c:
                val = float(g.group(1)) * float(u.group(1)) * float(c.group(1))
                if _plausible_gold(val):
                    prices["gold"] = round(val, 2)
        if "gold" not in prices:
            print("  Warning: gold price markup not matched — using fallback")
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
