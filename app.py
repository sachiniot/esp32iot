from flask import Flask, request, jsonify
import requests
from datetime import datetime
import json

app = Flask(__name__)

# ===== CONFIGURATION =====
THINGSBOARD_HOST = "demo.thingsboard.io"  # or "thingsboard.cloud"
ACCESS_TOKEN = "5VRotByuBcKD82t1PB8i"    # Your device access token

@app.route('/esp32-data', methods=['POST'])
def receive_esp32_data():
    try:
        # Get data from ESP32
        esp32_data = request.get_json()
        print("📥 Received from ESP32:", esp32_data)
        
        # Prepare data for ThingsBoard (SIMPLIFIED - send raw data directly)
        # ThingsBoard expects the actual telemetry values, not nested objects
        thingsboard_data = {
            # Send ESP32 data directly as telemetry
            "temperature": esp32_data.get('temperature', 0),
            "humidity": esp32_data.get('humidity', 0),
            "sensor_id": esp32_data.get('sensor_id', 'unknown'),
            "timestamp": esp32_data.get('timestamp', 0),
            # Add metadata
            "processed_at": datetime.now().isoformat(),
            "server": "render-cloud"
        }
        
        print("📤 Sending to ThingsBoard:", thingsboard_data)
        
        # Send to ThingsBoard
        url = f"https://{THINGSBOARD_HOST}/api/v1/{ACCESS_TOKEN}/telemetry"
        print(f"🌐 Sending to URL: {url}")
        
        response = requests.post(url, json=thingsboard_data, timeout=10)
        
        print(f"📡 ThingsBoard response status: {response.status_code}")
        print(f"📡 ThingsBoard response text: {response.text}")
        
        if response.status_code == 200:
            print("✅ Successfully sent to ThingsBoard!")
            return jsonify({"status": "success", "message": "Data sent to ThingsBoard"})
        else:
            print(f"❌ FAILED to send to ThingsBoard: {response.status_code}")
            print(f"❌ Error details: {response.text}")
            return jsonify({
                "status": "error", 
                "code": response.status_code,
                "message": response.text
            }), 500
            
    except Exception as e:
        print(f"❌ Exception: {e}")
        return jsonify({"status": "error", "message": str(e)}), 400

@app.route('/test-thingsboard', methods=['GET'])
def test_thingsboard():
    """Test endpoint to check ThingsBoard connection"""
    try:
        test_data = {
            "test_value": 42,
            "test_message": "connection_test",
            "timestamp": datetime.now().isoformat()
        }
        
        url = f"https://{THINGSBOARD_HOST}/api/v1/{ACCESS_TOKEN}/telemetry"
        response = requests.post(url, json=test_data, timeout=10)
        
        return jsonify({
            "status": "success" if response.status_code == 200 else "error",
            "thingsboard_status": response.status_code,
            "response": response.text,
            "test_data": test_data
        })
        
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/')
def home():
    return jsonify({
        "message": "ESP32 to ThingsBoard Bridge",
        "status": "ready",
        "endpoint": "POST /esp32-data",
        "test_endpoint": "GET /test-thingsboard"
    })

if __name__ == '__main__':
    print("🚀 Server started!")
    print("📡 Send POST requests to /esp32-data")
    print("🧪 Test ThingsBoard connection: GET /test-thingsboard")
    app.run(debug=True)

