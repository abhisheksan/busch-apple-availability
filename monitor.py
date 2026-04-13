"""
Busch Light Apple NJ Monitor
Checks all NJ zip codes every 5 minutes for 55 minutes (runs inside a 1-hour scheduled agent).
Sends push notification via ntfy.sh when stores are found.
"""
import requests
import json
import time
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

# ── Config ────────────────────────────────────────────────────────────────────
NTFY_TOPIC   = os.environ.get("NTFY_TOPIC", "busch-apple-nj")
CHECK_EVERY  = 300   # seconds between scans (5 minutes)
TOTAL_RUNS   = 11    # run 11 times = 55 minutes, fits inside a 1-hour agent window
MAX_WORKERS  = 5     # concurrent API calls — keep low to avoid rate limiting
RADIUS_MILES = 25.0

PRODUCT_DESCRIPTIONS = [
    "BUSCH LIGHT APPLE 30/12 OZ CAN DSTK",
    "BUSCH LIGHT APPLE 24/12 OZ CAN 2/12",
    "BUSCH LIGHT APPLE 15/25 AL CAN SHRINK",
    "BUSCH LIGHT APPLE 24/12 OZ CAN",
    "BUSCH LIGHT APPLE 48/12 AL CAN",
    "BUSCH LIGHT APPLE 24/16 OZ CAN 4/6",
    "BUSCH LIGHT APPLE 1/2 BBL SV",
]

# All potential NJ zip codes (07001-08999). Invalid ones will error and be skipped.
NJ_ZIPS = [f"{z:05d}" for z in range(7001, 8000)] + \
          [f"{z:05d}" for z in range(8001, 9000)]

API_URL = "https://api.beertech.com/singularity/graphql"

HEADERS = {
    "sec-ch-ua-platform": '"macOS"',
    "referer": "https://www.busch.com/",
    "accept-language": "en-US,en;q=0.9",
    "sec-ch-ua": '"Chromium";v="143", "Not A(Brand";v="24"',
    "sec-ch-ua-mobile": "?0",
    "baggage": "app.name=busch-brand-website",
    "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "content-type": "application/json",
}

QUERY_TEMPLATE = """
query LocateRetailers {{
    locateRetailers(
        brandName: "BUSCH LT APPLE"
        limit: 100
        zipCode: "{zip}"
        radius: {radius}
        productDescriptions: {products}
    ) {{
        retailers {{
            vpid
            name
            address
            city
            state
            zipCode
            distance
        }}
    }}
}}
"""

def build_query(zipcode):
    products_gql = "[" + ",".join(f'"{p}"' for p in PRODUCT_DESCRIPTIONS) + "]"
    return QUERY_TEMPLATE.format(
        zip=zipcode,
        radius=RADIUS_MILES,
        products=products_gql,
    )


def check_zip(zipcode):
    """Returns list of retailers for a zip, or None if error/invalid."""
    try:
        resp = requests.post(
            API_URL,
            json={"query": build_query(zipcode)},
            headers=HEADERS,
            timeout=15,
        )
        body = resp.json()
        if body.get("errors"):
            return zipcode, None  # invalid zip or API error
        retailers = (
            (body.get("data") or {})
            .get("locateRetailers") or {}
        ).get("retailers", [])
        return zipcode, retailers
    except Exception:
        return zipcode, None


def scan_all_nj():
    """Scan all NJ zips. Returns dict of vpid -> store for any stores found."""
    found = {}
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(check_zip, z): z for z in NJ_ZIPS}
        for future in as_completed(futures):
            zipcode, retailers = future.result()
            if retailers:
                for store in retailers:
                    vpid = store.get("vpid") or f"{store['name']}|{store['address']}"
                    found[vpid] = store
    return found


def send_ntfy(stores):
    """Send a push notification listing the stores found."""
    store_lines = []
    for store in sorted(stores, key=lambda s: s.get("distance", 99)):
        store_lines.append(
            f"• {store['name']} — {store['address']}, {store['city']} "
            f"({store.get('distance', '?'):.1f} mi)"
        )

    body = f"{len(stores)} store(s) have Busch Light Apple in NJ!\n\n" + "\n".join(store_lines)
    try:
        requests.post(
            f"https://ntfy.sh/{NTFY_TOPIC}",
            data=body.encode("utf-8"),
            headers={
                "Title": "🍎 Busch Light Apple found in NJ!",
                "Priority": "high",
                "Tags": "beer,tada",
            },
            timeout=10,
        )
        print(f"[ntfy] Notification sent to topic '{NTFY_TOPIC}'")
    except Exception as e:
        print(f"[ntfy] Failed to send notification: {e}")


def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")


def main():
    log(f"Busch Light Apple NJ Monitor starting. "
        f"Will run {TOTAL_RUNS} scans, {CHECK_EVERY}s apart.")
    log(f"Notifications → ntfy.sh/{NTFY_TOPIC}")

    notified_vpids = set()  # avoid duplicate alerts within the same session

    for run in range(1, TOTAL_RUNS + 1):
        log(f"── Scan {run}/{TOTAL_RUNS} ──────────────────────────")
        found = scan_all_nj()

        if found:
            new_stores = {k: v for k, v in found.items() if k not in notified_vpids}
            if new_stores:
                log(f"FOUND {len(new_stores)} new store(s)!")
                for store in new_stores.values():
                    log(f"  → {store['name']}, {store['city']} {store['zipCode']} "
                        f"({store.get('distance', '?')} mi)")
                send_ntfy(list(new_stores.values()))
                notified_vpids.update(new_stores.keys())
            else:
                log(f"Found {len(found)} store(s) but all already notified this session.")
        else:
            log("No stores found in NJ.")

        if run < TOTAL_RUNS:
            log(f"Sleeping {CHECK_EVERY}s until next scan...")
            time.sleep(CHECK_EVERY)

    log("Session complete.")


if __name__ == "__main__":
    main()
