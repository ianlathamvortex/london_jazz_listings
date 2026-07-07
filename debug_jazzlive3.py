import sys
sys.path.insert(0, "scrapers")
from utils import fetch

url = "https://www.jazzlive.co.uk/guide.html"
soup = fetch(url)
out = []

h3s = soup.select("h3")
out.append(f"Total h3: {len(h3s)}")
for h3 in h3s:
    out.append(f" - {h3.get_text(strip=True)!r}")

# also check box_blog_top count directly
boxes = soup.select("div.box_blog_top")
out.append(f"\nTotal div.box_blog_top: {len(boxes)}")
for b in boxes:
    date_div = b.select_one("div.blog_date")
    title_div = b.select_one("div.blog_title")
    out.append(f" - date={date_div.get_text(' ',strip=True) if date_div else None!r} title={title_div.get_text(strip=True) if title_div else None!r}")

open("debug_output3.txt", "w").write("\n".join(out))
print("\n".join(out))
