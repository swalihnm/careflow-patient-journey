"""Small, hand-curated list of common Arabic given/family names for bilingual enrichment.

Not sourced from a names dataset — authored for this project to give the synthetic
population plausible Gulf-style Arabic names alongside Synthea's US-generated ones.
Deliberately small; good enough for a portfolio demo, not a claim of demographic
accuracy. Documented honestly in the README.
"""

MALE_GIVEN = [
    "Ahmed", "Mohammed", "Khalid", "Omar", "Youssef", "Hassan", "Ali", "Saeed",
    "Rashid", "Tariq", "Faisal", "Abdullah", "Mansour", "Salem", "Hamdan",
    "Sultan", "Nasser", "Zayed", "Waleed", "Marwan",
]

FEMALE_GIVEN = [
    "Fatima", "Aisha", "Mariam", "Layla", "Noura", "Hessa", "Shaikha", "Amal",
    "Reem", "Salama", "Alia", "Maitha", "Moza", "Hanan", "Jawaher", "Latifa",
    "Sara", "Hind", "Dana", "Wadha",
]

FAMILY = [
    "Al Maktoum", "Al Suwaidi", "Al Marri", "Al Shamsi", "Al Falasi", "Al Ketbi",
    "Al Mansoori", "Al Nuaimi", "Al Zaabi", "Al Hashimi", "Al Balushi",
    "Al Qassimi", "Al Mazrouei", "Al Ali", "Al Hosani", "Al Dhaheri",
]


def pick_name(seed_int: int, gender: str) -> tuple[str, str]:
    """Deterministically pick (given, family) from `seed_int` so re-runs are stable."""
    given_list = MALE_GIVEN if gender == "male" else FEMALE_GIVEN
    given = given_list[seed_int % len(given_list)]
    family = FAMILY[(seed_int // len(given_list)) % len(FAMILY)]
    return given, family
