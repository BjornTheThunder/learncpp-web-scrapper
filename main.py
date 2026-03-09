import requests
from bs4 import BeautifulSoup
import time
import os
from urllib.parse import urljoin, urlparse, urlunparse, quote_plus

# --- Configuration ---
START_URL = "https://www.learncpp.com/cpp-tutorial/introduction-to-these-tutorials/"
BASE_URL = "https://www.learncpp.com"
MAX_LESSONS = 50
STOP_TITLE = "C.1 — The end?"
OUTPUT_FOLDER = "content"
IMG_FOLDER = os.path.join(OUTPUT_FOLDER, "img")
CSS_FILENAME = "style.css"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}


def normalize_url(url):
    """Normalizes URLs to ensure consistent matching, stripping off #fragments."""
    if url.startswith("/"):
        url = urljoin(BASE_URL, url)
    parsed = urlparse(url)

    # Strip params, query, and fragment to get the base page URL
    clean_url = urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", "", ""))

    # Ensure it ends with a slash for exact matching
    if not clean_url.endswith("/"):
        clean_url += "/"

    return clean_url, parsed.fragment


def download_local_images(content_div):
    """Finds all images, downloads them to /img, and updates the HTML to point locally."""
    if not os.path.exists(IMG_FOLDER):
        os.makedirs(IMG_FOLDER)

    for img in content_div.find_all("img"):
        original_src = img.get("data-src") or img.get("src")
        if not original_src:
            continue

        full_img_url = urljoin(BASE_URL, original_src)
        parsed_url = urlparse(full_img_url)
        img_filename = os.path.basename(parsed_url.path)

        if not img_filename:
            img_filename = f"img_{int(time.time())}.png"

        local_path = os.path.join(IMG_FOLDER, img_filename)

        if not os.path.exists(local_path):
            try:
                img_data = requests.get(
                    full_img_url, headers=HEADERS, timeout=10
                ).content
                with open(local_path, "wb") as f:
                    f.write(img_data)
            except Exception as e:
                print(f"    ↳ Error downloading image: {e}")
                continue

        img["src"] = f"img/{img_filename}"
        if img.has_attr("data-src"):
            del img["data-src"]


def scrape_lesson(url):
    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        content_div = soup.find("div", class_="entry-content")
        if not content_div:
            return None, None

        next_url = None
        for link in soup.find_all("a", class_="nav-link"):
            if "next" in link.get_text(strip=True).lower():
                href = link.get("href")
                next_url = urljoin(BASE_URL, href) if href else None
                break

        download_local_images(content_div)

        unwanted = [
            "a.nav-link",
            ".nav-links",
            ".post-navigation",
            ".entry-navigation",
            ".prevnext",
            ".ezoic-ad",
            ".wpdiscuz-wrapper",
            ".sharedaddy",
            ".code-block",
        ]
        for sel in unwanted:
            for el in content_div.select(sel):
                el.decompose()

        title = soup.find("h1").get_text(strip=True) if soup.find("h1") else "Untitled"

        # We return the body as a string to be re-parsed in Phase 2
        return {"title": title, "body": str(content_div), "original_url": url}, next_url
    except Exception as e:
        print(f"Error scraping {url}: {e}")
        return None, None


def wrap_and_nav(lesson, idx, total):
    prev_link = (
        f'<a href="lesson_{idx - 1}.html">← Previous</a>'
        if idx > 0
        else "<span></span>"
    )
    next_link = (
        f'<a href="lesson_{idx + 1}.html">Next →</a>'
        if idx < total - 1
        else "<span></span>"
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>{lesson["title"]}</title>
    <link rel="stylesheet" href="{CSS_FILENAME}">
    <script>
    function cppSolutionToggle(e,l,s,h){{e.style.display=(e.style.display==='none'||e.style.display==='')?'block':'none';l.innerHTML=(e.style.display==='none')?s:h;}}
    function cppHintToggle(e,l,s,h){{cppSolutionToggle(e,l,s,h);}}
    </script>
</head>
<body>
    <div class="entry-content">
        <h1>{lesson["title"]}</h1>
        {lesson["body"]}
        <div class="local-lesson-nav">{prev_link}<a href="index.html">📚 Index</a>{next_link}</div>
    </div>
</body>
</html>"""


def run_scraper():
    if not os.path.exists(OUTPUT_FOLDER):
        os.makedirs(OUTPUT_FOLDER)
    current_url = START_URL
    all_lessons = []

    # --- PHASE 1: Scrape all pages into memory ---
    while current_url and len(all_lessons) < MAX_LESSONS:
        print(f"Scraping [{len(all_lessons) + 1}]: {current_url}")
        lesson_data, next_url = scrape_lesson(current_url)
        if lesson_data:
            all_lessons.append(lesson_data)
            if lesson_data["title"].strip() == STOP_TITLE:
                break
            current_url = next_url
            time.sleep(1.5)
        else:
            break

    print(f"\nProcessing internal links for {len(all_lessons)} lessons...")

    # --- PHASE 2a: Map original URLs to local filenames ---
    url_to_local_map = {}
    for i, lesson in enumerate(all_lessons):
        lesson["filename"] = f"lesson_{i}.html"
        clean_url, _ = normalize_url(lesson["original_url"])
        url_to_local_map[clean_url] = lesson["filename"]

    # --- PHASE 2b: Rewrite Links and Save Files ---
    for i, lesson in enumerate(all_lessons):
        soup = BeautifulSoup(lesson["body"], "html.parser")

        # Find all hyperlink tags
        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"]

            # Check if it's an internal LearnCPP link (or a relative link)
            if BASE_URL in href or href.startswith("/"):
                clean_target, fragment = normalize_url(href)

                if clean_target in url_to_local_map:
                    # ✅ Route to local file
                    new_href = url_to_local_map[clean_target]
                    if (
                        fragment
                    ):  # Preserve anchor jumps (e.g., lesson_5.html#chapter-1)
                        new_href += f"#{fragment}"
                    a_tag["href"] = new_href
                else:
                    # 🔍 Route to Google Search
                    link_text = a_tag.get_text(strip=True)
                    if not link_text:
                        link_text = "C++"
                    # quote_plus turns "C++ pointers" into "C%2B%2B+pointers"
                    search_query = quote_plus(f"C++ {link_text}")
                    a_tag["href"] = f"https://www.google.com/search?q={search_query}"
                    a_tag["target"] = "_blank"  # Open searches in a new tab

        # Update the body with rewritten links
        lesson["body"] = str(soup)

        # Wrap and save to disk
        with open(
            os.path.join(OUTPUT_FOLDER, lesson["filename"]), "w", encoding="utf-8"
        ) as f:
            f.write(wrap_and_nav(lesson, i, len(all_lessons)))

    # --- PHASE 3: Generate Index ---
    with open(os.path.join(OUTPUT_FOLDER, "index.html"), "w", encoding="utf-8") as f:
        list_items = "".join(
            [
                f'<li><a href="{l["filename"]}">{l["title"]}</a></li>'
                for l in all_lessons
            ]
        )
        f.write(
            f'<html><head><link rel="stylesheet" href="{CSS_FILENAME}"></head><body><div class="entry-content"><h1>Index</h1><ul>{list_items}</ul></div></body></html>'
        )

    print("✅ Done! Links are fully localized.")


if __name__ == "__main__":
    print("⚠️Project created for educational purposes only!")
    print("  Local copies shall not be redistributed as by owners wishes!")

    run_scraper()
