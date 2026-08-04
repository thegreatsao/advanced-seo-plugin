#!/usr/bin/env python3
"""Check local SEO signals: NAP, LocalBusiness schema, GBP links, reviews, and maps."""

from __future__ import annotations

import argparse
import re
from typing import Any

from schema_required_props import extract_schema_documents, find_schema_nodes, load_source_html
from seo_common import parse_html, print_json_or_text, issue


PHONE_RE = re.compile(r"(\+?\d[\d\s().-]{7,}\d)")
MAP_PATTERNS = ("google.com/maps", "maps.google.", "bing.com/maps", "openstreetmap.org")
GBP_PATTERNS = ("g.page/", "business.google.com", "search.google.com/local/writereview")


# schema.org's LocalBusiness subtypes. `find_schema_nodes(documents,
# "LocalBusiness")` compares @type as a string, so a site publishing `Restaurant`
# — which *is* a LocalBusiness — was reported as having no local schema at all.
# On a live restaurant site that produced a `high` FAIL on LO-198 and a "No
# LocalBusiness JSON-LD found" issue, both of them fabricated: the mirror image of
# an assertion that always passes, and just as invisible.
#
# The list is the published hierarchy as of August 2026, not a guess at one. It is
# a subset — schema.org keeps adding leaves — so an unrecognised subtype still
# reports as missing. That is the safe direction for a list that can go stale: a
# false "no schema" is visible to whoever reads the report, while silently
# accepting anything with "Business" in its name would not be.
LOCAL_BUSINESS_TYPES = frozenset({
    "LocalBusiness",
    # direct subtypes
    "AnimalShelter", "ArchiveOrganization", "AutomotiveBusiness", "ChildCare",
    "Dentist", "DryCleaningOrLaundry", "EmergencyService", "EmploymentAgency",
    "EntertainmentBusiness", "FinancialService", "FoodEstablishment",
    "GovernmentOffice", "HealthAndBeautyBusiness", "HomeAndConstructionBusiness",
    "InternetCafe", "LegalService", "Library", "LodgingBusiness",
    "MedicalBusiness", "ProfessionalService", "RadioStation", "RealEstateAgent",
    "RecyclingCenter", "SelfStorage", "ShoppingCenter", "SportsActivityLocation",
    "Store", "TelevisionStation", "TouristInformationCenter", "TravelAgency",
    # FoodEstablishment
    "Bakery", "BarOrPub", "Brewery", "CafeOrCoffeeShop", "Distillery",
    "FastFoodRestaurant", "IceCreamShop", "Restaurant", "Winery",
    # LodgingBusiness
    "BedAndBreakfast", "Campground", "Hostel", "Hotel", "Motel", "Resort",
    "SkiResort",
    # HealthAndBeautyBusiness / MedicalBusiness / AutomotiveBusiness
    "BeautySalon", "DaySpa", "HairSalon", "HealthClub", "NailSalon",
    "TattooParlor", "Physician", "Optician", "Pharmacy", "VeterinaryCare",
    "AutoBodyShop", "AutoDealer", "AutoPartsStore", "AutoRental", "AutoRepair",
    "AutoWash", "GasStation", "MotorcycleDealer", "MotorcycleRepair",
    # HomeAndConstructionBusiness
    "Electrician", "GeneralContractor", "HVACBusiness", "HousePainter",
    "Locksmith", "MovingCompany", "Plumber", "RoofingContractor",
    # EntertainmentBusiness / SportsActivityLocation
    "AdultEntertainment", "AmusementPark", "ArtGallery", "Casino",
    "ComedyClub", "MovieTheater", "NightClub", "BowlingAlley", "ExerciseGym",
    "GolfCourse", "PublicSwimmingPool", "SkatingRink", "SportsClub",
    "StadiumOrArena", "TennisComplex",
    # Store
    "BikeStore", "BookStore", "ClothingStore", "ComputerStore",
    "ConvenienceStore", "DepartmentStore", "ElectronicsStore", "Florist",
    "FurnitureStore", "GardenStore", "GroceryStore", "HardwareStore",
    "HobbyShop", "HomeGoodsStore", "JewelryStore", "LiquorStore",
    "MensClothingStore", "MobilePhoneStore", "MovieRentalStore", "MusicStore",
    "OfficeEquipmentStore", "OutletStore", "PawnShop", "PetStore", "ShoeStore",
    "SportingGoodsStore", "TireShop", "ToyStore", "WholesaleStore",
    # FinancialService / other leaves
    "AccountingService", "AutomatedTeller", "BankOrCreditUnion",
    "InsuranceAgency", "Notary", "TouristAttraction",
})


def find_local_business_nodes(documents: list) -> list:
    """Every JSON-LD node whose @type is a LocalBusiness or one of its subtypes."""
    return [row for row in find_schema_nodes(documents)
            if LOCAL_BUSINESS_TYPES.intersection(row.get("types") or [])]


def check_local_seo(source: str, timeout: int = 15) -> dict[str, Any]:
    html, final_url, fetch = load_source_html(source, timeout=timeout)
    parsed = parse_html(html, final_url or source) if html else {}
    documents, _ = extract_schema_documents(source, timeout=timeout)
    local_nodes = find_local_business_nodes(documents)
    body_text = parsed.get("body_text", "")
    links = parsed.get("links", [])
    phones = sorted(set(match.group(1).strip() for match in PHONE_RE.finditer(body_text)))
    issues = []
    if not local_nodes:
        issues.append(issue("warning", "No LocalBusiness JSON-LD found (nor any of "
                            "its subtypes)", final_url or source))
    for row in local_nodes:
        node = row["node"]
        for prop in ("name", "address", "telephone"):
            if not node.get(prop):
                issues.append(issue("error", f"LocalBusiness is missing {prop}", evidence=row["path"]))
        if not node.get("areaServed") and not node.get("serviceArea"):
            issues.append(issue("info", "LocalBusiness is missing service area signal", evidence=row["path"]))
        if node.get("telephone") and phones and str(node["telephone"]).replace(" ", "") not in "".join(phones).replace(" ", ""):
            issues.append(issue("warning", "Schema telephone does not visibly match page phone text", evidence=row["path"]))
    map_embeds = html.count("google.com/maps") + html.count("maps.google.") + html.count("openstreetmap.org") if html else 0
    if not map_embeds and not any(any(pattern in link["href"] for pattern in MAP_PATTERNS) for link in links):
        issues.append(issue("info", "No map embed or map link found", final_url or source))
    if not any(any(pattern in link["href"] for pattern in GBP_PATTERNS) for link in links):
        issues.append(issue("info", "No Google Business Profile/review link found", final_url or source))
    if "review" not in body_text.lower() and not any(row["node"].get("aggregateRating") for row in local_nodes):
        issues.append(issue("info", "No visible reviews or aggregateRating signal found", final_url or source))
    return {
        "source": source,
        "final_url": final_url or source,
        "status": fetch.get("status"),
        # A page nobody could read has no LocalBusiness markup and no phone number,
        # and reporting that as a finding is how LO-198 and LO-200 — both `high` —
        # described a host that refused every connection as a business with no local
        # signals.
        "fetch_error": (fetch.get("error")
                        or (None if html else "the page could not be read")),
        "local_business_nodes": len(local_nodes),
        "phones_detected": phones,
        "map_embeds": map_embeds,
        "issues": issues,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Check local SEO signals")
    parser.add_argument("source", help="URL or HTML file")
    parser.add_argument("--timeout", type=int, default=15)
    parser.add_argument("--json", "-j", action="store_true", help="Output JSON")
    args = parser.parse_args()
    result = check_local_seo(args.source, timeout=args.timeout)
    lines = [
        f"Local SEO check for {args.source}",
        f"LocalBusiness nodes: {result['local_business_nodes']}  Phones: {len(result['phones_detected'])}  Issues: {len(result['issues'])}",
    ] + [f"[{item['severity']}] {item['message']} {item.get('evidence') or ''}" for item in result["issues"][:30]]
    print_json_or_text(result, args.json, lines)


if __name__ == "__main__":
    main()
