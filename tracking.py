"""
Member 4 - Real-Time Tracking Lead
Smart Passenger Journey Assistant

This module connects the existing mock train/bus schedules and cab quotes
with Member 4's responsibilities:
1. Simulate live delays / traffic slowdowns.
2. Detect whether a delay threatens a downstream connection.
3. Recommend a revised cab pickup time or an alternate connection.
4. Return simple passenger-friendly status messages.

NOTE:
The train/bus and cab modules supplied for this activity generate MOCK data.
This file therefore simulates real-time updates rather than calling a live API.
"""

from datetime import datetime, timedelta
from typing import Any, Dict, List

from trains import fetch_mainline_routes
from cabs import get_cab_quotes


def simulate_delay(
    schedule: Dict[str, Any],
    delay_minutes: int,
    reason: str = "Operational delay",
) -> Dict[str, Any]:
    """Return a copy of a train/bus schedule with a simulated live delay."""
    if delay_minutes < 0:
        raise ValueError("delay_minutes cannot be negative")

    updated = schedule.copy()

    departure = datetime.fromisoformat(updated["departure_time"])
    arrival = datetime.fromisoformat(updated["arrival_time"])

    updated["scheduled_departure_time"] = updated["departure_time"]
    updated["scheduled_arrival_time"] = updated["arrival_time"]
    updated["departure_time"] = (
        departure + timedelta(minutes=delay_minutes)
    ).isoformat()
    updated["arrival_time"] = (
        arrival + timedelta(minutes=delay_minutes)
    ).isoformat()

    updated["delay_minutes"] = delay_minutes
    updated["delay_reason"] = reason
    updated["status"] = "Delayed" if delay_minutes else "On time"

    return updated


def calculate_connection_risk(
    delayed_arrival: datetime,
    cab_pickup: datetime,
    minimum_buffer_minutes: int = 15,
) -> Dict[str, Any]:
   
    available_buffer = int((cab_pickup - delayed_arrival).total_seconds() / 60)

    at_risk = available_buffer < minimum_buffer_minutes

    return {
        "available_buffer_minutes": available_buffer,
        "minimum_buffer_minutes": minimum_buffer_minutes,
        "connection_at_risk": at_risk,
    }


def recommend_cab_reschedule(
    delayed_arrival: datetime,
    cab_quotes: List[Dict[str, Any]],
    minimum_buffer_minutes: int = 15,
) -> Dict[str, Any]:
    """Select the first cab quote whose wait time provides a safe buffer."""
    target_pickup = delayed_arrival + timedelta(minutes=minimum_buffer_minutes)

    suitable = []
    for quote in cab_quotes:
        wait = int(quote.get("wait_time_minutes", 0))
        estimated_pickup = target_pickup + timedelta(minutes=wait)
        item = {
            **quote,
            "recommended_pickup_time": estimated_pickup.isoformat(),
            "buffer_after_arrival_minutes": int(
                (estimated_pickup - delayed_arrival).total_seconds() / 60
            ),
        }
        suitable.append(item)

    if not suitable:
        return {
            "reschedule_required": True,
            "recommended_cab": None,
            "reason": "No cab quotes are available.",
        }

    # Prefer the earliest estimated pickup; break ties using lower price.
    best = min(
        suitable,
        key=lambda x: (
            x["recommended_pickup_time"],
            x.get("price", float("inf")),
        ),
    )

    return {
        "reschedule_required": True,
        "recommended_cab": best,
        "reason": "Original connection is at risk; a later pickup is recommended.",
    }


def build_status_message(
    delayed_schedule: Dict[str, Any],
    connection_risk: Dict[str, Any],
    reschedule_result: Dict[str, Any],
) -> str:
    """Create the simple status message required by Member 4's activity."""
    mode = delayed_schedule.get("mode", "transport").title()
    delay = delayed_schedule.get("delay_minutes", 0)

    if delay == 0:
        return f"{mode} is running on time - connection remains unchanged."

    if connection_risk["connection_at_risk"]:
        cab = reschedule_result.get("recommended_cab")
        if cab:
            return (
                f"{mode} running {delay} mins late - connection at risk. "
                f"Cab pickup recommended for {cab['recommended_pickup_time']}."
            )
        return (
            f"{mode} running {delay} mins late - connection at risk. "
            "No replacement cab quote is available."
        )

    return (
        f"{mode} running {delay} mins late - current connection "
        "is still feasible."
    )


def monitor_journey(
    origin: str,
    destination: str,
    travel_date: str,
    delayed_option_index: int = 0,
    delay_minutes: int = 30,
    cab_start: Dict[str, float] | None = None,
    cab_end: Dict[str, float] | None = None,
    cab_pickup_time: datetime | None = None,
) -> Dict[str, Any]:
    """
    End-to-end Member 4 demo.

    It obtains the existing mock mainline routes, applies a simulated live
    delay to one option, checks the connection, and proposes a cab update.
    """
    routes = fetch_mainline_routes(origin, destination, travel_date)

    if not routes:
        raise ValueError("No mainline routes are available.")

    if not 0 <= delayed_option_index < len(routes):
        raise IndexError("delayed_option_index is outside the available routes.")

    delayed = simulate_delay(
        routes[delayed_option_index],
        delay_minutes,
        reason="Simulated live delay",
    )

    delayed_arrival = datetime.fromisoformat(delayed["arrival_time"])

    # If no cab input is supplied, create the same style of mock locations
    # used by cabs.py and use the original arrival as the intended pickup.
    if cab_start is None:
        cab_start = {"lat": 13.0827, "lon": 80.2707, "name": destination}
    if cab_end is None:
        cab_end = {"lat": 12.9716, "lon": 77.5946, "name": "Final Destination"}
    if cab_pickup_time is None:
        cab_pickup_time = datetime.fromisoformat(
            delayed["arrival_time"]
        ) - timedelta(minutes=10)

    cab_quotes = get_cab_quotes(cab_start, cab_end, cab_pickup_time)

    risk = calculate_connection_risk(
        delayed_arrival,
        cab_pickup_time,
    )

    if risk["connection_at_risk"]:
        reschedule = recommend_cab_reschedule(
            delayed_arrival,
            cab_quotes,
        )
    else:
        reschedule = {
            "reschedule_required": False,
            "recommended_cab": None,
            "reason": "Connection has sufficient buffer.",
        }

    status = build_status_message(delayed, risk, reschedule)

    return {
        "original_option": routes[delayed_option_index],
        "updated_live_option": delayed,
        "connection_check": risk,
        "cab_action": reschedule,
        "status_message": status,
    }


if __name__ == "__main__":
    demo = monitor_journey(
        "Chennai",
        "Bangalore",
        "2026-08-20",
        delayed_option_index=0,
        delay_minutes=30,
        cab_pickup_time=datetime(2026, 8, 20, 5, 40, 0),
    )

    print("=== MEMBER 4 REAL-TIME TRACKING DEMO ===")
    print("Status:", demo["status_message"])
    print("Connection check:", demo["connection_check"])
    print("Cab action:", demo["cab_action"])
