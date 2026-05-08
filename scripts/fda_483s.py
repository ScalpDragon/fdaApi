import requests
import json
import csv
import os

# Output directory helper
OUTPUT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'outputs'))

def make_output_path(filename):
    return os.path.join(OUTPUT_DIR, filename)
from config import AUTH_USER, AUTH_KEY

BASE_URL = "https://api-datadashboard.fda.gov/v1/"

HEADERS = {
    "Content-Type": "application/json",
    "Authorization-User": AUTH_USER,
    "Authorization-Key": AUTH_KEY,
}

# Fields for the inspections_classifications endpoint
INSPECTION_COLUMNS = [
    "FEINumber",
    "LegalName",
    "AddressLine1",
    "City",
    "StateCode",
    "CountryName",
    "InspectionID",
    "InspectionEndDate",
    "FiscalYear",
    "Classification",
    "ClassificationCode",
    "ProductType",
    "PostedCitations",
    "ProjectArea",
    "FirmProfile",
]

# Fields for the inspections_citations endpoint (the actual 483 observations)
CITATION_COLUMNS = [
    "FEINumber",
    "LegalName",
    "InspectionID",
    "InspectionEndDate",
    "CitationID",
    "ActCFRNumber",
    "ShortDescription",
    "LongDescription",
    "ProgramArea",
]


def fetch_inspections(date_from, date_to, product_type="Drugs", classifications=None, rows=1000):
    """
    Fetch drug inspection records (CDER) from the FDA Data Dashboard API.

    Args:
        date_from:       Start date string "YYYY-MM-DD"
        date_to:         End date string "YYYY-MM-DD"
        product_type:    "Drugs" for CDER, "Devices" for CDRH, "Biologics" for CBER, etc.
        classifications: List of classification codes to include.
                         Options: "NAI", "VAI", "OAI"
                         Default: ["VAI", "OAI"] (inspections most likely to have 483s)
        rows:            Results per page (max 5000)

    Returns:
        List of inspection record dicts
    """
    if classifications is None:
        classifications = ["VAI", "OAI"]

    filters = {
        "ProductType": [product_type],
        "ClassificationCode": classifications,
        "InspectionEndDateFrom": [date_from],
        "InspectionEndDateTo": [date_to],
    }

    all_records = []
    start = 1

    print(f"\nFetching {product_type} inspections from {date_from} to {date_to}...")
    print(f"Classifications: {classifications}")

    while True:
        payload = {
            "start": start,
            "rows": rows,
            "returntotalcount": True,
            "sort": "InspectionEndDate",
            "sortorder": "DESC",
            "filters": filters,
            "columns": INSPECTION_COLUMNS,
        }

        response = requests.post(BASE_URL + "inspections_classifications", headers=HEADERS, json=payload)
        response.raise_for_status()
        data = response.json()

        if start == 1:
            print(f"Response status: {data.get('statuscode')} - {data.get('message')}")
            total = data.get("totalrecordcount", 0)
            print(f"Total matching records: {total}")

        records = data.get("result") or []
        if not records:
            break

        all_records.extend(records)
        print(f"  Fetched {len(records)} records (total so far: {len(all_records)})")

        total = data.get("totalrecordcount", 0)
        if len(all_records) >= total or len(records) < rows:
            break

        start += rows

    return all_records


def fetch_citations(fei_numbers, rows=5000):
    """
    Fetch 483 observation citations for a list of FEI numbers.

    Args:
        fei_numbers: List of FEI number strings from inspection records
        rows:        Results per page (max 5000)

    Returns:
        List of citation record dicts
    """
    if not fei_numbers:
        return []

    # API accepts up to ~1000 FEI numbers per request; chunk if needed
    chunk_size = 500
    all_citations = []

    for i in range(0, len(fei_numbers), chunk_size):
        chunk = fei_numbers[i : i + chunk_size]
        print(f"\nFetching citations for FEI batch {i // chunk_size + 1} ({len(chunk)} FEIs)...")

        start = 1
        while True:
            payload = {
                "start": start,
                "rows": rows,
                "returntotalcount": True,
                "sort": "InspectionEndDate",
                "sortorder": "DESC",
                "filters": {"FEINumber": chunk},
                "columns": CITATION_COLUMNS,
            }

            response = requests.post(BASE_URL + "inspections_citations", headers=HEADERS, json=payload)
            response.raise_for_status()
            data = response.json()

            if start == 1:
                total = data.get("totalrecordcount", 0)
                print(f"  Total citations in this batch: {total}")

            records = data.get("result") or []
            if not records:
                break

            all_citations.extend(records)

            total = data.get("totalrecordcount", 0)
            if len(all_citations) >= total or len(records) < rows:
                break

            start += rows

    print(f"Total citations fetched: {len(all_citations)}")
    return all_citations


def save_to_json(records, filename):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2)
    print(f"Saved {len(records)} records to {filename}")


def save_to_csv(records, filename):
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
    DATE_FROM = "2025-01-01"
    DATE_TO   = "2025-12-31"

    # Derive year tag from the date range for dynamic output filenames
    year_tag = DATE_FROM[:4]

    # --- Step 1: Fetch CDER drug inspection classifications ---
    inspections = fetch_inspections(
        date_from=DATE_FROM,
        date_to=DATE_TO,
        product_type="Drugs",           # CDER
        classifications=["VAI", "OAI"], # Include NAI too if you want all inspections
    )

    if inspections:
        save_to_json(inspections, make_output_path(f"cder_483_inspections_{year_tag}.json"))
        save_to_csv(inspections, make_output_path(f"cder_483_inspections_{year_tag}.csv"))
    else:
        print("No inspection records returned.")

    # --- Step 2: (Optional) Fetch the actual 483 observation citations ---
    # Only pull citations for inspections that have posted citations
    feis_with_citations = [
        r["FEINumber"]
        for r in inspections
        if r.get("PostedCitations") not in (None, "", "0", 0, False)
    ]
    feis_with_citations = list(set(feis_with_citations))  # deduplicate
    print(f"\n{len(feis_with_citations)} unique FEIs with posted citations found.")

    if feis_with_citations:
        citations = fetch_citations(feis_with_citations)
        if citations:
            save_to_json(citations, make_output_path(f"cder_483_citations_{year_tag}.json"))
            save_to_csv(citations, make_output_path(f"cder_483_citations_{year_tag}.csv"))
        else:
            print("No citation records returned.")
    else:
        print("No FEIs with posted citations; skipping citation fetch.")
