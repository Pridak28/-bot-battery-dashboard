"""Test the corrected Gemini 2.5 Flash model"""

import requests

API_KEY = "AIzaSyChg3CIggWscPe9C1TcPu9UNBNC1Oozns0"
model_name = "gemini-2.5-flash"
endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent"

print("Testing Gemini 2.5 Flash...\n")
print(f"Model: {model_name}")
print(f"Endpoint: {endpoint}\n")

payload = {
    "contents": [{
        "parts": [{
            "text": "What is the capital of France? Reply in one word."
        }]
    }],
    "generationConfig": {
        "temperature": 0.1,
        "maxOutputTokens": 50,
    }
}

try:
    response = requests.post(
        f"{endpoint}?key={API_KEY}",
        json=payload,
        timeout=10
    )

    if response.status_code == 200:
        data = response.json()
        text = data['candidates'][0]['content']['parts'][0]['text']
        print(f"✅ SUCCESS!")
        print(f"Response: {text.strip()}")
        print(f"\n🎉 Your Gemini API is now working with model: {model_name}")
    else:
        print(f"❌ Failed: Status {response.status_code}")
        print(f"Response: {response.text}")
except Exception as e:
    print(f"❌ Exception: {str(e)}")