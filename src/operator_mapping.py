"""
Operator-to-brand mapping for Illinois sports wagering licensees.

Each IGB licensee name maps to:
  - operator_id: stable entity identifier that follows rebrands
  - brand: consumer-facing sportsbook brand name
  - notes: rebrand history or other context

Rebrands collapsed:
  - PointsBet → Fanatics (2023 acquisition): Hawthorne Race Course → Alton Casino (Jan 2026 migration)
  - Barstool → ESPN BET (Nov 2023 rebrand): HC Aurora
  - William Hill → Caesars (2021 acquisition): Midwest Gaming
"""

# Mapping: IGB licensee name → (operator_id, brand, notes)
OPERATOR_MAP = {
    "Fairmount Park, Inc.": {
        "operator_id": "fanduel",
        "brand": "FanDuel",
        "notes": "",
    },
    "Casino Queen, Inc.": {
        "operator_id": "draftkings",
        "brand": "DraftKings",
        "notes": "",
    },
    "Hawthorne Race Course, Inc.": {
        "operator_id": "fanatics",
        "brand": "Fanatics",
        "notes": "PointsBet until 2023 acquisition; online migrated to Alton Casino Jan 2026",
    },
    "Alton Casino, LLC": {
        "operator_id": "fanatics",
        "brand": "Fanatics",
        "notes": "Online skin from Jan 2026 (migrated from Hawthorne); retail-only before that",
    },
    "HC Aurora, LLC": {
        "operator_id": "espn_bet",
        "brand": "ESPN BET",
        "notes": "Barstool Sportsbook until Nov 2023 rebrand; Penn Entertainment",
    },
    "HC Joliet, LLC": {
        "operator_id": "espn_bet",
        "brand": "ESPN BET",
        "notes": "Penn Entertainment; retail only (Hollywood Casino Joliet)",
    },
    "Midwest Gaming & Entertainment, LLC": {
        "operator_id": "caesars",
        "brand": "Caesars",
        "notes": "William Hill until 2021 acquisition; Rivers Casino Des Plaines",
    },
    "Southern Illinois Riverboat/Casino Cruises LLC": {
        "operator_id": "caesars",
        "brand": "Caesars",
        "notes": "Harrah's Metropolis; retail only",
    },
    "Elgin Riverboat Resort": {
        "operator_id": "betrivers",
        "brand": "BetRivers",
        "notes": "Rush Street Interactive; Grand Victoria Casino",
    },
    "Par-A-Dice Gaming Corporation": {
        "operator_id": "betmgm",
        "brand": "BetMGM",
        "notes": "",
    },
    "815 Entertainment": {
        "operator_id": "hard_rock",
        "brand": "Hard Rock Bet",
        "notes": "Entered Aug 2024; Hard Rock Casino Rockford",
    },
    "FHR-Illinois  LLC": {
        "operator_id": "bet365",
        "brand": "bet365",
        "notes": "Full House Resorts; American Place temporary casino (Waukegan)",
    },
    "WALKER'S BLUFF CASINO RESORT, LLC": {
        "operator_id": "walkers_bluff",
        "brand": "Walker's Bluff",
        "notes": "Online from Mar 2025; brand partner unconfirmed from IGB data alone",
    },
    "Northside Crown Gaming LLC": {
        "operator_id": "northside_crown",
        "brand": "Northside Crown",
        "notes": "Retail only; Bally's Chicago temporary casino",
    },
    "The Rock Island Boatworks, LLC": {
        "operator_id": "rock_island",
        "brand": "Rock Island",
        "notes": "Online from Jun 2026; Jumer's Casino (Circa Sports partner)",
    },
    "WIND CREEK IL LLC": {
        "operator_id": "wind_creek",
        "brand": "Wind Creek",
        "notes": "Entered Mar 2026; retail only; Wind Creek Hospitality (Poarch Band)",
    },
}


def get_operator_id(licensee_name):
    """Return operator_id for a licensee name, or the name itself if unmapped."""
    entry = OPERATOR_MAP.get(licensee_name.strip())
    return entry["operator_id"] if entry else licensee_name.strip()


def get_brand(licensee_name):
    """Return consumer-facing brand name."""
    entry = OPERATOR_MAP.get(licensee_name.strip())
    return entry["brand"] if entry else licensee_name.strip()
