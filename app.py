"""
Flight Tracking System - Main Application
==========================================
This mimics FlightAware's radio signal receiver system.

Key Components:
1. POST API: Receives flight position data (like radio signals)
2. GET API: Tracks flights and shows their path
3. MongoDB: Stores active flights and completed flight logs
4. Auto-archiving: Landed flights move to logs automatically

Author: [Muhammad Umair  FA23-BCS-135]
Date: 22 October 2025
"""

from datetime import datetime

from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from pymongo import MongoClient
import os

# Initialize Flask app
app = Flask(__name__)
CORS(app)
mongo_uri = os.environ.get('MONGO_URI', 'mongodb://localhost:27017/')
try:
    client = MongoClient(mongo_uri)
    db = client['flightaware_db']

    active_flights = db['active_flights']  # FLYING
    flight_logs = db['flight_logs']  # COMPLETED

    print(" Connected to Database successfully!")
except Exception as e:
    print(f"[ERROR] MongoDB Connection Error: {e}")
    print("Make sure MongoDB is running: 'mongod' or 'sudo systemctl start mongod'")


def serialize_doc(doc):
    # Convert ObjectId to string for JSON serialization (Convert  ObjectId to string for JSON serialization   MongoDB
    # stores _id as ObjectId, but JSON needs strings)
    if doc and '_id' in doc:
        doc['_id'] = str(doc['_id'])
    return doc


# api

@app.route('/')
def home():
    return render_template('web_dashboard.html')

@app.route('/api/flights/ingest', methods=['POST'])
def ingest_flight_data():
    try:
        data = request.get_json()

        #  Validate required fields
        required_fields = ['flight_number', 'latitude', 'longitude',
                           'altitude', 'speed', 'timestamp']

        for field in required_fields:
            if field not in data:
                return jsonify({
                    "error": f"Missing required field: {field}"
                }), 400

        flight_number = data['flight_number']

        #  Create position update object
        position_update = {
            "latitude": float(data['latitude']),
            "longitude": float(data['longitude']),
            "altitude": float(data['altitude']),
            "speed": float(data['speed']),
            "heading": float(data.get('heading', 0)),  # Default 0 if not provided
            "timestamp": data['timestamp']
        }

        # Check if flight already exists
        existing_flight = active_flights.find_one({"flight_number": flight_number})

        if existing_flight:
            active_flights.update_one(
                {"flight_number": flight_number},
                {
                    "$push": {"position_history": position_update},  # Add to array
                    "$set": {
                        "current_position": position_update,  # Update latest position
                        "last_update": datetime.utcnow(),
                        "status": data.get('status', 'in_flight')
                    }
                }
            )
        else:
            # if new flight, create document
            flight_doc = {
                "flight_number": flight_number,
                "status": data.get('status', 'in_flight'),
                "current_position": position_update,
                "position_history": [position_update],  # Start with first position
                "created_at": datetime.utcnow(),
                "last_update": datetime.utcnow()
            }
            active_flights.insert_one(flight_doc)

        #  Check if flight has landed
        if data.get('status') == 'landed':
            flight_data = active_flights.find_one({"flight_number": flight_number})

            if flight_data:
                # Movee to flight_logs
                log_entry = {
                    "flight_number": flight_number,
                    "position_history": flight_data['position_history'],
                    "flight_start": flight_data['created_at'],
                    "flight_end": datetime.utcnow(),
                    "total_positions": len(flight_data['position_history'])
                }
                flight_logs.insert_one(log_entry)

                # Remove from active flights
                active_flights.delete_one({"flight_number": flight_number})

                return jsonify({
                    "message": "Flight landed and moved to logs",
                    "flight_number": flight_number
                }), 200

        return jsonify({
            "message": "Flight data ingested successfully",
            "flight_number": flight_number
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/flights/track/<flight_number>', methods=['GET'])
def track_flight(flight_number):
    """
    GET API - Track Flight
    ======================
    Get current location and full tracking history of a flight.

    Usage:
    - Track current: /api/flights/track/AA123
    - At specific time: /api/flights/track/AA123?timestamp=2025-10-21T10:30:00

    Returns:
    {
        "flight_number": "AA123",
        "status": "in_flight",
        "current_position": {...},
        "position_history": [...],  // Complete flight path
        "total_updates": 15
    }
    """
    try:
        # Step 1: Look for flight in active flights
        flight = active_flights.find_one({"flight_number": flight_number})

        if not flight:
            # Step 2: If not active, check in logs (completed flights)
            flight = flight_logs.find_one({"flight_number": flight_number})
            if not flight:
                return jsonify({"error": "Flight not found"}), 404

            flight['status'] = 'completed'

        # Step 3: Check if specific timestamp requested
        timestamp = request.args.get('timestamp')

        if timestamp:
            # Find position at that specific time
            position_at_time = None
            for pos in flight['position_history']:
                if pos['timestamp'] == timestamp:
                    position_at_time = pos
                    break

            if position_at_time:
                return jsonify({
                    "flight_number": flight_number,
                    "timestamp": timestamp,
                    "position": position_at_time
                }), 200
            else:
                return jsonify({
                    "error": "No position data for that timestamp"
                }), 404

        # Step 4: Return full tracking data
        response = {
            "flight_number": flight_number,
            "status": flight.get('status', 'completed'),
            "current_position": flight.get('current_position'),
            "position_history": flight['position_history'],
            "total_updates": len(flight['position_history'])
        }

        return jsonify(serialize_doc(response)), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/flights/active', methods=['GET'])
def get_active_flights():
    # GET API - Get All Active Flights
    try:
        flights = list(active_flights.find())

        # Convert ObjectId to string for each flight

        for flight in flights:
            serialize_doc(flight)

        return jsonify({
            "active_flights": flights,
            "count": len(flights)
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/flights/logs', methods=['GET'])
def get_flight_logs():
    # GET API - Get Flight Logs --Shows last 50 flights.

    try:
        logs = list(flight_logs.find().limit(50))

        # Convert ObjectId to string for each log
        for log in logs:
            serialize_doc(log)

        return jsonify({
            "flight_logs": logs,
            "count": len(logs)
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ============================================
# HYBRID SEARCH API (NEW REQUIREMENT)
# ============================================
@app.route('/api/flights/search', methods=['GET'])
def hybrid_search():
    """
    Hybrid Search API - Search flights by multiple criteria

    Query Parameters:
    - flight_number: Partial match (e.g., ?flight_number=PK)
    - status: Exact match (e.g., ?status=in_flight)
    - min_altitude: Minimum altitude (e.g., ?min_altitude=30000)
    - max_altitude: Maximum altitude (e.g., ?max_altitude=40000)
    - min_speed: Minimum speed (e.g., ?min_speed=400)
    - airline: Search by airline name (e.g., ?airline=Emirates)

    Examples:
    /api/flights/search?flight_number=PK
    /api/flights/search?status=in_flight&min_altitude=30000
    /api/flights/search?flight_number=PK&min_speed=400
    """
    try:
        query = {}

        # TEXT SEARCH: Flight number (case-insensitive partial match)
        if 'flight_number' in request.args:
            flight_num = request.args['flight_number'].strip()
            query['flight_number'] = {
                '$regex': flight_num,
                '$options': 'i'  # Case insensitive
            }

        # STATUS FILTER: Exact match
        if 'status' in request.args:
            query['status'] = request.args['status']

        # ALTITUDE RANGE SEARCH
        altitude_query = {}
        if 'min_altitude' in request.args:
            min_alt = float(request.args['min_altitude'])
            altitude_query['$gte'] = min_alt

        if 'max_altitude' in request.args:
            max_alt = float(request.args['max_altitude'])
            altitude_query['$lte'] = max_alt

        if altitude_query:
            query['current_position.altitude'] = altitude_query

        # SPEED RANGE SEARCH
        speed_query = {}
        if 'min_speed' in request.args:
            min_spd = float(request.args['min_speed'])
            speed_query['$gte'] = min_spd

        if 'max_speed' in request.args:
            max_spd = float(request.args['max_speed'])
            speed_query['$lte'] = max_spd

        if speed_query:
            query['current_position.speed'] = speed_query

        # Execute hybrid search on active flights
        results = list(active_flights.find(query))

        # Also search in completed flights if no status filter
        if 'status' not in request.args or request.args['status'] == 'completed':
            # For completed flights, we need to adjust the query
            logs_query = {}
            if 'flight_number' in request.args:
                flight_num = request.args['flight_number'].strip()
                logs_query['flight_number'] = {
                    '$regex': flight_num,
                    '$options': 'i'
                }

            completed_results = list(flight_logs.find(logs_query))
            for comp in completed_results:
                comp['status'] = 'completed'
                results.append(comp)

        # Serialize all results
        for result in results:
            serialize_doc(result)

        return jsonify({
            "results": results,
            "count": len(results),
            "search_criteria": request.args.to_dict(),
            "message": "Hybrid search completed successfully"
        }), 200

    except ValueError as e:
        return jsonify({
            "error": "Invalid numeric value",
            "details": str(e)
        }), 400
    except Exception as e:
        return jsonify({
            "error": "Search failed",
            "details": str(e)
        }), 500


if __name__ == '__main__':
    print("\n" + "=" * 60)
    print("FLIGHT TRACKING SYSTEM - STARTING...")
    print("=" * 60)
    print("\nDatabase:")
    print("   - Database: flightaware_db")
    print("   - Active Flights: active_flights collection")
    print("   - Flight Logs: flight_logs collection")
    print("\nAPI Endpoints:")
    print("   POST /api/flights/ingest          - Ingest flight data")
    print("   GET  /api/flights/track/<flight>  - Track specific flight")
    print("   GET  /api/flights/active          - Get all active flights")
    print("   GET  /api/flights/logs            - Get completed flights")
    print("\nServer running on: http://localhost:5000")
    print("=" * 60 + "\n")

    # start flask
    app.run(debug=True, port=5000)
