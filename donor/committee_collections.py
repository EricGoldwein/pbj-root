"""
Placeholder for committee_collections: curated committee sets.

Future use: group committees by user-defined or curated criteria (e.g., Trump-aligned,
industry-specific). NOT exposed in UI yet. Structure only.
"""

# Placeholder: curated committee sets. Do not expose in UI.
# Format: { "slug": { "name": str, "description": str, "committee_ids": [str] } }
COMMITTEE_COLLECTIONS: dict = {}

# Reserved slugs for future curated sets (do not use until wired)
_RESERVED_SLUGS = frozenset(["trump-aligned", "industry-pac", "joint-fundraiser"])


def get_collection(slug: str) -> dict | None:
    """Return a committee collection by slug, or None."""
    return COMMITTEE_COLLECTIONS.get(slug)


def list_collections() -> list:
    """List all committee collections. Currently returns empty."""
    return list(COMMITTEE_COLLECTIONS.values())


def add_collection(slug: str, name: str, description: str, committee_ids: list[str]) -> None:
    """Add a committee collection. For future use only."""
    if slug in _RESERVED_SLUGS:
        raise ValueError(f"Slug '{slug}' is reserved")
    COMMITTEE_COLLECTIONS[slug] = {
        "slug": slug,
        "name": name,
        "description": description,
        "committee_ids": committee_ids,
    }
