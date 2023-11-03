import requests

url = 'https://app.coqui.ai/api/v2/samples/xtts'
headers = {'Authorization': 'Bearer ', 'accept': 'audio/wav'}

data = {
    "voice_id": "c791b5b5-0558-42b8-bb0b-602ac5efc0b9",
    "text": "Hello",
    "language": "en"
}

response = requests.post(url, headers=headers, json=data)

# Check the response
if response.status_code == 200:
    print("Request was successful")
    print(response.json())
else:
    print("Request failed with status code:", response.status_code)
    print(response.text)
