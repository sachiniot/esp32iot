# Weather API Server

A Python server that fetches weather data from external APIs and returns JSON format.

## Setup

1. Add your weather API key as environment variable in Render:
   - `WEATHER_API_KEY=your_actual_api_key`

2. The server will automatically deploy

## API Endpoints

- `GET /` - Check server status
- `GET /weather/{city}` - Get weather by city name
- `GET /weather?lat={latitude}&lon={longitude}` - Get weather by coordinates

## Example Usage

```bash
curl https://your-app.onrender.com/weather/London
