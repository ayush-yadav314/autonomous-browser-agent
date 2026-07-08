import re
import ollama
from playwright.sync_api import sync_playwright


def get_interactive_elements(page, max_text_length=40):
    elements = page.query_selector_all("input, button, textarea")
    numbered_elements = []
    viewport = page.viewport_size

    for i, el in enumerate(elements):
        if not el.is_visible():
            continue
        box = el.bounding_box()
        if not box:
            continue
        if box["y"] < 0 or box["y"] > viewport["height"]:
            continue

        tag = el.evaluate("el => el.tagName")
        text = (el.inner_text().strip() if el.inner_text() else "")
        placeholder = el.get_attribute("placeholder") or ""
        el_type = el.get_attribute("type") or ""

        if not text and not placeholder and not el_type:
            continue
        if len(text) > max_text_length:
            continue

        description = f"[{i}] <{tag}> text='{text}' placeholder='{placeholder}' type='{el_type}'"
        numbered_elements.append((i, el, description))

    return numbered_elements


def ask_llm_for_action(goal, elements_description, history, current_url):
    history_text = "\n".join(history) if history else "(no actions taken yet)"
    already_typed = any("TYPE" in h.upper() for h in history)

    typed_rule = (
        "You have ALREADY typed the search text. Your NEXT action MUST be CLICK on the search/submit button. Do NOT type again."
        if already_typed
        else "No text has been typed yet. Your FIRST action must be TYPE into the search input box."
    )

    prompt = f"""You are a browser automation agent.

GOAL: {goal}

CURRENT PAGE URL: {current_url}

ACTIONS ALREADY TAKEN:
{history_text}

IMPORTANT INSTRUCTION FOR THIS STEP: {typed_rule}

VISIBLE ELEMENTS (use the EXACT number in brackets, do not renumber them):
{elements_description}

RULES:
- Respond with EXACTLY ONE line and NOTHING else. No explanation, no parentheses, no extra words.
- Use the EXACT element number shown in brackets above.
- Only interact with elements relevant to the goal. Ignore menus, downloads, settings, unrelated links.
- Valid formats (pick ONE):
  TYPE [element_number] "text to type"
  CLICK [element_number]
  DONE "final answer"

Now output ONLY the single action line for the current state.
"""

    response = ollama.chat(
        model="phi3",
        messages=[{"role": "user", "content": prompt}]
    )
    return response["message"]["content"].strip()


def parse_action(decision_text):
    first_line = next((line.strip() for line in decision_text.splitlines() if line.strip()), decision_text)

    # TYPE with quotes (preferred format)
    match = re.search(r"TYPE\s*[\[#]?(\d+)\]?\s*(?:with)?\s*[\"'](.+?)[\"']", first_line, re.IGNORECASE)
    if match:
        return {"action": "TYPE", "element": int(match.group(1)), "text": match.group(2)}

    # TYPE with NO quotes at all — take everything after the number as the text
    match = re.search(r"TYPE\s*[\[#]?(\d+)\]?\s+(.+)", first_line, re.IGNORECASE)
    if match:
        return {"action": "TYPE", "element": int(match.group(1)), "text": match.group(2).strip()}

    match = re.search(r"CLICK\s*[\[#]?(\d+)\]?", first_line, re.IGNORECASE)
    if match:
        return {"action": "CLICK", "element": int(match.group(1))}

    match = re.search(r"DONE\s*[\"'](.+?)[\"']", first_line, re.IGNORECASE)
    if match:
        return {"action": "DONE", "answer": match.group(1)}

    return {"action": "UNKNOWN", "raw": decision_text}


def execute_action(page, elements, parsed):
    element_map = {i: el for i, el, _ in elements}

    try:
        if parsed["action"] == "TYPE":
            el = element_map.get(parsed["element"])
            if el:
                el.fill(parsed["text"], timeout=5000)
                print(f"Typed '{parsed['text']}' into element [{parsed['element']}]")
            else:
                print(f"Element [{parsed['element']}] not found")

        elif parsed["action"] == "CLICK":
            el = element_map.get(parsed["element"])
            if el:
                el.click(timeout=5000)
                print(f"Clicked element [{parsed['element']}]")
            else:
                print(f"Element [{parsed['element']}] not found")

        elif parsed["action"] == "DONE":
            print(f"Agent finished. Final answer: {parsed['answer']}")

        else:
            print(f"Could not understand action: {parsed.get('raw')}")

    except Exception as e:
        print(f"Action failed (element may be blocked/hidden/gone): {type(e).__name__}")


with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    page = browser.new_page()

    start_url = "https://www.amazon.in"
    page.goto(start_url)

    goal = "Search for 'books'"
    max_steps = 5
    history = []
    last_decision = None

    for step in range(max_steps):
        print(f"\n========== STEP {step + 1} ==========")

        url_before_action = page.url

        elements = get_interactive_elements(page)
        elements_text = "\n".join(desc for _, _, desc in elements)

        decision = ask_llm_for_action(goal, elements_text, history, page.url)
        print("--- LLM decision ---")
        print(decision)

        # Safeguard: if the model repeats the exact same decision twice in a row, stop
        if decision == last_decision:
            print("Same action repeated twice — stopping to avoid infinite loop.")
            break
        last_decision = decision

        parsed = parse_action(decision)
        print("--- Parsed action ---")
        print(parsed)

        was_click = parsed["action"] == "CLICK"

        execute_action(page, elements, parsed)
        history.append(decision)

        # Give the page a moment to finish navigating before checking the URL
        page.wait_for_timeout(1500)

        url_after_action = page.url
        if was_click and url_after_action != url_before_action:
            print(f"\nURL changed after click: {url_before_action} -> {url_after_action}")
            print("Goal achieved — action produced a page change.")
            break

        if parsed["action"] == "DONE":
            break

        page.wait_for_timeout(2000)

    page.wait_for_timeout(5000)
    browser.close()