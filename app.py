# app.py
from flask import Flask, request, jsonify
import requests
import json
from datetime import datetime

app = Flask(__name__)

# ThingsBoard configuration - UPDATE THESE WITH YOUR CREDENTIALS
THINGSBOARD_URL = "https://your-thingsboard-instance.com"
DEVICE_ACCESS_TOKEN = "your_device_access_token_here"

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
        # Extract data sent from ESP32 - update these variable names to match your JSON structure
        device_id = esp_data.get("device_id", "unknown")
        temperature = esp_data.get("temperature", 0)      # Your temperature data
        humidity = esp_data.get("humidity", 0)            # Your humidity data
        pressure = esp_data.get("pressure", 0)            # Your pressure data
        sensor_value1 = esp_data.get("sensor1", 0)        # Your custom sensor 1
        sensor_value2 = esp_data.get("sensor2", 0)        # Your custom sensor 2
        # Add more variables here based on your ESP32 data structure
        
        ####################################################################
        # PROCESS YOUR DATA - ADD YOUR CUSTOM PROCESSING LOGIC HERE
        ####################################################################
        # Example processing - replace with your actual calculations
        processed_temp = temperature * 1.1  # Example adjustment
        avg_sensor = (sensor_value1 + sensor_value2) / 2  # Example calculation
        status = "NORMAL" if temperature < 30 else "WARNING"  # Example logic
        
        # Add your custom processing here
        # result_value1 = your_calculation(sensor_value1, sensor_value2)
        # result_value2 = another_calculation(temperature, humidity)
        
        ####################################################################
        # PREPARE DATA FOR THINGSBOARD - ADD YOUR RESULT VARIABLES HERE
        ####################################################################
        # Create the data structure to send to ThingsBoard
        thingsboard_data = {
            "ts": int(datetime.utcnow().timestamp() * 1000),  # Timestamp in milliseconds
            "values": {
                # Original values from ESP32
                "temperature": temperature,
                "humidity": humidity,
                "pressure": pressure,
                "sensor1": sensor_value1,
                "sensor2": sensor_value2,
                
                # Your processed values - ADD YOUR RESULT VARIABLES HERE
                "processed_temp": processed_temp,      # Add your result values
                "avg_sensor": avg_sensor,              # Add your result values
                "status": status,                      # Add your result values
                # "result1": result_value1,            # Add your result values
                # "result2": result_value2,            # Add your result values
            }
        }
        
        # Send processed data to ThingsBoard
        success = send_to_thingsboard(thingsboard_data)
        
        if success:
            return jsonify({
                "status": "success", 
                "message": "Data processed and sent to ThingsBoard",
                "processed_data": thingsboard_data
            }), 200
        else:
            return jsonify({"error": "Failed to send data to ThingsBoard"}), 500
            
    except Exception as e:
        print(f"Error processing data: {str(e)}")
        return jsonify({"error": str(e)}), 500

def send_to_thingsboard(data):
    """Send processed data to ThingsBoard"""
    try:
        url = f"{THINGSBOARD_URL}/api/v1/{DEVICE_ACCESS_TOKEN}/telemetry"
        
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        response = requests.post(url, headers=headers, json=data, timeout=10)
        
        if response.status_code in [200, 201]:
            print("Data successfully sent to ThingsBoard")
            return True
        else:
            print(f"ThingsBoard error: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        print(f"Error sending to ThingsBoard: {str(e)}")
        return False

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({"status": "healthy", "timestamp": datetime.utcnow().isoformat()})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
