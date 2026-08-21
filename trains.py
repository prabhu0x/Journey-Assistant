def get_train_schedules(origin, destination, date):
    train_schedules = []

    for i in range(1, 51):
        # Calculates departure and arrival hours across the day
        dep_hour = (i * 2) % 24
        arr_hour = (dep_hour + 5) % 24

        train_schedules.append({
            "operator": f"IRCTC Express {i}",
            "mode": "train",
            "origin_station": f"{origin} Central",
            "destination_station": f"{destination} Junction",
            "departure_time": f"{date}T{dep_hour:02d}:00:00",
            "arrival_time": f"{date}T{arr_hour:02d}:30:00",
            "fare": 300 + (i * 15),
            "available_seats": (i * 3) % 100 + 1
        })

    return train_schedules


def get_bus_schedules(origin, destination, date):
    bus_schedules = []

    for i in range(1, 51):
        dep_hour = (i * 2 + 1) % 24
        arr_hour = (dep_hour + 6) % 24

        bus_schedules.append({
            "operator": f"redBus Express {i}",
            "mode": "bus",
            "origin_station": f"{origin} Bus Terminal",
            "destination_station": f"{destination} Bus Stand",
            "departure_time": f"{date}T{dep_hour:02d}:15:00",
            "arrival_time": f"{date}T{arr_hour:02d}:45:00",
            "fare": 250 + (i * 10),
            "available_seats": (i * 2) % 40 + 1
        })

    return bus_schedules


def fetch_mainline_routes(origin, destination, date):
    trains = get_train_schedules(origin, destination, date)
    buses = get_bus_schedules(origin, destination, date)
    return trains + buses


if __name__ == "__main__":
    # Test execution
    results = fetch_mainline_routes("Chennai", "Bangalore", "2026-08-20")
    print(f"Total options generated: {len(results)}")
    print("\nFirst option generated:")
    print(results[0])