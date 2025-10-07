"""Test correct Google Gemini API endpoint format"""

import os
import requests
import json

API_KEY = "AIzaSyChg3CIggWscPe9C1TcPu9UNBNC1Oozns0"

# Try the correct endpoint format with "models/" prefix
model_variations = [
    "models/gemini-pro",
    "models/gemini-1.5-flash",
    "models/gemini-1.5-flash-latest",
    "models/gemini-1.5-pro",
    "models/gemini-1.5-pro-latest",
    "gemini-pro-vision",
]

print("Testing Google Gemini API with correct endpoint format...\n")

for model in model_variations:
    # If model doesn't start with "models/", add it
    model_path = model if model.startswith("models/") else f"models/{model}"

    endpoint = f"https://generativelanguage.googleapis.com/v1beta/{model_path}:generateContent"

    payload = {
        "contents": [{
            "parts": [{
                "text": "Reply with just: OK"
            }]
        }],
        "generationConfig": {
            "temperature": 0.1,
            "maxOutputTokens": 10,
        }
    }

    try:
        print(f"Testing: {model_path}")
        print(f"URL: {endpoint}?key=***")

        response = requests.post(
            f"{endpoint}?key={API_KEY}",
            json=payload,
            timeout=10
        )

        if response.status_code == 200:
            data = response.json()
            text = data['candidates'][0]['content']['parts'][0]['text']
            print(f"✅ SUCCESS: Response: {text.strip()}")
        elif response.status_code == 404:
            print(f"❌ 404 NOT FOUND")
        elif response.status_code == 400:
            error_msg = response.json().get('error', {}).get('message', 'Unknown error')
            print(f"❌ 400 BAD REQUEST: {error_msg[:100]}")
        elif response.status_code == 403:
            print(f"❌ 403 FORBIDDEN: API key may be invalid or restricted")
        else:
            print(f"❌ Status {response.status_code}: {response.text[:100]}")
    except Exception as e:
        print(f"❌ EXCEPTION: {str(e)[:100]}")

    print("-" * 40)

# Also test the list models endpoint to see what's available
print("\n\nTesting list models endpoint...")
try:
    list_endpoint = f"https://generativelanguage.googleapis.com/v1beta/models?key={API_KEY}"
    response = requests.get(list_endpoint, timeout=10)

    if response.status_code == 200:
        data = response.json()
        models = data.get('models', [])
        print(f"✅ Available models:")
        for model in models[:5]:  # Show first 5
            print(f"   - {model.get('name', 'Unknown')}")
    else:
        print(f"❌ Failed to list models: Status {response.status_code}")
except Exception as e:
    print(f"❌ Exception listing models: {str(e)}")