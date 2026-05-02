import requests
import json
import datetime
import csv

AUTH_USER = ""
AUTH_KEY = ""

BASE_URL = "https://www.accessdata.fda.gov/rest/iresapi/recalls/"

HEADERS = {
    "Content-Type": "application/x-www-form-urlencoded",
    "Authorization-User": AUTH_USER,
    "Authorization-Key": AUTH_KEY,
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
}

DISPLAY_COLUMNS = ",".join([
    "productid", "recalleventid", "producttypeshort",
    "recallnum", "firmlegalnam", "productdescriptiontxt",
    "productshortreasontxt", "centercd", "centerclassificationtypetxt",
    "phasetxt", "recallinitiationdt", "centerclassificationdt",
    "terminationdt", "enforcementreportdt", "eventlmd",
    "firmcitynam", "firmstateprvncnam", "firmcountrynam",
    "distributionareasummarytxt", "productdistributedquantity",
])


def fetch_recalls(date_from, date_to, centers=None, classes=None, rows=100):
    """
    Fetch recall records from the FDA OII IRES API.

    Args:
        date_from: Start date string "MM/DD/YYYY"
        date_to:   End date string "MM/DD/YYYY"
        centers:   List of center codes, e.g. ["CDER", "CDRH"]
                   Options: CBER, CFSAN, CDER, CDRH, CTP, CVM
        classes:   List of classification types, e.g. ["1", "2", "3", "NC"]
        rows:      Number of results per page (max varies by server)

    Returns:
        List of recall record dicts
    """
    if centers is None:
        centers = ["CDER", "CDRH"]
    if classes is None:
        classes = ["1", "2", "3", "NC"]

    filters = [
        {"eventlmdfrom": date_from},
        {"eventlmdto": date_to},
        {"centerclassificationtypetxt": classes},
        {"centercd": centers},
    ]

    all_records = []
    start = 1

    while True:
        signature = str(int(datetime.datetime.now().timestamp()))
        url = BASE_URL + f"?signature={signature}"

        payload_obj = {
            "displaycolumns": DISPLAY_COLUMNS,
            "filter": json.dumps(filters),
            "start": start,
            "rows": rows,
            "sort": "recallinitiationdt",
            "sortorder": "desc",
        }

        # The API expects the payload as a URL-encoded string: payload={...}
        payload_str = "payload=" + json.dumps(payload_obj)

        response = requests.post(url, headers=HEADERS, data=payload_str)
        response.raise_for_status()

        data = response.json()

        # The response structure may vary; inspect it on first run
        print(f"Page starting at {start}: status={response.status_code}")
        if start == 1:
            print("Response keys:", list(data.keys()) if isinstance(data, dict) else type(data))

        # Adjust these keys based on actual response structure
        records = data.get("RESULT") or data.get("data") or data.get("results") or []
        if not records:
            print("No more records or unexpected response structure.")
            print("Full response:", json.dumps(data, indent=2)[:2000])
            break

        all_records.extend(records)
        print(f"  Fetched {len(records)} records (total so far: {len(all_records)})")

        total = data.get("RESULTCOUNT") or data.get("total") or data.get("count") or 0
        if len(all_records) >= total or len(records) < rows:
            break

        start += rows

    return all_records


def save_to_json(records, filename="recalls.json"):
    with open(filename, "w") as f:
        json.dump(records, f, indent=2)
    print(f"Saved {len(records)} records to {filename}")


def save_to_csv(records, filename="recalls.csv"):
    if not records:
        print("No records to save.")
        return
    keys = list(records[0].keys())
    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        writer.writerows(records)
    print(f"Saved {len(records)} records to {filename}")


if __name__ == "__main__":
    records = fetch_recalls(
        date_from="01/01/2024",
        date_to="12/31/2024",
        centers=["CDER", "CDRH"],   # Drug and Device recalls
        classes=["1", "2"],          # Class I and II only
        rows=50,
    )

    if records:
        save_to_json(records, "recalls_2024.json")
        save_to_csv(records, "recalls_2024.csv")
    else:
        print("No records returned. Check response structure above.")
