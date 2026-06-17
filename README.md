# FitFindr

A multi-tool AI agent that helps users find secondhand clothing and figure out how to wear it. Given a natural language query, FitFindr searches mock thrift listings, suggests outfit combinations using the user's wardrobe, and generates a shareable fit card caption.

---

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Create a `.env` file in the project root:

```
GROQ_API_KEY=your_key_here
```

Run the app:

```bash
python app.py
```

Open the URL shown in your terminal (usually `http://localhost:7860`).

---

## Tool Inventory

### `search_listings(description, size, max_price)`
**Purpose:** Searches the mock listings dataset for items matching the user's query, size, and budget.

| Parameter | Type | Description |
|-----------|------|-------------|
| `description` | `str` | Keywords describing the item (e.g. "vintage graphic tee") |
| `size` | `str \| None` | Size string to filter by (e.g. "M", "W30"). `None` skips size filtering. |
| `max_price` | `float \| None` | Maximum price inclusive. `None` skips price filtering. |

**Returns:** `list[dict]` — a list of matching listing dicts sorted by relevance score (highest first). Each dict contains: `id`, `title`, `description`, `category`, `style_tags`, `size`, `condition`, `price`, `colors`, `brand`, `platform`. Returns an empty list if nothing matches — never raises an exception.

---

### `suggest_outfit(new_item, wardrobe)`
**Purpose:** Given a thrifted item and the user's current wardrobe, uses the LLM to suggest 1–2 specific outfit combinations.

| Parameter | Type | Description |
|-----------|------|-------------|
| `new_item` | `dict` | A listing dict returned by `search_listings` |
| `wardrobe` | `dict` | A wardrobe dict with an `items` key (list of wardrobe item dicts). May be empty. |

**Returns:** `str` — a natural language outfit suggestion referencing specific wardrobe pieces by name. If the wardrobe is empty, returns general styling advice instead of crashing.

---

### `create_fit_card(outfit, new_item)`
**Purpose:** Generates a short, casual first-person caption for the outfit — the kind of thing someone would post on Instagram or TikTok.

| Parameter | Type | Description |
|-----------|------|-------------|
| `outfit` | `str` | The outfit suggestion string from `suggest_outfit` |
| `new_item` | `dict` | The listing dict for the thrifted item |

**Returns:** `str` — a 2–3 sentence caption mentioning the item name, price, and platform naturally. Uses LLM temperature 1.0 for variation. Returns a descriptive error string if `outfit` is empty — never raises an exception.

---

## How the Planning Loop Works

The planning loop runs as a sequential decision chain with early-exit conditions:

1. **Parse the query** — the LLM extracts `description`, `size`, and `max_price` from the user's natural language input. Falls back to using the raw query as the description if parsing fails.

2. **Call `search_listings`** — if the result is an empty list, the agent sets an error message and returns immediately. It does **not** proceed to `suggest_outfit` with empty input.

3. **Select the top result** — `session["selected_item"]` is set to `results[0]`.

4. **Call `suggest_outfit`** — passes the selected item and the user's wardrobe. The result is stored in `session["outfit_suggestion"]`.

5. **Call `create_fit_card`** — passes the outfit suggestion and selected item. The result is stored in `session["fit_card"]`.

6. **Return the session** — the caller checks `session["error"]` first; if it's `None`, all three output fields are populated.

The key behavior: if `search_listings` returns no results, steps 4–6 never execute. The agent branches, not runs a fixed sequence.

---

## State Management

A single `session` dict is created at the start of each interaction and passed through the entire planning loop. It holds:

| Key | Set when | Used by |
|-----|----------|---------|
| `session["query"]` | Start | Logging / display |
| `session["parsed"]` | After query parse | `search_listings` call |
| `session["search_results"]` | After `search_listings` | Early-exit check |
| `session["selected_item"]` | After search succeeds | `suggest_outfit`, `create_fit_card`, UI |
| `session["wardrobe"]` | Start | `suggest_outfit` |
| `session["outfit_suggestion"]` | After `suggest_outfit` | `create_fit_card` |
| `session["fit_card"]` | After `create_fit_card` | UI output |
| `session["error"]` | On any failure | UI output, early-exit signal |

No tool reads the raw user query directly — everything flows through session keys. This means `suggest_outfit` always receives the exact same dict that `search_listings` returned, not a re-parsed version.

---

## Error Handling

| Tool | Failure mode | Agent response |
|------|-------------|----------------|
| `search_listings` | No listings match the query | Sets `session["error"]`: "No listings found for '[description]' in size [size] under $[price]. Try a broader description, a different size, or a higher budget." Agent stops — does not call `suggest_outfit`. |
| `suggest_outfit` | Wardrobe is empty (`wardrobe["items"] == []`) | Returns general styling advice (e.g. "This tee would look adorable with high-waisted mom jeans and chunky sneakers for a retro vibe."). Agent continues to `create_fit_card` with this output. |
| `create_fit_card` | `outfit` is empty or whitespace-only | Returns: "Can't create a fit card without an outfit suggestion — something went wrong in the previous step." Does not call the LLM. |

**Concrete examples from testing:**

- `search_listings("designer ballgown", size="XXS", max_price=5)` → `[]`, no exception
- `suggest_outfit(results[0], get_empty_wardrobe())` → *"This tee would look adorable with high-waisted mom jeans and chunky sneakers for a retro vibe..."*
- `create_fit_card("", results[0])` → *"Can't create a fit card without an outfit suggestion — something went wrong in the previous step."*

---

## Spec Reflection

**One way the spec helped:** Writing the planning loop in plain conditional English in `planning.md` before touching code made the implementation nearly mechanical — each `if not results: return session` line maps directly to a line in the spec. The early-exit logic would have been easy to skip without having written it out first.

**One way implementation diverged from the spec:** The spec described query parsing as a simple extraction step. In practice, the LLM occasionally returns price values as strings (e.g. `"$30"`) rather than numbers, requiring a cleanup step that wasn't in the original plan. A fallback to raw query as description also proved necessary when the LLM returned malformed JSON.

---

## AI Usage

**Instance 1 — Tool implementations (`tools.py`):**
I gave Claude the Tool 1–3 spec blocks from `planning.md` (inputs, return values, failure modes) and the `load_listings()` docstring from `utils/data_loader.py`. I asked it to implement all three functions. Before running the output, I reviewed that `search_listings` filtered by all three parameters and returned an empty list (not `None`) on no match. I changed the scoring function to use `.split()` on the description rather than character-level matching, which produced better relevance ranking on multi-word queries like "vintage graphic tee."

**Instance 2 — Planning loop (`agent.py`):**
I gave Claude the Planning Loop section, State Management section, and ASCII architecture diagram from `planning.md`. I asked it to implement `run_agent()` following the session dict pattern. The generated code called `suggest_outfit` unconditionally before checking whether `search_results` was empty — I caught this in review and fixed the early-exit branch to return before the `suggest_outfit` call. I also added the `_parse_query` helper separately after realizing the generated loop assumed pre-parsed inputs.
