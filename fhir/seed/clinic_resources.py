"""Generates the two fictional 'Gulf Horizon Clinics' Organizations, 20
Practitioners split between them, and Schedule/Slot resources for 60 days
of bookable appointments — none of this comes from Synthea, which has no
notion of a Dubai clinic network; it's authored for this project.
"""

import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from arabic_names import pick_name
from idhash import bucket

CLINICS = [
    {
        "id": "org-downtown",
        "name": "Gulf Horizon Clinics – Downtown Dubai",
        "address": {"city": "Dubai", "state": "Dubai", "country": "AE", "line": ["Sheikh Zayed Road"]},
    },
    {
        "id": "org-marina",
        "name": "Gulf Horizon Clinics – Marina",
        "address": {"city": "Dubai", "state": "Dubai", "country": "AE", "line": ["Marina Walk"]},
    },
]

SPECIALTIES = [
    ("394814009", "General practice"),
    ("419772000", "Family practice"),
    ("394579002", "Cardiology"),
    ("394537008", "Pediatrics"),
    ("408443003", "Physiotherapy"),
    ("408475000", "Diabetic medicine"),
    ("408476004", "Obstetrics and gynecology"),
    ("394801008", "Orthopaedics"),
    ("394582007", "Dermatology"),
    ("394591006", "ENT"),
]

WORK_HOURS = [9, 10, 11, 12, 13, 14, 15, 16]  # 1-hour slots, 9:00-17:00
SLOT_MINUTES = 60


def _organization(clinic: dict) -> dict:
    return {
        "resourceType": "Organization",
        "id": clinic["id"],
        "active": True,
        "name": clinic["name"],
        "type": [{"coding": [{"system": "http://terminology.hl7.org/CodeSystem/organization-type", "code": "prov"}]}],
        "address": [clinic["address"]],
    }


def build_practitioners(n: int = 20) -> list[dict]:
    practitioners = []
    for i in range(n):
        gender = "male" if i % 2 == 0 else "female"
        given, family = pick_name(i * 7919 + 13, gender)  # spread across the name lists
        practitioners.append(
            {
                "resourceType": "Practitioner",
                "id": f"pract-{i:02d}",
                "active": True,
                "name": [{"use": "official", "given": [f"Dr. {given}"], "family": family}],
                "gender": gender,
            }
        )
    return practitioners


def build_practitioner_roles(practitioners: list[dict]) -> list[dict]:
    roles = []
    for i, pract in enumerate(practitioners):
        clinic = CLINICS[i % len(CLINICS)]
        code, display = SPECIALTIES[i % len(SPECIALTIES)]
        roles.append(
            {
                "resourceType": "PractitionerRole",
                "id": f"role-{pract['id']}",
                "active": True,
                "practitioner": {"reference": f"Practitioner/{pract['id']}"},
                "organization": {"reference": f"Organization/{clinic['id']}"},
                "specialty": [
                    {"coding": [{"system": "http://snomed.info/sct", "code": code, "display": display}]}
                ],
            }
        )
    return roles


def build_schedules(practitioners: list[dict], start: datetime, days: int) -> list[dict]:
    schedules = []
    for i, pract in enumerate(practitioners):
        clinic = CLINICS[i % len(CLINICS)]
        schedules.append(
            {
                "resourceType": "Schedule",
                "id": f"sched-{pract['id']}",
                "active": True,
                # Schedule.actor is typed Patient|Practitioner|PractitionerRole|
                # RelatedPerson|Device|HealthcareService|Location -- Organization
                # isn't a valid target, so the clinic is only reachable via
                # PractitionerRole.organization, not from Schedule directly.
                "actor": [{"reference": f"Practitioner/{pract['id']}"}],
                "comment": f"Clinic: {clinic['name']}",
                "planningHorizon": {
                    "start": start.isoformat(),
                    "end": (start + timedelta(days=days)).isoformat(),
                },
            }
        )
    return schedules


def build_slots(practitioners: list[dict], start: datetime, days: int, booked_fraction: float = 0.15) -> list[dict]:
    """One Slot per hour, 9:00-17:00, weekdays only, per practitioner's Schedule.

    A stable fraction of slots are pre-marked "busy" (already booked) so the
    dashboard/booking flow has a realistic mix of free and taken times.
    """
    slots = []
    for pract in practitioners:
        schedule_id = f"sched-{pract['id']}"
        for day_offset in range(days):
            day = start + timedelta(days=day_offset)
            if day.weekday() >= 5:  # Sat/Sun
                continue
            for hour in WORK_HOURS:
                slot_start = day.replace(hour=hour, minute=0, second=0, microsecond=0)
                slot_end = slot_start + timedelta(minutes=SLOT_MINUTES)
                slot_id = f"slot-{pract['id']}-{slot_start.strftime('%Y%m%d%H')}"
                is_busy = bucket(slot_id, 1000) < int(booked_fraction * 1000)
                slots.append(
                    {
                        "resourceType": "Slot",
                        "id": slot_id,
                        "schedule": {"reference": f"Schedule/{schedule_id}"},
                        "status": "busy" if is_busy else "free",
                        "start": slot_start.isoformat(),
                        "end": slot_end.isoformat(),
                    }
                )
    return slots


def build_all(days: int = 60, start: datetime | None = None, n_practitioners: int = 20) -> list[dict]:
    start = start or datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    organizations = [_organization(c) for c in CLINICS]
    practitioners = build_practitioners(n_practitioners)
    roles = build_practitioner_roles(practitioners)
    schedules = build_schedules(practitioners, start, days)
    slots = build_slots(practitioners, start, days)
    return [*organizations, *practitioners, *roles, *schedules, *slots]


if __name__ == "__main__":
    resources = build_all()
    print(f"Built {len(resources)} clinic resources (organizations, practitioners, roles, schedules, slots).")
