import sys
sys.path.insert(0, "scrapers")
from utils import fetch, HEADERS
import requests

url = "https://www.606club.co.uk/events/"
out = []

r = requests.get(url, headers=HEADERS, timeout=15)
out.append(f"HTTP status: {r.status_code}")
out.append(f"Response length: {len(r.text)}")

soup = fetch(url)
if soup is None:
    out.append("fetch() returned None")
else:
    links = soup.select("a[href*='/event/'], a[href*='/events/']")
    out.append(f"event-like links found: {len(links)}")
    for l in links[:10]:
        out.append(f"  href={l.get('href')!r} text={l.get_text(strip=True)[:60]!r}")

    # dump body text sample to see if calendar content loaded at all
    text = soup.get_text(separator=" | ", strip=True)
    out.append(f"\nBody text length: {len(text)}")
    out.append(f"First 1000 chars: {text[:1000]}")

open("debug_output_606.txt", "w").write("\n".join(out))
print("\n".join(out))
