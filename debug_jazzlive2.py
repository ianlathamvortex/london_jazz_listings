import sys
sys.path.insert(0, "scrapers")
from utils import fetch

url = "https://www.jazzlive.co.uk/guide.html"
soup = fetch(url)
out = []

h3 = soup.select("h3")[0]
node = h3
for level in range(6):
    node = node.parent
    if node is None:
        break
    classes = node.get("class")
    out.append(f"Level {level+1} up: <{node.name} class={classes}>")
    # show direct children tag+class summary
    children_summary = []
    for child in node.find_all(recursive=False):
        children_summary.append(f"{child.name}.{child.get('class')}")
    out.append(f"  direct children: {children_summary}")
    text_preview = node.get_text(separator=' | ', strip=True)[:200]
    out.append(f"  text preview: {text_preview!r}")

open("debug_output2.txt", "w").write("\n".join(out))
print("\n".join(out))
