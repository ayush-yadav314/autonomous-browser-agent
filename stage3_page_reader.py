from playwright.sync_api import sync_playwright


def get_interactive_elements(page, max_text_length=40):
    """
    Finds clickable/typeable elements currently visible on screen
    (without scrolling) and returns them as a numbered list
    that an LLM can reason over.
    """
    elements = page.query_selector_all("input, button, a, textarea")
    numbered_elements = []

    viewport = page.viewport_size  # e.g. {'width': 1280, 'height': 720}

    for i, el in enumerate(elements):
        if not el.is_visible():
            continue

        box = el.bounding_box()
        if not box:
            continue

        # Skip elements outside the visible viewport (footer, below the fold, etc.)
        if box["y"] < 0 or box["y"] > viewport["height"]:
            continue

        tag = el.evaluate("el => el.tagName")
        text = (el.inner_text().strip() if el.inner_text() else "")
        placeholder = el.get_attribute("placeholder") or ""
        el_type = el.get_attribute("type") or ""

        # Skip elements with no useful identifying info at all
        if not text and not placeholder and not el_type:
            continue

        # Skip elements with long text (marketing copy, not real controls)
        if len(text) > max_text_length:
            continue

        description = f"[{i}] <{tag}> text='{text}' placeholder='{placeholder}' type='{el_type}'"
        numbered_elements.append((i, el, description))

    return numbered_elements


with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    page = browser.new_page()
    page.goto("https://duckduckgo.com")

    elements = get_interactive_elements(page)

    print(f"--- Page elements the AI would 'see' ({len(elements)} total) ---")
    for i, el, description in elements:
        print(description)

    page.wait_for_timeout(3000)
    browser.close()