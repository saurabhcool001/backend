import os, json, urllib.request
from dotenv import load_dotenv

load_dotenv()
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')

req = urllib.request.Request(f'{SUPABASE_URL}/rest/v1/patients?limit=5')
req.add_header('apikey', SUPABASE_KEY or '')
req.add_header('Authorization', f'Bearer {SUPABASE_KEY or ""}')

try:
    with urllib.request.urlopen(req) as response:
        data = json.loads(response.read().decode())
        print("Success!", len(data))
except Exception as e:
    print("Error:", e)
