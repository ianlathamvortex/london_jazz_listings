import sys
sys.path.insert(0, "scrapers")
from utils import fetch
import re

url = "https://www.606club.co.uk/events/view/errol-linton-13/"
soup = fetch(url)
out = []

if soup is None:
    out.append("fetch() returned None")
else:
    text = soup.get_text(separator=" ", strip=True)
    out.append(f"Text length: {len(text)}")
    out.append(f"First 800 chars: {text[:800]}")

    h1 = soup.find("h1")
    h2 = soup.find("h2")
    out.append(f"\nh1: {h1.get_text(strip=True) if h1 else None!r}")
    out.append(f"h2: {h2.get_text(strip=True) if h2 else None!r}")

    date_match = re.search(
        r"(\d{1,2})\w*\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)"
        r"(?:\s+(\d{4}))?",
        text, re.IGNORECASE
    )
    out.append(f"\ndate_match: {date_match.group(0) if date_match else None!r}")

open("debug_output_606b.txt", "w").write("\n".join(out))
print("\n".join(out))
