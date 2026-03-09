import requests
from bs4 import BeautifulSoup
import time
import os
from urllib.parse import urljoin

# --- Configuration ---
START_URL = (
    "https://www.learncpp.com/cpp-tutorial/statements-and-the-structure-of-a-program/"
)
BASE_URL = "https://www.learncpp.com"
MAX_LESSONS = 3
OUTPUT_FOLDER = "content"
CSS_FILENAME = "style.css"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}


def scrape_lesson(url):
    """Scrapes content, cleans out original nav/ads, and finds the Next URL."""
    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        # 1. Identify Content
        content_div = soup.find("div", class_="entry-content")
        if not content_div:
            return None, None

        # 2. Extract Next URL before we start decomposing tags
        next_url = None
        nav_links = soup.find_all("a", class_="nav-link")
        for link in nav_links:
            if "next" in link.get_text(strip=True).lower():
                href = link.get("href")
                next_url = urljoin(BASE_URL, href) if href else None
                break

        # 3. CLEANING PHASE
        # Remove original nav-links, ads, and social sharing sidebars
        unwanted_selectors = [
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
        for selector in unwanted_selectors:
            for element in content_div.select(selector):
                element.decompose()

        # 4. Fix Image URLs for offline viewing
        for img in content_div.find_all("img"):
            if img.get("src") and img["src"].startswith("/"):
                img["src"] = urljoin(BASE_URL, img["src"])

        title = soup.find("h1").get_text(strip=True) if soup.find("h1") else "Untitled"

        return {"title": title, "body": content_div.prettify()}, next_url

    except Exception as e:
        print(f"Error scraping {url}: {e}")
        return None, None


def wrap_and_nav(lesson, idx, total):
    """Wraps body in Material UI structure and injects LOCAL navigation."""

    # Create Local Navigation HTML
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

    nav_html = f"""
    <div class="local-lesson-nav">
        {prev_link}
        <a href="index.html">📚 All Lessons</a>
        {next_link}
    </div>"""

    # JavaScript for Quiz Toggles (as discussed previously)
    js_toggle_script = """
    <script>
    function cppSolutionToggle(element, link, showText, hideText) {
        if (element.style.display === 'none' || element.style.display === '') {
            element.style.display = 'block';
            link.innerHTML = hideText;
        } else {
            element.style.display = 'none';
            link.innerHTML = showText;
        }
    }
    function cppHintToggle(element, link, showText, hideText) {
        cppSolutionToggle(element, link, showText, hideText);
    }
    </script>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{lesson["title"]}</title>
    <link rel="stylesheet" href="{CSS_FILENAME}">
    {js_toggle_script}
</head>
<body>
    <div class="entry-content">
        <h1>{lesson["title"]}</h1>
        {lesson["body"]}
        {nav_html}
    </div>
</body>
</html>"""


def run_scraper():
    if not os.path.exists(OUTPUT_FOLDER):
        os.makedirs(OUTPUT_FOLDER)

    current_url = START_URL
    all_lessons = []

    # Phase 1: Scrape into memory
    while current_url and len(all_lessons) < MAX_LESSONS:
        print(f"Scraping [{len(all_lessons) + 1}/{MAX_LESSONS}]: {current_url}")
        lesson_data, next_url = scrape_lesson(current_url)

        if lesson_data:
            all_lessons.append(lesson_data)
            current_url = next_url
            time.sleep(2)
        else:
            break

    # Phase 2: Save files with local navigation
    print(f"\nFinalizing {len(all_lessons)} local files...")
    for i, lesson in enumerate(all_lessons):
        filename = f"lesson_{i}.html"
        final_html = wrap_and_nav(lesson, i, len(all_lessons))

        with open(os.path.join(OUTPUT_FOLDER, filename), "w", encoding="utf-8") as f:
            f.write(final_html)
        lesson["filename"] = filename

    # Phase 3: Generate Index
    with open(os.path.join(OUTPUT_FOLDER, "index.html"), "w", encoding="utf-8") as f:
        list_items = "".join(
            [
                f'<li><a href="{l["filename"]}">{l["title"]}</a></li>'
                for l in all_lessons
            ]
        )
        f.write(
            f'<html><head><link rel="stylesheet" href="{CSS_FILENAME}"></head><body>'
        )
        f.write(
            f'<div class="entry-content"><h1>C++ Course Index</h1><ul class="lesson-list">{list_items}</ul></div></body></html>'
        )

    print(f"\n✅ Success! Scraped {len(all_lessons)} lessons into '{OUTPUT_FOLDER}/'")


if __name__ == "__main__":
    run_scraper()

