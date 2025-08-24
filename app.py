from flask import Flask, request, jsonify
import requests
from datetime import datetime

app = Flask(__name__)

# Configuration
THINGSBOARD_HOST = "demo.thingsboard.io"
ACCESS_TOKEN = "ZvxA9pfG0GtBiIZZJelX"  # Your access token

@app.route('/esp32-data', methods=['POST'])
def receive_esp32_data():
    try:
        # Get JSON data from ESP32
        data = request.get_json()
        print("📥 Received from ESP32:", data)
        
        # Add timestamp and process
        processed_data = {
            "original_data": data,
            "processed_at": datetime.now().isoformat(),
            "status": "success"
        }
        
        # Send to ThingsBoard
        url = f"https://{THINGSBOARD_HOST}/api/v1/{ACCESS_TOKEN}/telemetry"
        response = requests.post(url, json=processed_data)
        
        if response.status_code == 200:
            print("✅ Sent to ThingsBoard")
            return jsonify({"status": "success"})
        else:
            print("❌ Failed to send to ThingsBoard")
            return jsonify({"status": "error"}), 500
            
    except Exception as e:
        print("❌ Error:", e)
        return jsonify({"status": "error", "message": str(e)}), 400

@app.route('/')
def home():
    return jsonify({
        "message": "ESP32 to ThingsBoard Bridge",
        "status": "ready",
        "endpoint": "POST /esp32-data"
    })

if __name__ == '__main__':
    print("🚀 Server started! Send POST requests to /esp32-data")
    app.run(debug=True)