"""
FEC contributor name variations for live and batch queries.

Never emits surname-only queries (e.g. "FISCHL") — too broad and conflates unrelated donors.
"""
from __future__ import annotations

import pandas as pd

# Common nicknames → alternate first names paired with the same last name
NAME_VARIATIONS: dict[str, list[str]] = {
    "WILLIAM": ["BILL", "WILL", "WILLY"],
    "ROBERT": ["BOB", "ROB", "BOBBY"],
    "RICHARD": ["DICK", "RICK", "RICH"],
    "JAMES": ["JIM", "JIMMY", "JAMIE"],
    "JOHN": ["JACK", "JOHNNY"],
    "CHARLES": ["CHARLIE", "CHUCK"],
    "MICHAEL": ["MIKE", "MIKEY"],
    "JOSEPH": ["JOE", "JOEY"],
    "THOMAS": ["TOM", "TOMMY"],
    "CHRISTOPHER": ["CHRIS"],
    "DANIEL": ["DAN", "DANNY"],
    "MATTHEW": ["MATT"],
    "ANTHONY": ["TONY"],
    "EDWARD": ["ED", "EDDIE", "TED"],
    "PATRICK": ["PAT"],
    "KENNETH": ["KEN"],
    "STEPHEN": ["STEVE"],
    "ANDREW": ["ANDY"],
    "JOSHUA": ["JOSH"],
    "BENJAMIN": ["BEN"],
    "NICHOLAS": ["NICK"],
    "JONATHAN": ["JON"],
    "SAMUEL": ["SAM"],
    "ALEXANDER": ["ALEX"],
    "CHRISTIAN": ["CHRIS"],
    "RYAN": ["RYAN"],
    "NATHAN": ["NATE"],
    "TYLER": ["TY"],
    "JACOB": ["JAKE"],
}


def normalize_name_for_search(name: object) -> list[str]:
    """
    Build FEC name query variants for an individual or organization string.

    - Full normalized name
    - Nickname + last (when first name is in NAME_VARIATIONS)
    - First + last when middle name/initial present
    - Does not add last-name-only variants
    """
    if pd.isna(name) or not name:
        return []

    name_upper = str(name).upper().strip()
    variations = [name_upper]

    parts = name_upper.split()
    if len(parts) >= 2:
        first = parts[0]
        last = parts[-1]

        if first in NAME_VARIATIONS:
            for nickname in NAME_VARIATIONS[first]:
                variations.append(f"{nickname} {last}")
                if len(parts) > 2:
                    variations.append(f"{nickname} {parts[1]} {last}")

        if len(parts) > 2:
            variations.append(f"{first} {last}")

    return list(set(variations))
