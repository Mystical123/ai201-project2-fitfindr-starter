"""
tests/test_tools.py

Isolated tests for each FitFindr tool. Run with: pytest tests/
"""

from tools import search_listings, suggest_outfit, create_fit_card
from utils.data_loader import get_example_wardrobe, get_empty_wardrobe


# ── search_listings ────────────────────────────────────────────────────────────

def test_search_returns_results():
    results = search_listings("vintage graphic tee", size=None, max_price=50)
    assert isinstance(results, list)
    assert len(results) > 0

def test_search_empty_results():
    results = search_listings("designer ballgown", size="XXS", max_price=5)
    assert results == []

def test_search_price_filter():
    results = search_listings("jacket", size=None, max_price=10)
    assert all(item["price"] <= 10 for item in results)

def test_search_size_filter():
    results = search_listings("jeans", size="W99", max_price=None)
    assert results == []

def test_search_returns_full_listing_fields():
    results = search_listings("vintage", size=None, max_price=100)
    if results:
        item = results[0]
        for field in ["id", "title", "description", "category", "style_tags",
                      "size", "condition", "price", "colors", "platform"]:
            assert field in item

def test_search_sorted_by_relevance():
    # "graphic tee" should rank graphic tee listings above unrelated items
    results = search_listings("graphic tee", size=None, max_price=100)
    assert len(results) > 0
    titles = [r["title"].lower() for r in results]
    # first result should contain "tee" or "graphic"
    assert any(kw in titles[0] for kw in ["tee", "graphic", "shirt"])


# ── suggest_outfit ─────────────────────────────────────────────────────────────

SAMPLE_ITEM = {
    "id": "lst_006",
    "title": "Graphic Tee — 2003 Tour Bootleg Style",
    "description": "Vintage-style bootleg tee with faded graphic.",
    "category": "tops",
    "style_tags": ["graphic tee", "vintage", "grunge", "streetwear"],
    "size": "L",
    "condition": "good",
    "price": 24.0,
    "colors": ["black"],
    "brand": None,
    "platform": "depop",
}

def test_suggest_outfit_with_wardrobe():
    result = suggest_outfit(SAMPLE_ITEM, get_example_wardrobe())
    assert isinstance(result, str)
    assert len(result) > 20

def test_suggest_outfit_empty_wardrobe():
    result = suggest_outfit(SAMPLE_ITEM, get_empty_wardrobe())
    assert isinstance(result, str)
    assert len(result) > 20  # should return general advice, not crash or empty string

def test_suggest_outfit_does_not_raise():
    try:
        suggest_outfit(SAMPLE_ITEM, get_empty_wardrobe())
    except Exception as e:
        assert False, f"suggest_outfit raised an exception: {e}"


# ── create_fit_card ────────────────────────────────────────────────────────────

SAMPLE_OUTFIT = (
    "Pair with your baggy dark-wash jeans and chunky white sneakers for a "
    "laid-back streetwear look. Tuck the front slightly for shape."
)

def test_create_fit_card_returns_string():
    result = create_fit_card(SAMPLE_OUTFIT, SAMPLE_ITEM)
    assert isinstance(result, str)
    assert len(result) > 20

def test_create_fit_card_empty_outfit():
    result = create_fit_card("", SAMPLE_ITEM)
    assert "Can't create a fit card" in result

def test_create_fit_card_whitespace_outfit():
    result = create_fit_card("   ", SAMPLE_ITEM)
    assert "Can't create a fit card" in result

def test_create_fit_card_does_not_raise():
    try:
        create_fit_card(SAMPLE_OUTFIT, SAMPLE_ITEM)
    except Exception as e:
        assert False, f"create_fit_card raised an exception: {e}"
