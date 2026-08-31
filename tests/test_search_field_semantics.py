"""Search field semantic attributes for iOS Safari AutoFill suppression.

Verifies that every user-facing search/discovery input carries the HTML
attributes needed to prevent irrelevant iOS Safari AutoFill accessory bar
suggestions (passwords, payment cards, location). The required attributes
suppress AutoFill heuristics without altering functionality.

Target semantics per category:
- Primary search / autocomplete / combobox inputs:
    type="search" autocomplete="off" autocapitalize="none"
    autocorrect="off" spellcheck="false" inputmode="search"
    enterkeyhint="search"
- Table filter / simple search inputs:
    type="search" autocomplete="off" autocapitalize="none"
    autocorrect="off" spellcheck="false"
"""

import pathlib
import re

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# Target inventory: (file_rel, input_id, category)
# category: "primary" | "filter"
# primary = search / autocomplete / combobox with JS → full semantics
# filter  = table filter / simple search → type + off attrs (no inputmode/enterkeyhint)
# ---------------------------------------------------------------------------
TARGETS = [
    ("index.html", "homeSearchInput", "primary"),
    ("public-search.js", "pbj-public-search-input", "primary"),
    ("pbj-site-universal.js", "pbj-public-search-input", "primary"),
    ("app.py", "pbj-page-header-switcher-input-entity", "primary"),
    ("app.py", "pbj-page-header-switcher-input-state", "primary"),
    ("app.py", "entityFacilitiesFilter", "filter"),
    ("pbj-ai-support.html", "ai-facility-search", "primary"),
    ("insights_posts/_rankings_table_q1_2026.fragment.html", "irt-filter", "filter"),
    ("insights-ny-minimum-staffing.html", "fac-filter-search", "filter"),
    ("templates/chow_body.html", "chowSearch", "filter"),
    ("ownership/state_owner_index_html.py", "ownersHubSearchInput", "primary"),
    ("ownership/owner_profile_html.py", "ownerFacilitiesFilter", "filter"),
    ("ownership/owner_profile_html.py", "ownerFacilitiesFilterMobile", "filter"),
    ("donor/templates/owner_donor_dashboard.html", "searchInput", "filter"),
    ("donor/templates/owner_donor_dashboard.html", "recipientFilter", "filter"),
    ("donor/templates/owner_donor_dashboard_test.html", "searchInput", "filter"),
    ("donor/templates/owner_donor_dashboard_test.html", "recipientFilter", "filter"),
]


def _find_input_html(file_path: pathlib.Path, input_id: str) -> str | None:
    """Extract the raw HTML of the <input> tag carrying the given id.

    Handles both literal HTML ids and Python f-string / .format() templates
    where the id may contain ``{mode}`` or similar placeholders.
    """
    text = file_path.read_text(encoding="utf-8", errors="replace")

    # For f-strings / .format() the id in source is e.g.
    #   id="pbj-page-header-switcher-input-{mode}"
    # We need to match the literal source, not the rendered output.
    # Strategy: try literal match first; if not found, try with a
    # generic placeholder pattern for the suffix after the known prefix.
    pattern = re.compile(
        rf'id\s*=\s*["\']'
        + re.escape(input_id)
        + rf'["\']'
    )
    m = pattern.search(text)

    if not m:
        # Try f-string / format placeholder variant: strip the last
        # segment (after the final '-') and match id="<prefix>-{...}"
        dash = input_id.rfind("-")
        if dash > 0:
            prefix = input_id[: dash + 1]
            pattern2 = re.compile(
                rf'id\s*=\s*["\']'
                + re.escape(prefix)
                + r'\{[^}]*\}["\']'
            )
            m = pattern2.search(text)

    if not m:
        return None

    # Find the opening <input before the id attribute
    before = text[: m.start()]
    lt_pos = before.rfind("<input")
    if lt_pos == -1:
        return None

    # Find the closing of the tag: the next '>' after lt_pos
    gt_pos = text.find(">", lt_pos)
    if gt_pos == -1:
        return None

    return text[lt_pos : gt_pos + 1]


def _parse_attrs(tag: str) -> dict[str, str | None]:
    """Return a dict of attribute-name -> value (or None for boolean attrs)."""
    attrs: dict[str, str | None] = {}
    for m in re.finditer(r'(\w[\w-]*)(?:\s*=\s*"([^"]*)")?', tag):
        name = m.group(1).lower()
        value = m.group(2)
        attrs[name] = value
    return attrs


# ---------------------------------------------------------------------------
# Parametrized tests
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    ("file_rel", "input_id", "category"),
    TARGETS,
    ids=[f"{f}::{i}" for f, i, _ in TARGETS],
)
def test_search_input_exists(file_rel: str, input_id: str, category: str) -> None:
    """The target input exists in the source file."""
    path = ROOT / file_rel
    assert path.exists(), f"File not found: {file_rel}"
    tag = _find_input_html(path, input_id)
    assert tag is not None, (
        f"Input with id={input_id!r} not found in {file_rel}"
    )


@pytest.mark.parametrize(
    ("file_rel", "input_id", "category"),
    TARGETS,
    ids=[f"{f}::{i}" for f, i, _ in TARGETS],
)
def test_search_input_type_search(file_rel: str, input_id: str, category: str) -> None:
    """type='search' prevents iOS Safari text-Input accessory bar."""
    tag = _find_input_html(ROOT / file_rel, input_id)
    assert tag is not None
    attrs = _parse_attrs(tag)
    assert attrs.get("type") == "search", (
        f"{file_rel}::{input_id}: expected type='search', got type={attrs.get('type')!r}"
    )


@pytest.mark.parametrize(
    ("file_rel", "input_id", "category"),
    TARGETS,
    ids=[f"{f}::{i}" for f, i, _ in TARGETS],
)
def test_search_input_autocomplete_off(file_rel: str, input_id: str, category: str) -> None:
    """autocomplete='off' prevents AutoFill population."""
    tag = _find_input_html(ROOT / file_rel, input_id)
    assert tag is not None
    attrs = _parse_attrs(tag)
    assert attrs.get("autocomplete") == "off", (
        f"{file_rel}::{input_id}: expected autocomplete='off', "
        f"got {attrs.get('autocomplete')!r}"
    )


@pytest.mark.parametrize(
    ("file_rel", "input_id", "category"),
    TARGETS,
    ids=[f"{f}::{i}" for f, i, _ in TARGETS],
)
def test_search_input_autocapitalize_none(file_rel: str, input_id: str, category: str) -> None:
    """autocapitalize='none' prevents auto-capitalization of search input."""
    tag = _find_input_html(ROOT / file_rel, input_id)
    assert tag is not None
    attrs = _parse_attrs(tag)
    assert attrs.get("autocapitalize") == "none", (
        f"{file_rel}::{input_id}: expected autocapitalize='none', "
        f"got {attrs.get('autocapitalize')!r}"
    )


@pytest.mark.parametrize(
    ("file_rel", "input_id", "category"),
    TARGETS,
    ids=[f"{f}::{i}" for f, i, _ in TARGETS],
)
def test_search_input_autocorrect_off(file_rel: str, input_id: str, category: str) -> None:
    """autocorrect='off' prevents spell-correction of search queries."""
    tag = _find_input_html(ROOT / file_rel, input_id)
    assert tag is not None
    attrs = _parse_attrs(tag)
    assert attrs.get("autocorrect") == "off", (
        f"{file_rel}::{input_id}: expected autocorrect='off', "
        f"got {attrs.get('autocorrect')!r}"
    )


@pytest.mark.parametrize(
    ("file_rel", "input_id", "category"),
    TARGETS,
    ids=[f"{f}::{i}" for f, i, _ in TARGETS],
)
def test_search_input_spellcheck_false(file_rel: str, input_id: str, category: str) -> None:
    """spellcheck='false' prevents browser spell-check UI on search text."""
    tag = _find_input_html(ROOT / file_rel, input_id)
    assert tag is not None
    attrs = _parse_attrs(tag)
    assert attrs.get("spellcheck") == "false", (
        f"{file_rel}::{input_id}: expected spellcheck='false', "
        f"got {attrs.get('spellcheck')!r}"
    )


# --- Primary-only attributes ---

PRIMARY_TARGETS = [(f, i, c) for f, i, c in TARGETS if c == "primary"]


@pytest.mark.parametrize(
    ("file_rel", "input_id", "category"),
    PRIMARY_TARGETS,
    ids=[f"{f}::{i}" for f, i, _ in PRIMARY_TARGETS],
)
def test_search_input_inputmode_search(file_rel: str, input_id: str, category: str) -> None:
    """inputmode='search' shows the search keyboard on mobile."""
    tag = _find_input_html(ROOT / file_rel, input_id)
    assert tag is not None
    attrs = _parse_attrs(tag)
    assert attrs.get("inputmode") == "search", (
        f"{file_rel}::{input_id}: expected inputmode='search', "
        f"got {attrs.get('inputmode')!r}"
    )


@pytest.mark.parametrize(
    ("file_rel", "input_id", "category"),
    PRIMARY_TARGETS,
    ids=[f"{f}::{i}" for f, i, _ in PRIMARY_TARGETS],
)
def test_search_input_enterkeyhint_search(file_rel: str, input_id: str, category: str) -> None:
    """enterkeyhint='search' shows 'Search' on the mobile keyboard return key."""
    tag = _find_input_html(ROOT / file_rel, input_id)
    assert tag is not None
    attrs = _parse_attrs(tag)
    assert attrs.get("enterkeyhint") == "search", (
        f"{file_rel}::{input_id}: expected enterkeyhint='search', "
        f"got {attrs.get('enterkeyhint')!r}"
    )
