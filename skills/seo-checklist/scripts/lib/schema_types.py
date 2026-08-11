"""Shared schema.org type hierarchy used by entity and local-SEO checks."""

from __future__ import annotations


# Snapshot of schema.org's LocalBusiness hierarchy in August 2026. Unknown future
# subtypes remain unknown rather than being guessed from their spelling.
LOCAL_BUSINESS_TYPES = frozenset({
    "LocalBusiness",
    "AnimalShelter", "ArchiveOrganization", "AutomotiveBusiness", "ChildCare",
    "Dentist", "DryCleaningOrLaundry", "EmergencyService", "EmploymentAgency",
    "EntertainmentBusiness", "FinancialService", "FoodEstablishment",
    "GovernmentOffice", "HealthAndBeautyBusiness", "HomeAndConstructionBusiness",
    "InternetCafe", "LegalService", "Library", "LodgingBusiness",
    "MedicalBusiness", "ProfessionalService", "RadioStation", "RealEstateAgent",
    "RecyclingCenter", "SelfStorage", "ShoppingCenter", "SportsActivityLocation",
    "Store", "TelevisionStation", "TouristInformationCenter", "TravelAgency",
    "Bakery", "BarOrPub", "Brewery", "CafeOrCoffeeShop", "Distillery",
    "FastFoodRestaurant", "IceCreamShop", "Restaurant", "Winery",
    "BedAndBreakfast", "Campground", "Hostel", "Hotel", "Motel", "Resort",
    "SkiResort", "BeautySalon", "DaySpa", "HairSalon", "HealthClub",
    "NailSalon", "TattooParlor", "Physician", "Optician", "Pharmacy",
    "VeterinaryCare", "AutoBodyShop", "AutoDealer", "AutoPartsStore",
    "AutoRental", "AutoRepair", "AutoWash", "GasStation", "MotorcycleDealer",
    "MotorcycleRepair", "Electrician", "GeneralContractor", "HVACBusiness",
    "HousePainter", "Locksmith", "MovingCompany", "Plumber", "RoofingContractor",
    "AdultEntertainment", "AmusementPark", "ArtGallery", "Casino", "ComedyClub",
    "MovieTheater", "NightClub", "BowlingAlley", "ExerciseGym", "GolfCourse",
    "PublicSwimmingPool", "SkatingRink", "SportsClub", "StadiumOrArena",
    "TennisComplex", "BikeStore", "BookStore", "ClothingStore", "ComputerStore",
    "ConvenienceStore", "DepartmentStore", "ElectronicsStore", "Florist",
    "FurnitureStore", "GardenStore", "GroceryStore", "HardwareStore", "HobbyShop",
    "HomeGoodsStore", "JewelryStore", "LiquorStore", "MensClothingStore",
    "MobilePhoneStore", "MovieRentalStore", "MusicStore", "OfficeEquipmentStore",
    "OutletStore", "PawnShop", "PetStore", "ShoeStore", "SportingGoodsStore",
    "TireShop", "ToyStore", "WholesaleStore", "AccountingService",
    "AutomatedTeller", "BankOrCreditUnion", "InsuranceAgency", "Notary",
})


def schema_types(value) -> list[str]:
    """Return @type as a list of non-empty strings, preserving source order."""
    values = value if isinstance(value, list) else [value]
    return [item for item in values if isinstance(item, str) and item]


def is_local_business_type(value) -> bool:
    """Return whether any supplied @type is LocalBusiness or a known subtype."""
    return bool(LOCAL_BUSINESS_TYPES.intersection(schema_types(value)))
