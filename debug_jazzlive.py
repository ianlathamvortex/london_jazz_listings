import sys
sys.path.insert(0, "scrapers")
from utils import fetch, HEADERS
import requests

url = "https://www.jazzlive.co.uk/guide.html"
out = []

r = requests.get(url, headers=HEADERS, timeout=15)
out.append(f"HTTP status: {r.status_code}")
out.append(f"Response length: {len(r.text)}")
out.append(f"First 500 chars of raw HTML:\n{r.text[:500]}")

soup = fetch(url)
if soup is None:
    out.append("fetch() returned None")
else:
    h3s = soup.select("h3")
    out.append(f"\nNumber of h3 tags found: {len(h3s)}")
    for i, h3 in enumerate(h3s[:3]):
        out.append(f"\n--- h3 #{i}: {h3.get_text(strip=True)!r} ---")
        parent = h3.parent
        depth = 0
        while parent and parent.name not in ("div", "section", "article", "body"):
            parent = parent.parent
            depth += 1
        out.append(f"Walked up {depth} levels to find parent tag: {parent.name if parent else None}")
        if parent:
            classes = parent.get("class")
            out.append(f"Parent classes: {classes}")
            block_text = parent.get_text(separator=" ", strip=True)
            out.append(f"block_text length: {len(block_text)}")
            out.append(f"block_text first 300 chars: {block_text[:300]!r}")

open("debug_output.txt", "w").write("\n".join(out))
print("\n".join(out))
