from flask import Flask, jsonify
import requests
import os
from datetime import datetime
import logging

app = Flask(__name__)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Weather API configuration (you can use OpenWeatherMap, WeatherAPI, etc.)
WEATHER_API_KEY = os.environ.get('WEATHER_API_KEY', 'your_default_api_key')
WEATHER_API_URL = "http://api.openweathermap.org/data/2.5/weather"

@app.route('/')
def home():
    return jsonify({
        "message": "Weather API Server is running",
        "endpoints": {
            "weather": "/weather/<city>",
            "weather_with_coords": "/weather?lat=<latitude>&lon=<longitude>"
        }
    })

@app.route('/weather/<city>')
def get_weather_by_city(city):
    try:
        # Make request to weather API
        params = {
            'q': city,
            'appid': WEATHER_API_KEY,
            'units': 'metric'  # Use 'imperial' for Fahrenheit
        }
        
        response = requests.get(WEATHER_API_URL, params=params, timeout=10)
        response.raise_for_status()  # Raise exception for bad status codes
        
        weather_data = response.json()
        
        # Extract relevant information
        processed_data = {
            'city': weather_data.get('name'),
            'country': weather_data.get('sys', {}).get('country'),
            'temperature': weather_data.get('main', {}).get('temp'),
            'feels_like': weather_data.get('main', {}).get('feels_like'),
            'humidity': weather_data.get('main', {}).get('humidity'),
            'description': weather_data['weather'][0]['description'] if weather_data.get('weather') else 'N/A',
            'wind_speed': weather_data.get('wind', {}).get('speed'),
            'timestamp': datetime.utcnow().isoformat()
        }
        
        logger.info(f"Weather data fetched for {city}")
        return jsonify(processed_data)
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching weather data: {e}")
        return jsonify({"error": "Failed to fetch weather data", "details": str(e)}), 500
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return jsonify({"error": "Internal server error"}), 500

@app.route('/weather')
def get_weather_by_coords():
    try:
        lat = request.args.get('lat')
        lon = request.args.get('lon')
        
        if not lat or not lon:
            return jsonify({"error": "Latitude and longitude parameters are required"}), 400
        
        params = {
            'lat': lat,
            'lon': lon,
            'appid': WEATHER_API_KEY,
            'units': 'metric'
        }
        
        response = requests.get(WEATHER_API_URL, params=params, timeout=10)
        response.raise_for_status()
        
        weather_data = response.json()
        
        processed_data = {
            'city': weather_data.get('name'),
            'coordinates': {
                'latitude': weather_data.get('coord', {}).get('lat'),
                'longitude': weather_data.get('coord', {}).get('lon')
            },
            'temperature': weather_data.get('main', {}).get('temp'),
            'description': weather_data['weather'][0]['description'] if weather_data.get('weather') else 'N/A',
            'timestamp': datetime.utcnow().isoformat()
        }
        
        return jsonify(processed_data)
        
    except requests.exceptions.RequestException as e:
        return jsonify({"error": "Failed to fetch weather data"}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=os.environ.get('DEBUG', 'False').lower() == 'true')