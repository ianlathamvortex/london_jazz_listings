import sys
sys.path.insert(0, "scrapers")
from utils import fetch, HEADERS
import requests

url = "https://www.vortexjazz.co.uk/events/2026-07-23/"
out = []

r = requests.get(url, headers=HEADERS, timeout=15)
out.append(f"HTTP status: {r.status_code}")
out.append(f"Response length: {len(r.text)}")

soup = fetch(url)
if soup is None:
    out.append("fetch() returned None")
else:
    a1 = soup.select("article.type-tribe_events")
    a2 = soup.select("div.tribe-event")
    out.append(f"article.type-tribe_events count: {len(a1)}")
    out.append(f"div.tribe-event count: {len(a2)}")

    # dump all <article> tags with their classes
    all_articles = soup.find_all("article")
    out.append(f"\nTotal <article> tags: {len(all_articles)}")
    for a in all_articles[:5]:
        out.append(f"  <article class={a.get('class')}>")

    # dump elements containing "Kate Williams" text
    kw = soup.find_all(string=lambda t: t and "Kate Williams" in t)
    out.append(f"\n'Kate Williams' text nodes found: {len(kw)}")
    for t in kw[:3]:
        parent = t.parent
        chain = []
        node = parent
        for _ in range(5):
            if node is None:
                break
            chain.append(f"{node.name}.{node.get('class')}")
            node = node.parent
        out.append(f"  text={t.strip()!r} ancestor_chain={chain}")

open("debug_output5.txt", "w").write("\n".join(out))
print("\n".join(out))
