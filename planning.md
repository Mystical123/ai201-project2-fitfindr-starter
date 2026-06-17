# FitFindr — planning.md

> Complete this document before writing any implementation code.
> Your spec and agent diagram are what you'll use to direct AI tools (Claude, Copilot, etc.) to generate your implementation — the more specific they are, the more useful the generated code will be.
> Your planning.md will be reviewed as part of your submission.
> Update it before starting any stretch features.

---

## Tools

List every tool your agent will use. For each tool, fill in all four fields.
You must have at least 3 tools. The three required tools are listed — add any additional tools below them.

### Tool 1: search_listings

**What it does:**
Searches the mock listings dataset for items that match the user's description, size, and budget. Returns a ranked list of matching listings sorted by relevance (keyword match score).

**Input parameters:**
- `description` (str): A natural language description of the item the user is looking for (e.g. "vintage graphic tee", "baggy jeans"). Used to match against listing title, description, and style_tags.
- `size` (str): The user's size as a string (e.g. "M", "W30", "S/M"). Matched against the listing's `size` field. Optional — if None or empty string, size filtering is skipped.
- `max_price` (float): The maximum price the user is willing to pay. Filters out any listing where `price > max_price`.

**What it returns:**
A list of up to 5 listing dicts, each containing: `id` (str), `title` (str), `description` (str), `category` (str), `style_tags` (list[str]), `size` (str), `condition` (str), `price` (float), `colors` (list[str]), `brand` (str or None), `platform` (str). List is sorted descending by relevance score. Returns an empty list if nothing matches.

**What happens if it fails or returns nothing:**
If the list is empty, the agent sets an error message in session state: "No listings found for '[description]' in size [size] under $[max_price]. Try a broader description or higher budget." The agent returns this message to the user and stops — it does not proceed to suggest_outfit.

---

### Tool 2: suggest_outfit

**What it does:**
Given a specific listing item and the user's wardrobe, uses the LLM to suggest one or more complete outfit combinations that incorporate the new item. Considers color compatibility and style_tags overlap between the new item and wardrobe pieces.

**Input parameters:**
- `new_item` (dict): A single listing dict returned by search_listings (same fields: title, category, colors, style_tags, condition, price, platform).
- `wardrobe` (dict): A wardrobe dict with an `items` key containing a list of wardrobe item dicts. Each wardrobe item has: `id` (str), `name` (str), `category` (str), `colors` (list[str]), `style_tags` (list[str]), `notes` (str or None).

**What it returns:**
A string containing one or more outfit suggestions written in natural language — specific piece combinations (e.g. "Pair with your baggy dark-wash jeans and chunky white sneakers"), styling notes, and the overall vibe. Always references actual items from the wardrobe by name.

**What happens if it fails or returns nothing:**
If `wardrobe['items']` is empty, the agent skips wardrobe-based pairing and instead asks the LLM to suggest generic styling advice for the item. It informs the user: "You haven't added any wardrobe items, so here's a general styling suggestion:" followed by the generic advice. If the LLM call itself fails, return "Couldn't generate outfit suggestions right now — try again in a moment."

---

### Tool 3: create_fit_card

**What it does:**
Generates a short, shareable caption for the complete outfit — written in a casual, first-person social media voice. The output should sound like something a real person would post on Instagram or TikTok, not a product description.

**Input parameters:**
- `outfit` (str): The outfit suggestion string returned by suggest_outfit.
- `new_item` (dict): The listing dict for the thrifted item (used to pull in price, platform, title for the caption).

**What it returns:**
A single string of 1–3 sentences in casual first-person voice that references the specific item, where it was found, the price, and the overall look. Each call should produce a distinct output — the LLM prompt should include a temperature instruction or variation cue to avoid repetition.

**What happens if it fails or returns nothing:**
If `outfit` is an empty string or None, the agent returns: "Can't create a fit card without an outfit suggestion — something went wrong in the previous step." If the LLM call fails, return a fallback: "thrifted something good — details in my stories 🖤"

---

### Additional Tools (if any)

None for the base implementation.

---

## Planning Loop

**How does your agent decide which tool to call next?**

The planning loop runs as a sequential decision chain with early-exit conditions at each step:

1. **Parse user input** — extract `description`, `size`, and `max_price` from the user's natural language message using the LLM. Store these in session state.

2. **Call search_listings(description, size, max_price)**
   - If result is an empty list → set `session["error"] = "No listings found..."`, return the error message to the user, and exit the loop.
   - If result is non-empty → set `session["search_results"] = results` and `session["selected_item"] = results[0]`. Continue.

3. **Call suggest_outfit(selected_item, wardrobe)**
   - If result is an empty string or None → set `session["error"] = "Couldn't generate outfit suggestion"`, return error to user, and exit.
   - If result is a non-empty string → set `session["outfit_suggestion"] = result`. Continue.

4. **Call create_fit_card(outfit_suggestion, selected_item)**
   - Store result in `session["fit_card"]`.
   - Return the fit card to the user as the final response.

The loop knows it's done when `session["fit_card"]` is set, or when any step sets `session["error"]` and returns early.

---

## State Management

**How does information from one tool get passed to the next?**

A single `session` dictionary is created at the start of each user interaction and passed through the planning loop. It holds:

- `session["description"]` — parsed search query string
- `session["size"]` — parsed size string
- `session["max_price"]` — parsed max price float
- `session["search_results"]` — full list of matching listings from search_listings
- `session["selected_item"]` — the top result (results[0]), passed to suggest_outfit
- `session["wardrobe"]` — the user's wardrobe dict (loaded at session start via get_example_wardrobe())
- `session["outfit_suggestion"]` — the string returned by suggest_outfit, passed to create_fit_card
- `session["fit_card"]` — the final caption string returned by create_fit_card
- `session["error"]` — set if any tool fails; presence of this key signals early exit

Each tool receives only the session keys it needs — no tool reads the raw user message directly.

---

## Error Handling

For each tool, describe the specific failure mode you're handling and what the agent does in response.

| Tool | Failure mode | Agent response |
|------|-------------|----------------|
| search_listings | No results match the query | Returns: "No listings found for '[description]' in size [size] under $[max_price]. Try a broader description or raising your budget." Agent stops — does not call suggest_outfit. |
| suggest_outfit | Wardrobe is empty | Returns generic styling advice for the item and tells the user: "You haven't added wardrobe items, so here's a general styling suggestion:" — agent continues to create_fit_card with this output. |
| create_fit_card | Outfit input is missing or None | Returns: "Can't create a fit card without an outfit suggestion — something went wrong in the previous step." Agent exits and surfaces this message to the user. |

---

## Architecture

```
User query (natural language)
    │
    ▼
Planning Loop
    │
    ├─► [Parse] Extract description, size, max_price via LLM
    │       │
    │       ▼
    │   Session: description, size, max_price
    │       │
    ├─► search_listings(description, size, max_price)
    │       │
    │       ├── results=[] ──► "No listings found. Try broader search." → EXIT
    │       │
    │       │ results=[listing, ...]
    │       ▼
    │   Session: search_results=results, selected_item=results[0]
    │       │
    ├─► suggest_outfit(selected_item, wardrobe)
    │       │
    │       ├── wardrobe empty ──► generic styling advice (continues)
    │       ├── LLM fails ──► "Couldn't generate suggestions." → EXIT
    │       │
    │       │ outfit_suggestion="Pair with your wide-leg jeans..."
    │       ▼
    │   Session: outfit_suggestion=result
    │       │
    └─► create_fit_card(outfit_suggestion, selected_item)
            │
            ├── outfit=None ──► "Can't create fit card..." → EXIT
            │
            │ fit_card="thrifted this faded tee for $22..."
            ▼
        Session: fit_card=result
            │
            ▼
        Return fit_card to user ✓
```

---

## AI Tool Plan

**Milestone 3 — Individual tool implementations:**

For `search_listings`: I'll give Claude the Tool 1 spec from this file (inputs, return value, failure mode) and ask it to implement the function using `load_listings()` from `utils/data_loader.py`. I'll verify it filters by all three parameters, scores by keyword match against title/description/style_tags, returns a list of full listing dicts, and returns an empty list (not an error) when nothing matches. I'll test it with 3 queries: one that matches, one with a price that filters everything out, and one with a size that matches nothing.

For `suggest_outfit`: I'll give Claude the Tool 2 spec and the wardrobe schema from `data/wardrobe_schema.json`. I'll ask it to build a prompt that passes the new item's fields and the wardrobe items' names, colors, and style_tags to the LLM. I'll verify the output references actual wardrobe item names (not generic advice) when the wardrobe is non-empty, and falls back to generic advice when it's empty.

For `create_fit_card`: I'll give Claude the Tool 3 spec and two example fit cards from the assignment brief. I'll ask it to write a prompt that produces a casual first-person caption under 3 sentences. I'll verify it sounds social-media-ready (not a product description) by running it 3 times with different inputs and checking for variation.

**Milestone 4 — Planning loop and state management:**

I'll give Claude the Planning Loop section and Architecture diagram from this file and ask it to implement the loop in `agent.py` using the session dict pattern described in State Management. I'll verify that: (1) the loop exits early when search_listings returns empty, (2) session keys are populated correctly at each step, and (3) the final return value is the fit card string. I'll test the full flow end-to-end with the example query below.

---

## A Complete Interaction (Step by Step)

FitFindr takes a user's natural language request — what they're looking for, their size, budget, and wardrobe — and orchestrates three tools in sequence: it searches mock listings for matching items, suggests outfit combinations using the user's existing wardrobe, and generates a shareable fit card caption. Each tool is triggered by the output of the previous one — suggest_outfit only runs if search_listings returns a result, and create_fit_card only runs if suggest_outfit produces an outfit. If any tool fails or returns nothing, the agent tells the user what went wrong and either asks for more information or stops gracefully instead of continuing with bad data.

**Example user query:** "I'm looking for a vintage graphic tee under $30. I mostly wear baggy jeans and chunky sneakers. What's out there and how would I style it?"

**Step 1:**
The agent parses the user's message and extracts: `description="vintage graphic tee"`, `size=None` (not specified), `max_price=30.0`. It calls `search_listings("vintage graphic tee", size=None, max_price=30.0)`. The function scans listings.json, scores each item by keyword overlap with title/description/style_tags, filters out items over $30, and returns 2 matches: the Y2K Baby Tee ($18) and the Graphic Tee — 2003 Tour Bootleg Style ($24). Session stores both; `selected_item` is set to the top result: the Graphic Tee at $24 from Depop.

**Step 2:**
The agent calls `suggest_outfit(new_item=<Graphic Tee dict>, wardrobe=get_example_wardrobe())`. The LLM receives the item's details (black, graphic tee, grunge/streetwear tags) and the user's wardrobe (baggy dark-wash jeans, chunky white sneakers, black combat boots, vintage denim jacket). It returns: "Pair this with your baggy dark-wash jeans and chunky white sneakers for an effortless streetwear look — tuck the front slightly for shape. If you want to add a layer, throw your vintage black denim jacket over it for a grungier vibe." Session stores this as `outfit_suggestion`.

**Step 3:**
The agent calls `create_fit_card(outfit="Pair this with your baggy dark-wash jeans...", new_item=<Graphic Tee dict>)`. The LLM generates a casual first-person caption using the item title, platform, and price. It returns: "grabbed this 2003 bootleg tee off depop for $24 and it was made for my baggies 🖤 full fit in my stories". Session stores this as `fit_card`.

**Final output to user:**
The agent displays all three outputs in sequence:
1. "Found 2 listings. Top pick: Graphic Tee — 2003 Tour Bootleg Style, $24, Depop (good condition)"
2. The outfit suggestion paragraph
3. "Your fit card: grabbed this 2003 bootleg tee off depop for $24 and it was made for my baggies 🖤 full fit in my stories"
