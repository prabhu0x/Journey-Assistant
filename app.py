import math
import json
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

import uvicorn
from fastapi import FastAPI, Query, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware

# ==============================================================================
# CITY COORDINATES LOOKUP TABLE
# ==============================================================================
CITY_COORDS = {
    "chennai": {"lat": 13.0827, "lon": 80.2707},
    "bangalore": {"lat": 12.9716, "lon": 77.5946},
    "bengaluru": {"lat": 12.9716, "lon": 77.5946},
    "mumbai": {"lat": 19.0760, "lon": 72.8777},
    "delhi": {"lat": 28.6139, "lon": 77.2090},
    "hyderabad": {"lat": 17.3850, "lon": 78.4867},
    "kolkata": {"lat": 22.5726, "lon": 88.3639},
    "pune": {"lat": 18.5204, "lon": 73.8567},
    "ahmedabad": {"lat": 23.0225, "lon": 72.5714},
    "kochi": {"lat": 9.9312, "lon": 76.2673}
}

RATES = {
    "Bike": 10.0,
    "Auto": 12.0,
    "Hatchback": 15.0,
    "Sedan": 22.0,
    "SUV": 30.0,
    "Premium Sedan": 40.0,
    "Luxury SUV": 55.0
}

# ==============================================================================
# 1. MEMBER 1 & 2 DATA LOGIC
# ==============================================================================

def calculate_haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlon / 2) ** 2)
    c = 2 * math.asin(math.sqrt(a))
    return R * c

def is_peak_hour(pickup_time: datetime) -> bool:
    hour = pickup_time.hour
    return (8 <= hour <= 11) or (17 <= hour <= 20)

def get_cab_quotes(start_location: Dict[str, float], end_location: Dict[str, float], pickup_time: datetime) -> List[Dict[str, Any]]:
    lat1, lon1 = start_location["lat"], start_location["lon"]
    lat2, lon2 = end_location["lat"], end_location["lon"]
    distance_km = calculate_haversine_distance(lat1, lon1, lat2, lon2)
    if distance_km <= 0:
        distance_km = 0.5

    peak_multiplier = 1.25 if is_peak_hour(pickup_time) else 1.0
    cab_schedules = []
    providers = ["Uber", "Ola", "Rapido", "InDrive", "Meru"]
    car_types = ["Bike", "Auto", "Hatchback", "Sedan", "SUV", "Premium Sedan", "Luxury SUV"]

    for i in range(1, 51):
        provider = providers[i % len(providers)]
        car_type = car_types[i % len(car_types)]

        if car_type == "Bike" and distance_km > 25:
            car_type = "Hatchback"

        rate = RATES.get(car_type, 15.0)
        base_price = (distance_km * rate) + (i * 2.5)
        final_price = round(base_price * peak_multiplier, 2)
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

def get_train_schedules(origin: str, destination: str, date: str, distance_km: float = 350.0) -> List[Dict[str, Any]]:
    train_schedules = []
    duration_hours = max(2, int(distance_km / 75.0))
    base_rate = max(150, int(distance_km * 0.8))

    for i in range(1, 51):
        dep_hour = (i * 2) % 24
        arr_hour = (dep_hour + duration_hours) % 24
        train_schedules.append({
            "operator": f"IRCTC Express {i}",
            "mode": "train",
            "origin_station": f"{origin} Central",
            "destination_station": f"{destination} Junction",
            "departure_time": f"{date}T{dep_hour:02d}:00:00",
            "arrival_time": f"{date}T{arr_hour:02d}:30:00",
            "fare": base_rate + (i * 15),
            "available_seats": (i * 3) % 100 + 1
        })
    return train_schedules

def get_bus_schedules(origin: str, destination: str, date: str, distance_km: float = 350.0) -> List[Dict[str, Any]]:
    bus_schedules = []
    duration_hours = max(3, int(distance_km / 55.0))
    base_rate = max(120, int(distance_km * 0.7))

    for i in range(1, 51):
        dep_hour = (i * 2 + 1) % 24
        arr_hour = (dep_hour + duration_hours) % 24

        bus_schedules.append({
            "operator": f"redBus Express {i}",
            "mode": "bus",
            "origin_station": f"{origin} Bus Terminal",
            "destination_station": f"{destination} Bus Stand",
            "departure_time": f"{date}T{dep_hour:02d}:15:00",
            "arrival_time": f"{date}T{arr_hour:02d}:45:00",
            "fare": base_rate + (i * 10),
            "available_seats": (i * 2) % 40 + 1
        })
    return bus_schedules

def fetch_mainline_routes(origin: str, destination: str, date: str, distance_km: float = 350.0) -> List[Dict[str, Any]]:
    trains = get_train_schedules(origin, destination, date, distance_km)
    buses = get_bus_schedules(origin, destination, date, distance_km)
    return trains + buses

# ==============================================================================
# 2. MEMBER 3 ROUTER STITCHING ENGINE
# ==============================================================================

def plan_journey(start_location: Dict[str, Any], end_location: Dict[str, Any], preferred_departure: datetime, sort_preference: str = "cheapest") -> List[Dict[str, Any]]:
    origin_name = start_location.get("name", "Origin")
    dest_name = end_location.get("name", "Destination")
    date_str = preferred_departure.strftime("%Y-%m-%d")

    main_distance = calculate_haversine_distance(
        start_location["lat"], start_location["lon"],
        end_location["lat"], end_location["lon"]
    )
    if main_distance <= 0:
        main_distance = 10.0

    mainline_options = fetch_mainline_routes(origin_name, dest_name, date_str, distance_km=main_distance)

    origin_station_loc = {"lat": start_location["lat"] + 0.05, "lon": start_location["lon"] + 0.05, "name": f"{origin_name} Station"}
    dest_station_loc = {"lat": end_location["lat"] - 0.05, "lon": end_location["lon"] - 0.05, "name": f"{dest_name} Station"}

    first_mile_cabs = get_cab_quotes(start_location, origin_station_loc, preferred_departure)
    complete_journeys = []

    for i, transit in enumerate(mainline_options[:15]):
        first_mile = first_mile_cabs[i % len(first_mile_cabs)]
        transit_arrival_time = datetime.fromisoformat(transit["arrival_time"])
        
        last_mile_cabs = get_cab_quotes(dest_station_loc, end_location, transit_arrival_time)
        last_mile = last_mile_cabs[i % len(last_mile_cabs)]

        total_cost = first_mile["price"] + transit["fare"] + last_mile["price"]
        first_buffer_mins = 15
        last_buffer_mins = 10
        
        transit_dep_time = datetime.fromisoformat(transit["departure_time"])
        transit_duration_mins = (transit_arrival_time - transit_dep_time).total_seconds() / 60
        if transit_duration_mins < 0:
            transit_duration_mins += 24 * 60
        
        total_travel_time_mins = (
            first_mile["wait_time_minutes"] + 
            first_buffer_mins + 
            transit_duration_mins + 
            last_buffer_mins + 
            last_mile["wait_time_minutes"]
        )

        journey = {
            "journey_id": f"JRN-{i+1}",
            "summary": f"{origin_name} → {first_mile['car_type']} → {transit['mode'].capitalize()} ({transit['operator']}) → {last_mile['car_type']} → {dest_name}",
            "first_mile_leg": first_mile,
            "main_transit_leg": transit,
            "last_mile_leg": last_mile,
            "total_cost": round(total_cost, 2),
            "total_travel_time_minutes": round(total_travel_time_mins, 2)
        }
        complete_journeys.append(journey)

    if sort_preference.lower() == "cheapest":
        complete_journeys.sort(key=lambda x: x["total_cost"])
    elif sort_preference.lower() == "fastest":
        complete_journeys.sort(key=lambda x: x["total_travel_time_minutes"])
    
    return complete_journeys

# ==============================================================================
# 3. MEMBER 4 REAL-TIME TRACKING MONITOR
# ==============================================================================

def monitor_journey(origin: str, destination: str, travel_date: str, delay_minutes: int = 30) -> Dict[str, Any]:
    routes = fetch_mainline_routes(origin, destination, travel_date)
    if not routes:
        return {"status_message": "No mainline routes found.", "connection_at_risk": False}

    delayed_schedule = routes[0]
    arr = datetime.fromisoformat(delayed_schedule["arrival_time"])

    delayed_arrival = arr + timedelta(minutes=delay_minutes)
    delayed_schedule["scheduled_arrival_time"] = delayed_schedule["arrival_time"]
    delayed_schedule["arrival_time"] = delayed_arrival.isoformat()
    delayed_schedule["delay_minutes"] = delay_minutes

    cab_pickup_time = arr + timedelta(minutes=10)
    available_buffer = int((cab_pickup_time - delayed_arrival).total_seconds() / 60)
    at_risk = available_buffer < 15

    mode = delayed_schedule.get("mode", "transport").title()
    if delay_minutes == 0:
        msg = f"{mode} is running on time - connection remains unchanged."
    elif at_risk:
        rec_time = (delayed_arrival + timedelta(minutes=15)).strftime("%H:%M")
        msg = f"⚠️ ALERT: {mode} ({origin} to {destination}) running {delay_minutes} mins late - Connection at risk! Recommended Cab Reschedule to {rec_time}."
    else:
        msg = f"ℹ️ NOTICE: {mode} running {delay_minutes} mins late - Current connection is still feasible."

    return {
        "status_message": msg,
        "connection_at_risk": at_risk,
        "delay_minutes": delay_minutes,
        "updated_option": delayed_schedule
    }

# ==============================================================================
# 4. FASTAPI APP & ENDPOINTS
# ==============================================================================

app = FastAPI(title="Smart Passenger Journey Assistant")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_location_coords(city_name: str, fallback_lat: float, fallback_lon: float) -> Dict[str, float]:
    key = city_name.lower().strip()
    if key in CITY_COORDS:
        return CITY_COORDS[key]
    
    name_hash = sum(ord(c) for c in key)
    generated_lat = round(10.0 + (name_hash % 1800) / 100.0, 4)
    generated_lon = round(70.0 + (name_hash % 1500) / 100.0, 4)
    return {"lat": generated_lat, "lon": generated_lon}

@app.get("/api/routes")
def get_routes(
    origin: str = Query("Chennai"),
    destination: str = Query("Bangalore"),
    date: str = Query("2026-08-20"),
    preference: str = Query("cheapest")
):
    start_coords = get_location_coords(origin, 13.0827, 80.2707)
    end_coords = get_location_coords(destination, 12.9716, 77.5946)

    mock_start = {**start_coords, "name": origin.title()}
    mock_end = {**end_coords, "name": destination.title()}
    
    try:
        preferred_time = datetime.strptime(f"{date} 08:00:00", "%Y-%m-%d %H:%M:%S")
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD.")

    journeys = plan_journey(mock_start, mock_end, preferred_time, sort_preference=preference)
    return {"status": "success", "data": journeys}

@app.get("/api/live-tracking")
def get_live_tracking(
    origin: str = Query("Chennai"),
    destination: str = Query("Bangalore"),
    date: str = Query("2026-08-20"),
    delay: int = Query(35)
):
    tracking_info = monitor_journey(origin, destination, date, delay_minutes=delay)
    return {"status": "success", "data": tracking_info}

# ==============================================================================
# 5. MULTI-PAGE VIEW INTERFACE
# ==============================================================================

HTML_CONTENT = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Smart Passenger Journey Assistant</title>
    <style>
        :root {
            --bg-color: #F8FAFC;
            --primary-blue: #2563EB;
            --teal: #0D9488;
            --card-bg: #FFFFFF;
            --main-text: #0F172A;
            --secondary-text: #475569;
            --success: #16A34A;
            --warning: #B45309;
            --border-color: #E2E8F0;
        }

        * { box-sizing: border-box; margin: 0; padding: 0; font-family: system-ui, -apple-system, sans-serif; }
        body { background-color: var(--bg-color); color: var(--main-text); min-height: 100vh; display: flex; flex-direction: column; }

        .page { display: none; width: 100%; max-width: 1200px; margin: 0 auto; padding: 40px 24px; flex-direction: column; gap: 32px; }
        .page.active { display: flex; }

        /* CENTER HERO PAGE (PAGE 1) */
        #homePage { align-items: center; justify-content: center; text-align: center; min-height: 85vh; }
        .hero-title { font-size: 3.2rem; font-weight: 900; color: var(--primary-blue); letter-spacing: -1px; margin-bottom: 12px; }
        .hero-subtitle { font-size: 1.25rem; color: var(--secondary-text); margin-bottom: 40px; max-width: 600px; }

        .search-card { background: var(--card-bg); border-radius: 20px; border: 1.5px solid var(--border-color); padding: 36px; box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.05); width: 100%; max-width: 900px; }
        
        .form-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 20px; text-align: left; }
        .form-group { display: flex; flex-direction: column; gap: 8px; }
        .form-group label { font-size: 0.9rem; font-weight: 700; color: var(--secondary-text); text-transform: uppercase; letter-spacing: 0.5px; }
        .form-group input, .form-group select { padding: 14px 18px; border: 1.5px solid var(--border-color); border-radius: 10px; font-size: 1.05rem; outline: none; background: #FFF; color: var(--main-text); font-weight: 500; }
        .form-group input:focus, .form-group select:focus { border-color: var(--primary-blue); box-shadow: 0 0 0 4px rgba(37, 99, 235, 0.15); }

        .btn { background-color: var(--primary-blue); color: #FFF; border: none; padding: 16px 32px; font-size: 1.1rem; font-weight: 700; border-radius: 12px; cursor: pointer; width: 100%; margin-top: 24px; transition: all 0.2s; }
        .btn:hover { background-color: #1D4ED8; transform: translateY(-1px); }
        .btn-secondary { background-color: transparent; color: var(--secondary-text); border: 2px solid var(--border-color); padding: 10px 20px; width: auto; margin: 0; font-size: 0.95rem; }
        .btn-secondary:hover { background-color: #E2E8F0; color: var(--main-text); }

        /* RESULTS PAGE (PAGE 2) */
        .results-header { display: flex; justify-content: space-between; align-items: center; border-bottom: 2px solid var(--border-color); padding-bottom: 20px; }
        .banner { background-color: #FEF3C7; border-left: 6px solid var(--warning); color: #78350F; padding: 16px 20px; border-radius: 10px; font-weight: 600; font-size: 1rem; width: 100%; }

        .results-list { display: flex; flex-direction: column; gap: 20px; }
        .journey-card { border: 1.5px solid var(--border-color); border-radius: 16px; padding: 24px; background-color: var(--card-bg); cursor: pointer; transition: all 0.2s; display: flex; flex-direction: column; gap: 16px; }
        .journey-card:hover { border-color: var(--primary-blue); box-shadow: 0 8px 20px rgba(0,0,0,0.06); transform: translateY(-2px); }
        
        .journey-header { display: flex; justify-content: space-between; align-items: center; }
        .journey-title { display: flex; align-items: center; gap: 12px; }
        .journey-id { font-weight: 800; color: var(--primary-blue); font-size: 1.2rem; }
        .badge { padding: 4px 12px; border-radius: 20px; font-size: 0.8rem; font-weight: 800; color: #FFF; background-color: var(--teal); text-transform: uppercase; }
        .journey-cost { font-size: 1.6rem; font-weight: 900; color: var(--success); }

        .timeline-bar { display: flex; justify-content: space-between; align-items: center; background: #F1F5F9; padding: 16px 20px; border-radius: 10px; font-size: 0.95rem; font-weight: 600; color: var(--secondary-text); }

        /* DETAIL PAGE (PAGE 3 / MODAL) */
        .detail-card { background: var(--card-bg); border-radius: 20px; border: 1.5px solid var(--border-color); padding: 36px; box-shadow: 0 10px 25px rgba(0,0,0,0.05); display: flex; flex-direction: column; gap: 24px; }
        .detail-step { display: flex; gap: 20px; border-left: 4px solid var(--primary-blue); padding-left: 20px; margin-bottom: 12px; }
        .detail-step-content h4 { font-size: 1.1rem; color: var(--main-text); font-weight: 700; margin-bottom: 4px; }
        .detail-step-content p { font-size: 0.95rem; color: var(--secondary-text); }

        @media (max-width: 768px) {
            .form-grid { grid-template-columns: 1fr; }
            .hero-title { font-size: 2.2rem; }
            .timeline-bar { flex-direction: column; align-items: flex-start; gap: 8px; }
        }
    </style>
</head>
<body>

<!-- PAGE 1: CENTERED SEARCH HOME -->
<div id="homePage" class="page active">
    <div>
        <h1 class="hero-title">Smart Passenger Assistant</h1>
        <p class="hero-subtitle">Plan custom multi-modal trips with real-time transit & route stitching</p>
    </div>

    <div class="search-card">
        <form id="searchForm">
            <div class="form-grid">
                <div class="form-group">
                    <label for="origin">From (Origin)</label>
                    <input type="text" id="origin" placeholder="e.g. Chennai" required>
                </div>
                <div class="form-group">
                    <label for="destination">To (Destination)</label>
                    <input type="text" id="destination" placeholder="e.g. Bangalore" required>
                </div>
                <div class="form-group">
                    <label for="date">Travel Date</label>
                    <input type="date" id="date" required>
                </div>
                <div class="form-group">
                    <label for="preference">Mode Preference</label>
                    <select id="preference">
                        <option value="cheapest">Cheapest First</option>
                        <option value="fastest">Fastest First</option>
                    </select>
                </div>
            </div>
            <button type="submit" class="btn">Generate & Search Routes ➔</button>
        </form>
    </div>
</div>

<!-- PAGE 2: ROUTE LIST OVERVIEW -->
<div id="resultsPage" class="page">
    <div class="results-header">
        <div>
            <h2 id="routeResultsTitle" style="font-size:1.8rem; color:var(--primary-blue);">Available Routes</h2>
            <p id="routeResultsSubtitle" style="color:var(--secondary-text);">Select any route to view complete details</p>
        </div>
        <button class="btn btn-secondary" onclick="navigateTo('homePage')">← New Search</button>
    </div>

    <div id="liveAlertBanner" class="banner">
        <span id="bannerText">🔄 Checking live connection updates...</span>
    </div>

    <div id="resultsContainer" class="results-list">
        <!-- Dynamic Cards Load Here -->
    </div>
</div>

<!-- PAGE 3: ROUTE DETAILS -->
<div id="detailsPage" class="page">
    <div class="results-header">
        <div>
            <h2 style="font-size:1.8rem; color:var(--primary-blue);">Detailed Journey Breakdown</h2>
            <p style="color:var(--secondary-text);">Step-by-step connection analysis</p>
        </div>
        <button class="btn btn-secondary" onclick="navigateTo('resultsPage')">← Back to All Routes</button>
    </div>

    <div id="detailsContainer" class="detail-card">
        <!-- Selected Route Detail Loads Here -->
    </div>
</div>

<script>
    // Set default date picker to today
    document.getElementById('date').valueAsDate = new Date();

    let loadedJourneys = [];

    function navigateTo(pageId) {
        document.querySelectorAll('.page').forEach(page => page.classList.remove('active'));
        document.getElementById(pageId).classList.add('active');
        window.scrollTo(0,0);
    }

    async function fetchLiveTracking(origin, destination, date) {
        try {
            const res = await fetch(`/api/live-tracking?origin=${encodeURIComponent(origin)}&destination=${encodeURIComponent(destination)}&date=${date}&delay=35`);
            const json = await res.json();
            if(json.status === "success") {
                document.getElementById('bannerText').innerText = json.data.status_message;
            }
        } catch (e) {
            document.getElementById('bannerText').innerText = "Unable to fetch live connection alerts.";
        }
    }

    document.getElementById('searchForm').addEventListener('submit', async function(e) {
        e.preventDefault();
        
        const origin = document.getElementById('origin').value.trim();
        const destination = document.getElementById('destination').value.trim();
        const date = document.getElementById('date').value;
        const preference = document.getElementById('preference').value;

        if(!origin || !destination) return;

        // Transition to results page
        navigateTo('resultsPage');
        document.getElementById('routeResultsTitle').innerText = `${origin} to ${destination}`;
        document.getElementById('routeResultsSubtitle').innerText = `Travel Date: ${date} | Preferred Mode: ${preference.toUpperCase()}`;
        
        const container = document.getElementById('resultsContainer');
        container.innerHTML = "<p style='text-align:center; font-size:1.2rem; padding:40px;'>Calculating optimal multi-modal routes...</p>";

        fetchLiveTracking(origin, destination, date);

        try {
            const res = await fetch(`/api/routes?origin=${encodeURIComponent(origin)}&destination=${encodeURIComponent(destination)}&date=${date}&preference=${preference}`);
            const json = await res.json();
            
            if(json.status === "success" && json.data.length > 0) {
                loadedJourneys = json.data;
                renderJourneysList(json.data);
            } else {
                container.innerHTML = "<p style='text-align:center; font-size:1.2rem; padding:40px;'>No available routes found for these locations.</p>";
            }
        } catch(err) {
            container.innerHTML = "<p style='text-align:center; font-size:1.2rem; color: #DC2626; padding:40px;'>Failed to connect to server.</p>";
        }
    });

    function renderJourneysList(journeys) {
        const container = document.getElementById('resultsContainer');
        container.innerHTML = journeys.map((j, index) => `
            <div class="journey-card" onclick="openRouteDetails(${index})">
                <div class="journey-header">
                    <div class="journey-title">
                        <span class="journey-id">${j.journey_id}</span>
                        <span class="badge">${j.main_transit_leg.mode}</span>
                    </div>
                    <div class="journey-cost">₹${j.total_cost}</div>
                </div>

                <div class="timeline-bar">
                    <span>🚕 ${j.first_mile_leg.company_name}</span>
                    <span>➔</span>
                    <span>🚆 ${j.main_transit_leg.operator}</span>
                    <span>➔</span>
                    <span>🚖 ${j.last_mile_leg.company_name}</span>
                </div>

                <div style="display:flex; justify-content:space-between; font-size:0.9rem; color:var(--secondary-text);">
                    <span><strong>Total Time:</strong> ${j.total_travel_time_minutes} Mins</span>
                    <span style="color:var(--primary-blue); font-weight:700;">Click for complete itinerary ➔</span>
                </div>
            </div>
        `).join('');
    }

    function openRouteDetails(index) {
        const j = loadedJourneys[index];
        if(!j) return;

        const container = document.getElementById('detailsContainer');
        container.innerHTML = `
            <div style="display:flex; justify-content:space-between; align-items:center; border-bottom:2px solid var(--border-color); padding-bottom:16px;">
                <h3 style="font-size:1.5rem; color:var(--primary-blue);">${j.journey_id} Full Route Plan</h3>
                <span style="font-size:2rem; font-weight:900; color:var(--success);">₹${j.total_cost}</span>
            </div>

            <div class="detail-step">
                <div class="detail-step-content">
                    <h4>Leg 1: Pickup Cab (First Mile)</h4>
                    <p><strong>Provider:</strong> ${j.first_mile_leg.company_name} (${j.first_mile_leg.car_type})</p>
                    <p><strong>Pickup Hub:</strong> ${j.first_mile_leg.pickup_location}</p>
                    <p><strong>Estimated Fare:</strong> ₹${j.first_mile_leg.price} | Wait Time: ${j.first_mile_leg.wait_time_minutes} mins</p>
                </div>
            </div>

            <div class="detail-step" style="border-left-color: var(--teal);">
                <div class="detail-step-content">
                    <h4>Leg 2: Intercity Transit (${j.main_transit_leg.mode.toUpperCase()})</h4>
                    <p><strong>Operator:</strong> ${j.main_transit_leg.operator}</p>
                    <p><strong>From:</strong> ${j.main_transit_leg.origin_station} ➔ <strong>To:</strong> ${j.main_transit_leg.destination_station}</p>
                    <p><strong>Departure:</strong> ${j.main_transit_leg.departure_time.replace('T', ' ')}</p>
                    <p><strong>Arrival:</strong> ${j.main_transit_leg.arrival_time.replace('T', ' ')}</p>
                    <p><strong>Ticket Fare:</strong> ₹${j.main_transit_leg.fare} | Available Seats: ${j.main_transit_leg.available_seats}</p>
                </div>
            </div>

            <div class="detail-step" style="border-left-color: var(--warning);">
                <div class="detail-step-content">
                    <h4>Leg 3: Destination Cab (Last Mile)</h4>
                    <p><strong>Provider:</strong> ${j.last_mile_leg.company_name} (${j.last_mile_leg.car_type})</p>
                    <p><strong>Dropoff Point:</strong> ${j.last_mile_leg.drop_location}</p>
                    <p><strong>Estimated Fare:</strong> ₹${j.last_mile_leg.price} | Wait Time: ${j.last_mile_leg.wait_time_minutes} mins</p>
                </div>
            </div>

            <div style="background:#F1F5F9; padding:16px; border-radius:10px; font-weight:600; color:var(--main-text);">
                ⏱️ Total Estimated End-to-End Travel Duration: ${j.total_travel_time_minutes} minutes
            </div>
        `;

        navigateTo('detailsPage');
    }
</script>

</body>
</html>
"""

@app.get("/", response_class=HTMLResponse)
def read_root():
    return HTML_CONTENT

if __name__ == "__main__":
    # Updated host to 127.0.0.1 so the browser can directly open http://127.0.0.1:8000
    uvicorn.run(app, host="127.0.0.1", port=8000)