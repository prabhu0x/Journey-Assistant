import math
from datetime import datetime
from typing import Dict, List, Any

# Rates per kilometer for different vehicle types
RATES = {
    "Bike": 10.0,
    "Auto": 12.0,
    "Hatchback": 15.0,
    "Sedan": 22.0,
    "SUV": 30.0,
    "Premium Sedan": 40.0,
    "Luxury SUV": 55.0
}


def calculate_haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculates the great-circle distance between two points
    on the earth (specified in decimal degrees) using the Haversine formula.
    """
    R = 6371.0  # Earth radius in kilometers

    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)

    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlon / 2) ** 2)

    c = 2 * math.asin(math.sqrt(a))

    return R * c


def is_peak_hour(pickup_time: datetime) -> bool:
    """
    Determines if the given pickup time falls into peak travel hours
    (Morning 8:00 AM - 11:00 AM, Evening 5:00 PM - 8:00 PM).
    """
    hour = pickup_time.hour
    is_morning_peak = 8 <= hour <= 11
    is_evening_peak = 17 <= hour <= 20
    return is_morning_peak or is_evening_peak


def get_cab_quotes(
        start_location: Dict[str, float],
        end_location: Dict[str, float],
        pickup_time: datetime
) -> List[Dict[str, Any]]:
    """
    Calculates and generates exactly 50 cab quotes across multiple providers
    and vehicle types.
    """
    lat1, lon1 = start_location["lat"], start_location["lon"]
    lat2, lon2 = end_location["lat"], end_location["lon"]

    # Calculate distance using Haversine formula
    distance_km = calculate_haversine_distance(lat1, lon1, lat2, lon2)
    if distance_km <= 0:
        distance_km = 0.5  # Minimum chargeable distance safeguard

    peak_multiplier = 1.25 if is_peak_hour(pickup_time) else 1.0

    cab_schedules = []

    providers = ["Uber", "Ola", "Rapido", "InDrive", "Meru"]
    car_types = ["Bike", "Auto", "Hatchback", "Sedan", "SUV", "Premium Sedan", "Luxury SUV"]

    # Loop to generate precisely 50 options
    for i in range(1, 51):
        provider = providers[i % len(providers)]
        car_type = car_types[i % len(car_types)]

        # Skip bikes for long distances
        if car_type == "Bike" and distance_km > 25:
            car_type = "Hatchback"

        # Price calculation with slight variation per option index
        rate = RATES.get(car_type, 15.0)
        base_price = (distance_km * rate) + (i * 2.5)
        final_price = round(base_price * peak_multiplier, 2)

        # Simulated wait time variation
        wait_time_mins = (i % 8) + 2

        cab_schedules.append({
            "company_name": f"{provider} Prime {i}" if i % 2 == 0 else f"{provider} Go {i}",
            "car_type": car_type,
            "distance_km": round(distance_km, 2),
            "price": final_price,
            "wait_time_minutes": wait_time_mins,
            "pickup_location": f"{start_location.get('name', 'Origin')} Hub",
            "drop_location": f"{end_location.get('name', 'Destination')} Point"
        })

    return cab_schedules


if __name__ == "__main__":
    # Test execution matching your train/bus example structure
    mock_start = {"lat": 13.0827, "lon": 80.2707, "name": "Chennai"}
    mock_end = {"lat": 12.9716, "lon": 77.5946, "name": "Bangalore"}
    sample_time = datetime(2026, 8, 20, 9, 30, 0)

    results = get_cab_quotes(mock_start, mock_end, sample_time)
    print(f"Total cab options generated: {len(results)}")
    print("\nFirst option generated:")
    print(results[0])