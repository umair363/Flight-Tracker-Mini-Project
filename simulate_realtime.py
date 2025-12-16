"""
Flight Tracking System - Real-Time Flight Simulator
====================================================
This is the MAIN system that simulates real-time flight tracking.

Features:
- 10 realistic flight routes (Pakistan + International)
- Real-time position updates every 8 seconds
- Automatic takeoff, cruise, descent, and landing
- Live tracking on web dashboard
- Automatic archiving when flights land

How to use:
1. Start MongoDB: mongod
2. Start Flask API: python app.py
3. Run this simulator: python flight_simulator.py
4. Open web_dashboard.html and watch flights move live!

Author: [Your Name]
Date: October 2025
"""

import requests
import time
from datetime import datetime
import threading
import random

BASE_URL = "http://localhost:5000"

# ============================================
# FLIGHT ROUTES DATABASE
# ============================================

FLIGHT_ROUTES = [
    # Domestic Pakistani Flights
    {
        "flight_number": "PK301",
        "airline": "Pakistan International Airlines",
        "route": "Lahore → Karachi",
        "start": (31.5204, 74.3587),  # Lahore
        "end": (24.8607, 67.0011),     # Karachi
        "cruise_altitude": 35000,
        "cruise_speed": 480,
        "color": "🔵"
    },
    {
        "flight_number": "PK456",
        "airline": "Pakistan International Airlines",
        "route": "Karachi → Islamabad",
        "start": (24.8607, 67.0011),   # Karachi
        "end": (33.6844, 73.0479),     # Islamabad
        "cruise_altitude": 34000,
        "cruise_speed": 470,
        "color": "🟢"
    },
    {
        "flight_number": "PA201",
        "airline": "Air Blue",
        "route": "Islamabad → Lahore",
        "start": (33.6844, 73.0479),   # Islamabad
        "end": (31.5204, 74.3587),     # Lahore
        "cruise_altitude": 32000,
        "cruise_speed": 450,
        "color": "🟡"
    },

    # Regional International Flights
    {
        "flight_number": "PK785",
        "airline": "Pakistan International Airlines",
        "route": "Islamabad → Dubai",
        "start": (33.6844, 73.0479),   # Islamabad
        "end": (25.2532, 55.3657),     # Dubai
        "cruise_altitude": 38000,
        "cruise_speed": 500,
        "color": "🟠"
    },
    {
        "flight_number": "EK542",
        "airline": "Emirates",
        "route": "Dubai → Lahore",
        "start": (25.2532, 55.3657),   # Dubai
        "end": (31.5204, 74.3587),     # Lahore
        "cruise_altitude": 37000,
        "cruise_speed": 490,
        "color": "🔴"
    },
    {
        "flight_number": "QR101",
        "airline": "Qatar Airways",
        "route": "Doha → Islamabad",
        "start": (25.2731, 51.6080),   # Doha
        "end": (33.6844, 73.0479),     # Islamabad
        "cruise_altitude": 36000,
        "cruise_speed": 485,
        "color": "🟣"
    },
    {
        "flight_number": "FZ150",
        "airline": "Fly Dubai",
        "route": "Dubai → Karachi",
        "start": (25.2532, 55.3657),   # Dubai
        "end": (24.8607, 67.0011),     # Karachi
        "cruise_altitude": 35500,
        "cruise_speed": 475,
        "color": "🟤"
    },

    # Long-haul International Flights
    {
        "flight_number": "AA123",
        "airline": "American Airlines",
        "route": "Karachi → London",
        "start": (24.8607, 67.0011),   # Karachi
        "end": (51.4700, -0.4543),     # London
        "cruise_altitude": 41000,
        "cruise_speed": 520,
        "color": "⚫"
    },
    {
        "flight_number": "BA260",
        "airline": "British Airways",
        "route": "London → Karachi",
        "start": (51.4700, -0.4543),   # London
        "end": (24.8607, 67.0011),     # Karachi
        "cruise_altitude": 42000,
        "cruise_speed": 530,
        "color": "⚪"
    },
    {
        "flight_number": "TK710",
        "airline": "Turkish Airlines",
        "route": "Istanbul → Lahore",
        "start": (40.9769, 28.8169),   # Istanbul
        "end": (31.5204, 74.3587),     # Lahore
        "cruise_altitude": 39000,
        "cruise_speed": 510,
        "color": "🟥"
    }
]


# ============================================
# FLIGHT SIMULATION CLASS
# ============================================

class FlightSimulator:
    """Simulates a single flight from takeoff to landing"""

    def __init__(self, flight_info):
        self.flight_number = flight_info['flight_number']
        self.airline = flight_info['airline']
        self.route = flight_info['route']
        self.color = flight_info['color']

        # Position
        self.current_lat = flight_info['start'][0]
        self.current_lon = flight_info['start'][1]
        self.target_lat = flight_info['end'][0]
        self.target_lon = flight_info['end'][1]

        # Flight parameters
        self.cruise_altitude = flight_info['cruise_altitude']
        self.cruise_speed = flight_info['cruise_speed']

        # Current state
        self.altitude = 0
        self.speed = 0
        self.heading = self.calculate_heading()
        self.phase = "ground"  # ground, climbing, cruising, descending, landed

        # Statistics
        self.updates_sent = 0
        self.start_time = datetime.now()

    def calculate_heading(self):
        """Calculate heading (bearing) from current to target position"""
        lat_diff = self.target_lat - self.current_lat
        lon_diff = self.target_lon - self.current_lon

        # Simplified heading calculation
        if abs(lon_diff) > abs(lat_diff):
            return 90 if lon_diff > 0 else 270  # East/West
        else:
            return 0 if lat_diff > 0 else 180   # North/South

    def calculate_distance_to_target(self):
        """Calculate distance to destination"""
        return ((self.target_lat - self.current_lat)**2 +
                (self.target_lon - self.current_lon)**2)**0.5

    def update_position(self):
        """Update flight position and parameters based on current phase"""
        distance = self.calculate_distance_to_target()

        # Check if reached destination
        if distance < 0.3:
            self.phase = "landed"
            self.altitude = 0
            self.speed = 0
            return True  # Flight completed

        # Determine flight phase based on distance
        if self.phase == "ground":
            self.phase = "climbing"
            self.speed = 150
            self.altitude = 1000

        elif self.phase == "climbing":
            # Climb phase
            self.altitude = min(self.altitude + 2500, self.cruise_altitude)
            self.speed = min(self.speed + 50, self.cruise_speed)

            if self.altitude >= self.cruise_altitude:
                self.phase = "cruising"

        elif self.phase == "cruising":
            # Cruise phase - check if approaching destination
            if distance < 4.0:
                self.phase = "descending"

        elif self.phase == "descending":
            # Descent phase
            self.altitude = max(self.altitude - 3000, 0)
            self.speed = max(self.speed - 60, 150)

            if self.altitude <= 0:
                self.phase = "landed"
                return True

        # Move towards destination
        move_speed = 0.08  # Adjust for realistic speed
        self.current_lat += (self.target_lat - self.current_lat) * move_speed
        self.current_lon += (self.target_lon - self.current_lon) * move_speed

        return False  # Flight not completed

    def get_status(self):
        """Get flight status for API"""
        if self.phase == "landed":
            return "landed"
        return "in_flight"

    def get_position_data(self):
        """Generate position data for API"""
        return {
            "flight_number": self.flight_number,
            "latitude": round(self.current_lat, 4),
            "longitude": round(self.current_lon, 4),
            "altitude": int(self.altitude),
            "speed": int(self.speed),
            "heading": self.heading,
            "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
            "status": self.get_status()
        }

    def send_update(self):
        """Send position update to API"""
        position_data = self.get_position_data()

        try:
            response = requests.post(
                f"{BASE_URL}/api/flights/ingest",
                json=position_data,
                timeout=3
            )

            if response.status_code == 200:
                self.updates_sent += 1
                return True
            else:
                print(f"{self.color} {self.flight_number}: API error - {response.status_code}")
                return False

        except Exception as e:
            print(f"{self.color} {self.flight_number}: Connection error - {str(e)[:50]}")
            return False

    def get_phase_emoji(self):
        """Get emoji for current phase"""
        phase_emojis = {
            "ground": "🛫",
            "climbing": "↗️",
            "cruising": "✈️",
            "descending": "↘️",
            "landed": "🛬"
        }
        return phase_emojis.get(self.phase, "✈️")


# ============================================
# SIMULATION MANAGER
# ============================================

def simulate_flight(flight_info, delay_start=0):
    """Simulate a single flight in its own thread"""

    # Stagger flight starts
    if delay_start > 0:
        time.sleep(delay_start)

    flight = FlightSimulator(flight_info)

    print(f"\n{flight.color} {flight.flight_number} STARTING")
    print(f"   Route: {flight.route}")
    print(f"   Airline: {flight.airline}")

    # Send initial position (takeoff)
    flight.send_update()

    # Simulation loop
    while True:
        time.sleep(8)  # Update every 8 seconds

        # Update flight state
        completed = flight.update_position()

        # Send update to API
        success = flight.send_update()

        if not success:
            print(f"{flight.color} {flight.flight_number}: Stopping due to connection error")
            break

        # Print status
        phase_emoji = flight.get_phase_emoji()
        print(f"{flight.color} {flight.flight_number}: {phase_emoji} {flight.phase.upper()} "
              f"| Alt: {flight.altitude:,}ft | Speed: {flight.speed}kts | Updates: {flight.updates_sent}")

        # Check if landed
        if completed:
            duration = (datetime.now() - flight.start_time).total_seconds() / 60
            print(f"\n{flight.color} {flight.flight_number} LANDED ✅")
            print(f"   Total Updates: {flight.updates_sent}")
            print(f"   Flight Duration: {duration:.1f} minutes")
            break


def test_connection():
    """Test if Flask server is running"""
    try:
        response = requests.get(f"{BASE_URL}/api/flights/active", timeout=3)
        return response.status_code == 200
    except:
        return False


def print_banner():
    """Print startup banner"""
    print("\n" + "="*70)
    print("✈️  FLIGHT TRACKING SYSTEM - REAL-TIME SIMULATOR")
    print("="*70)
    print("\nSimulating realistic flight operations with live tracking!")
    print(f"Total Flights: {len(FLIGHT_ROUTES)}")
    print("Update Interval: 8 seconds")
    print("\n" + "="*70 + "\n")


def main():
    """Main simulation program"""

    print_banner()

    # Test connection
    print("⏳ Testing connection to Flask API...")
    if not test_connection():
        print("\n❌ ERROR: Cannot connect to Flask server!")
        print("\nPlease make sure:")
        print("  1. MongoDB is running: mongod")
        print("  2. Flask server is running: python app.py")
        print("  3. Server is on port 5000")
        return

    print("✅ Connected to API successfully!\n")

    # Confirm start
    print("🚀 Ready to start simulation!")
    print("\nThis will simulate 10 flights with real-time updates.")
    print("Open web_dashboard.html to watch flights move on the map!\n")

    input("Press ENTER to start simulation...")

    print("\n" + "="*70)
    print("SIMULATION STARTING...")
    print("="*70)
    print("\n💡 TIP: Open web_dashboard.html now!\n")

    # Create threads for each flight
    threads = []

    for i, flight_info in enumerate(FLIGHT_ROUTES):
        # Stagger starts (2 seconds between each flight)
        delay = i * 2

        thread = threading.Thread(
            target=simulate_flight,
            args=(flight_info, delay),
            daemon=True
        )
        thread.start()
        threads.append(thread)

    # Wait for all flights to complete
    try:
        for thread in threads:
            thread.join()

        print("\n" + "="*70)
        print("✅ ALL FLIGHTS COMPLETED!")
        print("="*70)
        print("\nCheck web_dashboard.html to see:")
        print("  - Click 'Completed' tab to see all landed flights")
        print("  - Click 'Show Completed' to see all routes on map")
        print("  - Beautiful colored paths for each flight!")

    except KeyboardInterrupt:
        print("\n\n⚠️  SIMULATION STOPPED BY USER")
        print("\nFlights in database may be incomplete.")
        print("Run clear_database.py to reset before next demo.")


# ============================================
# ENTRY POINT
# ============================================

if __name__ == "__main__":
    main()