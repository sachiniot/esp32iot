from flask import Flask, request, jsonify
import requests
from datetime import datetime, timedelta
import openmeteo_requests
import requests_cache
from retry_requests import retry
import numpy as np

app = Flask(__name__)

# ThingsBoard configuration - UPDATE THESE WITH YOUR CREDENTIALS
THINGSBOARD_URL = "https://demo.thingsboard.io"
DEVICE_ACCESS_TOKEN = "rTDdjKOCJTeV9N1RQH1R"

# Setup the Open-Meteo API client
cache_session = requests_cache.CachedSession('.cache', expire_after=3600)
retry_session = retry(cache_session, retries=5, backoff_factor=0.2)
openmeteo = openmeteo_requests.Client(session=retry_session)

# The endpoint your ESP32 should call
@app.route('/api/data', methods=['POST'])
def receive_data():
    try:
        # Get data from ESP32
        esp_data = request.get_json()
        
        if not esp_data:
            return jsonify({"error": "No JSON data received"}), 400
        
        print(f"Received data from ESP32: {esp_data}")
        
        ####################################################################
        # EXTRACTING DATA FROM ESP32 - THESE ARE YOUR CUSTOM VARIABLES
        ####################################################################
        # Extract data sent from ESP32
        temperature = esp_data.get("temperature", 0)      # Your temperature data
        latitude = esp_data.get("latitude", 40.7128)      # Default to NY if not provided
        longitude = esp_data.get("longitude", -74.0060)   # Default to NY if not provided
        device_id = esp_data.get("device_id", "ESP32_001")
        
        ####################################################################
        # GET SOLAR DATA FROM OPEN-METEO API
        ####################################################################
        solar_data = get_solar_meteo_data(latitude, longitude)
        
        if not solar_data:
            return jsonify({"error": "Failed to fetch solar data from Open-Meteo"}), 500
        
        ####################################################################
        # PROCESS YOUR DATA - COMBINE ESP32 DATA WITH SOLAR DATA
        ####################################################################
        # Example processing - replace with your actual calculations
        processed_temp = temperature * 1.1  # Example adjustment
        status = "NORMAL" if temperature < 30 else "WARNING"  # Example logic
        
        # Get current solar data
        current_solar = solar_data.get('current_hour', {})
        
        ####################################################################
        # PREPARE DATA FOR THINGSBOARD - COMBINE ALL DATA
        ####################################################################
        # Create the data structure to send to ThingsBoard
        thingsboard_data = {
            "ts": int(datetime.utcnow().timestamp() * 1000),  # Timestamp in milliseconds
            "values": {
                # Original values from ESP32
                "temperature": temperature,
                "latitude": latitude,
                "longitude": longitude,
                "device_id": device_id,
                
                # Solar data from Open-Meteo
                "cloud_cover": current_solar.get('cloud_cover_percentage', 0),
                "solar_radiation_ghi": current_solar.get('solar_radiation', {}).get('ghi_wm2', 0),
                "solar_radiation_dni": current_solar.get('solar_radiation', {}).get('dni_wm2', 0),
                "solar_radiation_dhi": current_solar.get('solar_radiation', {}).get('dhi_wm2', 0),
                "lux_intensity": current_solar.get('lux_intensity_approx', 0),
                "sunshine_duration": current_solar.get('sunshine_duration_seconds', 0),
                "is_day": current_solar.get('is_day', False),
                "irradiance_quality": current_solar.get('irradiance_factors', {}).get('irradiance_quality', 'unknown'),
                "clearness_index": current_solar.get('irradiance_factors', {}).get('clearness_index', 0),
                
                # Your processed values
                "processed_temp": processed_temp,
                "status": status,
                
                # Solar panel performance estimates
                "estimated_panel_output": current_solar.get('panel_performance', {}).get('estimated_output_w', 0),
                "performance_ratio": current_solar.get('panel_performance', {}).get('performance_ratio', 0),
                
                # Weather condition
                "weather_condition": current_solar.get('weather_condition', 'unknown')
            }
        }
        
        # Send processed data to ThingsBoard
        thingsboard_result = send_to_thingsboard(thingsboard_data)
        thingsboard_success = thingsboard_result.get("success", False)
        
        # Prepare comprehensive response for ESP32
        response_data = {
            "status": "success" if thingsboard_success else "partial_success",
            "message": "Data processed and sent to ThingsBoard" if thingsboard_success else "Data processed but ThingsBoard failed",
            "timestamp": datetime.utcnow().isoformat(),
            "thingsboard_status": thingsboard_result,
            "solar_data_received": solar_data is not None,
            "thingsboard_payload": thingsboard_data,  # This is what was sent to ThingsBoard
            "processed_data": {
                "original_temperature": temperature,
                "processed_temperature": processed_temp,
                "status": status,
                "solar_radiation": current_solar.get('solar_radiation', {}).get('ghi_wm2', 0),
                "cloud_cover": current_solar.get('cloud_cover_percentage', 0),
                "estimated_power": current_solar.get('panel_performance', {}).get('estimated_output_w', 0),
                "lux_intensity": current_solar.get('lux_intensity_approx', 0),
                "is_day": current_solar.get('is_day', False),
                "weather_condition": current_solar.get('weather_condition', 'unknown')
            },
            "location_info": {
                "latitude": latitude,
                "longitude": longitude,
                "location_name": solar_data.get('location', {}).get('name', 'Unknown')
            }
        }
        
        if thingsboard_success:
            return jsonify(response_data), 200
        else:
            return jsonify(response_data), 207  # 207 Multi-Status (partial success)
            
    except Exception as e:
        print(f"Error processing data: {str(e)}")
        return jsonify({
            "status": "error",
            "message": str(e),
            "timestamp": datetime.utcnow().isoformat(),
            "thingsboard_status": {"success": False, "error": str(e)}
        }), 500

def send_to_thingsboard(data):
    """Send processed data to ThingsBoard and return detailed status"""
    try:
        url = f"{THINGSBOARD_URL}/api/v1/{DEVICE_ACCESS_TOKEN}/telemetry"
        
        headers = {
            "Content-Type": "application/json",
        }
        
        response = requests.post(url, headers=headers, json=data, timeout=10)
        
        if response.status_code in [200, 201]:
            print("Data successfully sent to ThingsBoard")
            return {
                "success": True,
                "status_code": response.status_code,
                "message": "Data sent successfully",
                "timestamp": datetime.utcnow().isoformat()
            }
        else:
            print(f"ThingsBoard error: {response.status_code} - {response.text}")
            return {
                "success": False,
                "status_code": response.status_code,
                "message": response.text,
                "timestamp": datetime.utcnow().isoformat()
            }
            
    except Exception as e:
        print(f"Error sending to ThingsBoard: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "message": "Network error connecting to ThingsBoard",
            "timestamp": datetime.utcnow().isoformat()
        }

def get_solar_meteo_data(latitude, longitude):
    """Get solar data from Open-Meteo API for the current location"""
    try:
        # Calculate time range (past 3 hours + current hour = 4 hours total)
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=3)
        
        # Make API request with solar-specific parameters
        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "hourly": [
                "cloud_cover",
                "shortwave_radiation",      # Global horizontal irradiance (GHI)
                "direct_radiation",         # Direct normal irradiance (DNI)
                "diffuse_radiation",        # Diffuse horizontal irradiance (DHI)
                "sunshine_duration",
                "is_day",
                "temperature_2m"
            ],
            "start_date": start_time.strftime("%Y-%m-%d"),
            "end_date": end_time.strftime("%Y-%m-%d"),
            "timezone": "auto"
        }
        
        responses = openmeteo.weather_api(url, params=params)
        response = responses[0]
        
        # Process hourly data
        hourly = response.Hourly()
        hourly_data = process_solar_data(hourly)
        
        # Get current hour data
        current_hour_data = get_current_hour_data(hourly_data)
        
        return {
            "location": {
                "latitude": latitude,
                "longitude": longitude,
                "name": response.Name() or "Unknown location",
                "elevation": response.Elevation(),
                "timezone": response.Timezone()
            },
            "current_hour": current_hour_data,
            "past_3_hours": hourly_data[:-1] if len(hourly_data) > 1 else [],
            "summary": calculate_solar_summary(hourly_data)
        }
        
    except Exception as e:
        print(f"Error fetching solar data: {str(e)}")
        return None

def process_solar_data(hourly):
    """Process hourly solar data"""
    hourly_data = []
    
    # Get all the data arrays
    cloud_cover = hourly.Variables(0).ValuesAsNumpy()
    shortwave_radiation = hourly.Variables(1).ValuesAsNumpy()  # GHI
    direct_radiation = hourly.Variables(2).ValuesAsNumpy()     # DNI
    diffuse_radiation = hourly.Variables(3).ValuesAsNumpy()    # DHI
    sunshine_duration = hourly.Variables(4).ValuesAsNumpy()
    is_day = hourly.Variables(5).ValuesAsNumpy()
    temperature = hourly.Variables(6).ValuesAsNumpy()
    
    # Get time data
    time_range = range(len(cloud_cover))
    base_time = hourly.Time()
    interval = hourly.Interval()
    
    for i in time_range:
        ghi = shortwave_radiation[i]
        lux_intensity = ghi * 120  # Convert to approximate lux
        
        # Calculate panel output (simplified)
        panel_output_w = calculate_panel_output(ghi, 0.18, 1.6, temperature[i])
        
        # Calculate irradiance factors
        irradiance_factors = calculate_irradiance_factors(ghi, direct_radiation[i], diffuse_radiation[i])
        
        hourly_time = (base_time + i * interval).DateTime()
        
        hourly_data.append({
            "timestamp": hourly_time.isoformat(),
            "hour": hourly_time.hour,
            "is_current_hour": is_current_hour(hourly_time),
            "cloud_cover_percentage": float(cloud_cover[i]),
            "solar_radiation": {
                "ghi_wm2": float(ghi),
                "dni_wm2": float(direct_radiation[i]),
                "dhi_wm2": float(diffuse_radiation[i]),
                "total_irradiance": float(ghi)
            },
            "lux_intensity_approx": float(lux_intensity),
            "sunshine_duration_seconds": float(sunshine_duration[i]),
            "is_day": bool(is_day[i]),
            "temperature_c": float(temperature[i]),
            "panel_performance": {
                "estimated_output_w": panel_output_w,
                "performance_ratio": min(1.0, ghi / 1000)
            },
            "irradiance_factors": irradiance_factors,
            "weather_condition": get_weather_condition(float(cloud_cover[i]), float(ghi), bool(is_day[i]))
        })
    
    return hourly_data

def is_current_hour(dt):
    """Check if the given datetime is the current hour"""
    now = datetime.utcnow()
    return dt.year == now.year and dt.month == now.month and dt.day == now.day and dt.hour == now.hour

def get_current_hour_data(hourly_data):
    """Extract data for the current hour"""
    for hour_data in hourly_data:
        if hour_data.get('is_current_hour', False):
            return hour_data
    return hourly_data[-1] if hourly_data else None

def calculate_panel_output(ghi, efficiency, area, temperature):
    """Calculate estimated solar panel output"""
    temp_coefficient = -0.004
    temp_difference = temperature - 25.0
    temp_factor = 1 + (temp_coefficient * temp_difference)
    return max(0, ghi * efficiency * area * temp_factor)

def calculate_irradiance_factors(ghi, dni, dhi):
    """Calculate various irradiance factors"""
    if ghi == 0:
        return {
            "clearness_index": 0,
            "diffuse_fraction": 0,
            "direct_fraction": 0,
            "irradiance_quality": "none"
        }
    
    clearness_index = ghi / 1361
    diffuse_fraction = dhi / ghi
    direct_fraction = dni / ghi if ghi > 0 else 0
    
    if clearness_index > 0.7:
        quality = "excellent"
    elif clearness_index > 0.5:
        quality = "good"
    elif clearness_index > 0.3:
        quality = "fair"
    else:
        quality = "poor"
    
    return {
        "clearness_index": float(clearness_index),
        "diffuse_fraction": float(diffuse_fraction),
        "direct_fraction": float(direct_fraction),
        "irradiance_quality": quality
    }

def get_weather_condition(cloud_cover, solar_rad, is_day):
    """Determine weather condition based on data"""
    if not is_day:
        return "night"
    elif cloud_cover < 10 and solar_rad > 600:
        return "clear_sky_optimal"
    elif cloud_cover < 30:
        return "mostly_clear"
    elif cloud_cover < 60:
        return "partly_cloudy"
    elif solar_rad > 200:
        return "cloudy_but_bright"
    else:
        return "overcast"

def calculate_solar_summary(hourly_data):
    """Calculate summary statistics for the period"""
    if not hourly_data:
        return {}
    
    total_energy = sum(hour['panel_performance']['estimated_output_w'] for hour in hourly_data) / 1000
    avg_ghi = np.mean([hour['solar_radiation']['ghi_wm2'] for hour in hourly_data])
    avg_cloud_cover = np.mean([hour['cloud_cover_percentage'] for hour in hourly_data])
    
    return {
        "total_energy_kwh": float(total_energy),
        "average_ghi_wm2": float(avg_ghi),
        "average_cloud_cover_percentage": float(avg_cloud_cover),
        "total_hours": len(hourly_data)
    }

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({"status": "healthy", "timestamp": datetime.utcnow().isoformat()})

@app.route('/solar-test', methods=['GET'])
def solar_test():
    """Test endpoint to check solar data functionality"""
    lat = request.args.get('lat', 40.7128, type=float)
    lon = request.args.get('lon', -74.0060, type=float)
    
    solar_data = get_solar_meteo_data(lat, lon)
    if solar_data:
        return jsonify(solar_data)
    else:
        return jsonify({"error": "Failed to get solar data"}), 500

@app.route('/thingsboard-test', methods=['GET'])
def thingsboard_test():
    """Test endpoint to check ThingsBoard connection"""
    test_data = {
        "ts": int(datetime.utcnow().timestamp() * 1000),
        "values": {
            "test_temperature": 25.5,
            "test_message": "Connection test from Flask server",
            "test_timestamp": datetime.utcnow().isoformat()
        }
    }
    
    result = send_to_thingsboard(test_data)
    return jsonify(result)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
