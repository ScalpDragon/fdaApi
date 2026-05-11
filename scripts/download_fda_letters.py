import asyncio
import os
import csv
import re
from playwright.async_api import async_playwright

# Configuration
BASE_URL = "https://www.fda.gov/drugs/warning-letters-and-notice-violation-letters-pharmaceutical-companies/untitled-letters"
# Since script is in '0-scripts', we save downloads one level up
DOWNLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SUMMARY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "download_summary.csv")

async def download_file(page, url, filename):
    """Downloads a file from a URL using the browser's download capability."""
    try:
        # We wrap goto in a try-except because it will "fail" when a download starts
        async with page.expect_download() as download_info:
            try:
                await page.goto(url, wait_until="commit") # wait_until="commit" is faster for downloads
            except:
                pass # Expected for downloads
        download = await download_info.value
        path = os.path.join(DOWNLOAD_DIR, filename)
        await download.save_as(path)
        return path
    except Exception as e:
        print(f"Error downloading {url}: {e}")
        return None

def sanitize_filename(name):
    """Sanitizes strings for use as filenames."""
    return re.sub(r'[\\/*?:"<>|]', "", name).strip()

async def scrape_fda_letters():
    if not os.path.exists(DOWNLOAD_DIR):
        os.makedirs(DOWNLOAD_DIR)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        # Create a persistent context or just a page
        context = await browser.new_context()
        page = await context.new_page()

        print(f"Navigating to {BASE_URL}...")
        await page.goto(BASE_URL)

        # Wait for the table to load
        await page.wait_for_selector("table")

        # Set entries to 100 to minimize pagination clicks
        try:
            await page.select_option("select[name='DataTables_Table_0_length']", "100")
            await asyncio.sleep(2) # Wait for table to refresh
        except:
            print("Could not change entries per page, proceeding with default.")

        all_data = []
        page_num = 1

        while True:
            print(f"Processing page {page_num}...")
            
            # Get all rows in the table body
            rows = await page.query_selector_all("table tbody tr")
            
            for row in rows:
                cells = await row.query_selector_all("td")
                if len(cells) < 3:
                    continue

                issued_date = (await cells[0].inner_text()).strip()
                company_cell = cells[1]
                company_name = (await company_cell.inner_text()).split('\n')[0].strip() # Get first line usually company
                product_issue = (await cells[2].inner_text()).strip()
                
                # Find the link for "Untitled Letter"
                links = await company_cell.query_selector_all("a")
                pdf_link = None
                for link in links:
                    text = await link.inner_text()
                    if "Untitled Letter" in text:
                        pdf_link = await link.get_attribute("href")
                        if pdf_link and not pdf_link.startswith("http"):
                            pdf_link = "https://www.fda.gov" + pdf_link
                        break

                if pdf_link:
                    # Construct filename: YYYY-MM-DD - Company Name - Untitled Letter.pdf
                    # Date might be MM/DD/YYYY, let's normalize it
                    date_norm = issued_date.replace("/", "-")
                    safe_company = sanitize_filename(company_name)
                    filename = f"{date_norm} - {safe_company} - Untitled Letter.pdf"
                    
                    all_data.append({
                        "Date": issued_date,
                        "Company": company_name,
                        "Product": product_issue,
                        "Link": pdf_link,
                        "Filename": filename
                    })

            # Check for "Next" button
            next_button = await page.query_selector("a.paginate_button.next:not(.disabled)")
            if next_button:
                await next_button.click()
                await asyncio.sleep(2) # Wait for page to load
                page_num += 1
            else:
                break

        print(f"Found {len(all_data)} letters. Starting downloads...")

        # Create summary CSV
        with open(SUMMARY_FILE, mode='w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=["Date", "Company", "Product", "Link", "Filename", "Status"])
            writer.writeheader()

            for entry in all_data:
                print(f"Downloading: {entry['Filename']}...")
                # Open a new tab for each download to avoid navigating away from the table
                download_page = await context.new_page()
                path = await download_file(download_page, entry['Link'], entry['Filename'])
                await download_page.close()
                
                entry["Status"] = "Downloaded" if path else "Failed"
                writer.writerow(entry)

        await browser.close()
        print("Done!")

if __name__ == "__main__":
    asyncio.run(scrape_fda_letters())
