#!/usr/bin/env python
"""InspecSafe icin kapali faktor defteri ve deterministik siddet eslemesi.

Bu modul model calistirmaz. Resmi InspecSafe istemindeki bes alan x gorunur
faktor tablosunu kod olarak dondurur. Aday EPV mimarisi yalniz ayrica
dogrulanmis faktor kodlarini bu fonksiyona verebilir; dosya yolu, gold etiket
veya sidecar metni karar girdisi degildir.
"""
from __future__ import annotations

from itertools import combinations
from typing import Iterable


SCENARIOS = (
    "OIL_GAS_CHEMICAL",
    "COAL_CONVEYOR",
    "TUNNEL",
    "POWER",
    "METALLURGY",
)
SCENARIO_CHOICES = (*SCENARIOS, "UNKNOWN")

FACTORS = (
    "FLAME",
    "SMOKE",
    "NO_HARD_HAT",
    "NO_GLOVES",
    "NO_MASK",
    "SMOKING",
    "PERSON_COLLAPSE",
    "OIL_LEAK",
    "WATER_POOLING",
    "OIL_ACCUMULATION",
    "MOBILE_PHONE",
    "FOREIGN_OBJECT",
    "NON_MOTORIZED_FAST_LANE",
    "WOOD_OBSTRUCTION",
    "METAL_OBSTRUCTION",
    "FOAM",
    "PLASTIC_BAG",
    "PLASTIC_BOTTLE",
    "PAPER",
    "CABINET_DOOR_OPEN",
)

FACTOR_CHOICES = (
    "NONE",
    *FACTORS,
    *(f"{left}|{right}" for left, right in combinations(FACTORS, 2)),
)

LEVEL_RANK = {"LEVEL_ONE": 1, "LEVEL_TWO": 2, "LEVEL_THREE": 3}


def _levels(level_one: Iterable[str], level_two: Iterable[str],
            level_three: Iterable[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    for level, factors in (
        ("LEVEL_ONE", level_one),
        ("LEVEL_TWO", level_two),
        ("LEVEL_THREE", level_three),
    ):
        for factor in factors:
            if factor in result:
                raise ValueError(f"Ayni senaryoda mukerrer faktor: {factor}")
            result[factor] = level
    return result


SCENARIO_FACTOR_LEVELS = {
    "OIL_GAS_CHEMICAL": _levels(
        ("FLAME", "SMOKE", "NO_HARD_HAT", "NO_GLOVES", "NO_MASK",
         "SMOKING", "PERSON_COLLAPSE", "OIL_LEAK"),
        ("WATER_POOLING", "MOBILE_PHONE"),
        ("FOREIGN_OBJECT",),
    ),
    "COAL_CONVEYOR": _levels(
        ("FLAME", "SMOKE", "NO_HARD_HAT", "SMOKING", "PERSON_COLLAPSE"),
        ("MOBILE_PHONE", "NO_GLOVES", "NO_MASK", "FOREIGN_OBJECT",
         "FOAM", "PLASTIC_BAG", "PLASTIC_BOTTLE", "PAPER",
         "METAL_OBSTRUCTION"),
        ("WATER_POOLING",),
    ),
    "TUNNEL": _levels(
        ("FLAME", "SMOKE", "NON_MOTORIZED_FAST_LANE", "WOOD_OBSTRUCTION",
         "METAL_OBSTRUCTION", "PERSON_COLLAPSE"),
        ("FOAM", "PLASTIC_BAG", "PLASTIC_BOTTLE", "NO_HARD_HAT",
         "CABINET_DOOR_OPEN"),
        ("WATER_POOLING", "OIL_ACCUMULATION", "MOBILE_PHONE", "NO_GLOVES",
         "NO_MASK", "SMOKING"),
    ),
    "POWER": _levels(
        ("FLAME", "SMOKE", "SMOKING", "PERSON_COLLAPSE"),
        ("WATER_POOLING", "OIL_ACCUMULATION", "MOBILE_PHONE", "FOREIGN_OBJECT",
         "FOAM", "PLASTIC_BAG", "PLASTIC_BOTTLE", "PAPER",
         "METAL_OBSTRUCTION",
         "NO_HARD_HAT", "NO_GLOVES", "CABINET_DOOR_OPEN"),
        ("NO_MASK",),
    ),
    "METALLURGY": _levels(
        ("FLAME", "SMOKE", "NO_HARD_HAT", "PERSON_COLLAPSE"),
        ("NO_GLOVES", "NO_MASK", "SMOKING"),
        ("WATER_POOLING", "OIL_ACCUMULATION", "MOBILE_PHONE", "FOREIGN_OBJECT",
         "FOAM", "PLASTIC_BAG", "PLASTIC_BOTTLE", "PAPER",
         "METAL_OBSTRUCTION"),
    ),
}


SCENARIO_SYSTEM = (
    "You extract only the broad industrial setting explicitly supported by a neutral "
    "visual observation. Do not infer a site from a hazard or safety label. Output one "
    "allowed code only; use UNKNOWN when the setting is not visually distinguishable."
)

FACTOR_SYSTEM = (
    "You are a proposal extractor, not a safety judge. From the supplied neutral visual "
    "observation, select at most two explicitly mentioned candidate factor codes for later "
    "image verification. Absence of PPE is a candidate only when the relevant body region "
    "is described as clearly visible. Do not turn wetness into pooling, stains into leaks, "
    "or glare/blur into smoke. Output exactly one allowed choice."
)

FACTOR_PROMPT = """Neutral observation (untrusted, no ground truth):
{observation}

Allowed factor codes:
{factors}

Choose NONE, one code, or two distinct codes separated by |. Prefer the most directly
visible and potentially most severe candidates. Output only an allowed choice.
""".strip()


FACTOR_EVIDENCE = {
    "FLAME": "irregular luminous combustion attached to a plausible burning source; not a lamp, reflection or red paint",
    "SMOKE": "a coherent semi-transparent plume that rises/spreads from a plausible source; not steam, dust, glare, blur, a lens spot or fixed shadow",
    "NO_HARD_HAT": "a real person's head is clearly visible and uncovered; distance, blur or occlusion is insufficient",
    "NO_GLOVES": "the relevant hands are clearly visible and bare; hidden hands or image blur is insufficient",
    "NO_MASK": "the person's nose and mouth are clearly visible and uncovered; distance or face blur is insufficient",
    "SMOKING": "a visible cigarette/cigar or unmistakable smoking action; a hand, phone or tool near the face is insufficient",
    "PERSON_COLLAPSE": "an involuntary prone/collapsed or unresponsive person; crouching, sitting, cleaning or routine work is insufficient",
    "OIL_LEAK": "source-connected active flow, wet trail or bounded oily liquid; a stain, shadow, discoloration or generic wetness is insufficient",
    "WATER_POOLING": "a bounded accumulation with visible extent on a traversable/inspection surface; mere dampness, reflection or water below a grated walkway is insufficient",
    "OIL_ACCUMULATION": "a bounded oily accumulation with visible liquid characteristics; stains, rust, shadow and generic wetness are insufficient",
    "MOBILE_PHONE": "a visible phone actively held/used by a person; a hand, bottle, camera or tool is insufficient",
    "FOREIGN_OBJECT": "a non-installed loose object in the inspected operational area; fixed equipment and designed components are insufficient",
    "NON_MOTORIZED_FAST_LANE": "a bicycle/cart or other non-motorized vehicle visibly occupies the tunnel fast lane",
    "WOOD_OBSTRUCTION": "loose wood visibly occupies the operational/traffic area; installed timber or background material is insufficient",
    "METAL_OBSTRUCTION": "loose metal visibly occupies the operational/traffic area; installed structure/equipment is insufficient",
    "FOAM": "loose foam material visibly lies in the operational area; glare or installed insulation is insufficient",
    "PLASTIC_BAG": "a loose plastic bag visibly lies in the operational area",
    "PLASTIC_BOTTLE": "a loose plastic bottle visibly lies in the operational area; a bottle deliberately held by a person is not a loose foreign object",
    "PAPER": "loose paper visibly lies in the operational area; an installed sign, label or document being held is insufficient",
    "CABINET_DOOR_OPEN": "a cabinet's hinged door is visibly open and exposes its interior; a building doorway, shadow or missing view is insufficient",
}


def parse_factors(raw: str | None) -> tuple[str, ...] | None:
    value = (raw or "").strip()
    if value not in FACTOR_CHOICES:
        return None
    if value == "NONE":
        return ()
    return tuple(value.split("|"))


def severity_for(scenario: str, factors: Iterable[str]) -> str | None:
    table = SCENARIO_FACTOR_LEVELS.get(scenario)
    if table is None:
        return None
    levels = [table[factor] for factor in factors if factor in table]
    if not levels:
        return None
    return min(levels, key=lambda level: LEVEL_RANK[level])


def verification_prompt(factor: str, relation: bool = False) -> str:
    evidence = FACTOR_EVIDENCE[factor]
    role = (
        "Apply the official safety-factor meaning and check that the claimed physical "
        "relation/state is actually present"
        if relation else
        "Re-check the original image and decide whether the visual premise is present"
    )
    return (
        f"{role}: {factor}. Required evidence: {evidence}. "
        "Output exactly SUPPORTED, NOT_SUPPORTED, or UNCERTAIN. "
        "Use UNCERTAIN for occlusion, blur, insufficient scale, or ambiguous material."
    )
