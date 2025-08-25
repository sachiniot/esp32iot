from flask import Flask, request, jsonify
import requests
from datetime import datetime
import json
import tensorflow as tf
import numpy as np
from PIL import Image
import io
import base64
import os

app = Flask(__name__)

# ===== CONFIGURATION =====
THINGSBOARD_HOST = "demo.thingsboard.io"  # or "thingsboard.cloud"
ACCESS_TOKEN = "5VRotByuBcKD82t1PB8i"    # Your device access token

# ===== PLANT DISEASE MODEL CONFIGURATION =====
# Load the TFLite model and labels when the server starts
try:
    print("🤖 Loading AI Model...")
    interpreter = tf.lite.Interpreter(model_path="plant_disease_model.tflite")
    interpreter.allocate_tensors()
    input_details = interpreter.get_input_details()
    output_details = interpreter.get_output_details()
    print("✅ AI Model Loaded Successfully!")
    
    # Load disease labels and their cures
    with open("disease_cures.json", "r") as f:
        disease_database = json.load(f)
    print("✅ Disease Database Loaded!")
    
except Exception as e:
    print(f"❌ Failed to load AI model: {e}")
    interpreter = None
    disease_database = {}

def predict_disease(image_bytes):
    """Predict disease from image bytes using TensorFlow Lite"""
    if interpreter is None:
        return "Model not loaded", 0.0, "Please check server logs"
    
    try:
        # 1. Open and preprocess the image
        image = Image.open(io.BytesIO(image_bytes)).convert('RGB')
        
        # 2. Get model input size and resize image
        input_shape = input_details[0]['shape']
        height, width = input_shape[1], input_shape[2]
        image = image.resize((width, height))
        
        # 3. Convert to numpy array and normalize
        input_data = np.array(image, dtype=np.float32) / 255.0
        input_data = np.expand_dims(input_data, axis=0)  # Add batch dimension

        # 4. Run inference
        interpreter.set_tensor(input_details[0]['index'], input_data)
        interpreter.invoke()
        output_data = interpreter.get_tensor(output_details[0]['index'])
        
        # 5. Process results
        predictions = np.squeeze(output_data)
        predicted_idx = np.argmax(predictions)
        confidence = float(predictions[predicted_idx])
        
        # 6. Get disease name from database (assuming labels are keys)
        disease_names = list(disease_database.keys())
        if predicted_idx < len(disease_names):
            disease_name = disease_names[predicted_idx]
        else:
            disease_name = f"Unknown_Disease_{predicted_idx}"
            
        return disease_name, confidence, disease_database.get(disease_name, {}).get("cure", "No cure information available")
        
    except Exception as e:
        return f"Prediction error: {str(e)}", 0.0, ""

@app.route('/esp32-data', methods=['POST'])
def receive_esp32_data():
    try:
        # Get data from ESP32
        esp32_data = request.get_json()
        print("📥 Received from ESP32:", {k: v for k, v in esp32_data.items() if k != 'image'})  # Don't print full image
        
        # Check if image data is present
        if 'image' not in esp32_data:
            return jsonify({"status": "error", "message": "No image data received"}), 400
        
        # Extract and decode the image
        image_base64 = esp32_data['image']
        image_bytes = base64.b64decode(image_base64)
        print(f"📸 Decoded image: {len(image_bytes)} bytes")
        
        # Predict disease
        disease_name, confidence, cure_advice = predict_disease(image_bytes)
        print(f"🔍 Prediction: {disease_name} ({confidence:.2%})")
        
        # Prepare comprehensive data for ThingsBoard
        thingsboard_data = {
            # Original sensor data
            "temperature": esp32_data.get('temperature', 0),
            "humidity": esp32_data.get('humidity', 0),
            "sensor_id": esp32_data.get('sensor_id', 'unknown'),
            "timestamp": esp32_data.get('timestamp', 0),
            
            # Disease prediction results
            "disease_detected": disease_name,
            "confidence": confidence,
            "cure_advice": cure_advice,
            "is_healthy": "healthy" in disease_name.lower(),
            
            # Metadata
            "processed_at": datetime.now().isoformat(),
            "server": "render-cloud",
            "ai_model": "tensorflow_lite"
        }
        
        print("📤 Sending to ThingsBoard:", {k: v for k, v in thingsboard_data.items() if k != 'cure_advice'})
        
        # Send to ThingsBoard
        url = f"https://{THINGSBOARD_HOST}/api/v1/{ACCESS_TOKEN}/telemetry"
        response = requests.post(url, json=thingsboard_data, timeout=10)
        
        print(f"📡 ThingsBoard response status: {response.status_code}")
        
        if response.status_code == 200:
            print("✅ Successfully sent to ThingsBoard!")
            return jsonify({
                "status": "success", 
                "message": "Data sent to ThingsBoard",
                "prediction": {
                    "disease": disease_name,
                    "confidence": confidence,
                    "cure": cure_advice
                }
            })
        else:
            print(f"❌ FAILED to send to ThingsBoard: {response.status_code}")
            return jsonify({
                "status": "error", 
                "code": response.status_code,
                "message": response.text
            }), 500
            
    except Exception as e:
        print(f"❌ Exception: {e}")
        return jsonify({"status": "error", "message": str(e)}), 400

@app.route('/test-model', methods=['GET'])
def test_model():
    """Test endpoint to check if model is working"""
    try:
        # Create a simple test image (red square)
        test_image = Image.new('RGB', (224, 224), color='red')
        img_byte_arr = io.BytesIO()
        test_image.save(img_byte_arr, format='JPEG')
        img_byte_arr = img_byte_arr.getvalue()
        
        disease, confidence, cure = predict_disease(img_byte_arr)
        
        return jsonify({
            "status": "success",
            "model_loaded": interpreter is not None,
            "test_prediction": {
                "disease": disease,
                "confidence": confidence,
                "cure": cure
            }
        })
        
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/')
def home():
    return jsonify({
        "message": "ESP32 to ThingsBoard Bridge with AI Disease Detection",
        "status": "ready",
        "endpoints": {
            "main": "POST /esp32-data",
            "test_connection": "GET /test-thingsboard",
            "test_model": "GET /test-model"
        },
        "model_loaded": interpreter is not None
    })

if __name__ == '__main__':
    print("🚀 Server started with AI Disease Detection!")
    print("📡 Send POST requests to /esp32-data with image data")
    print("🤖 AI Model status:", "Loaded" if interpreter else "Not loaded")
    app.run(debug=True)
