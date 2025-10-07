"""Test Google Gemini API connection with corrected model name"""

import os
import requests
import json

# Your API key (from the error URL you provided)
API_KEY = "AIzaSyChg3CIggWscPe9C1TcPu9UNBNC1Oozns0"

# Test different model names
model_names = [
    "gemini-1.5-flash-latest",
    "gemini-1.5-pro-latest",
    "gemini-pro",
    "gemini-1.5-flash"  # This one should fail with 404
]

print("Testing Google Gemini API endpoints...\n")

for model_name in model_names:
    endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent"

    payload = {
        "contents": [{
            "parts": [{
                "text": "What is 2+2? Reply with just the number."
            }]
        }],
        "generationConfig": {
            "temperature": 0.1,
            "maxOutputTokens": 10,
        }
    }

    try:
        print(f"Testing model: {model_name}")
        response = requests.post(
            f"{endpoint}?key={API_KEY}",
            json=payload,
            timeout=10
        )

        if response.status_code == 200:
            data = response.json()
            text = data['candidates'][0]['content']['parts'][0]['text']
            print(f"✅ SUCCESS: {model_name} - Response: {text.strip()}")
        else:
            print(f"❌ FAILED: {model_name} - Status: {response.status_code}")
            if response.status_code == 404:
                print(f"   Error: Model '{model_name}' not found")
            else:
                print(f"   Error: {response.text[:200]}")
    except Exception as e:
        print(f"❌ EXCEPTION: {model_name} - {str(e)}")

    print()

print("\n" + "="*60)
print("RECOMMENDATION: Use 'gemini-1.5-flash-latest' or 'gemini-pro'")
print("="*60)