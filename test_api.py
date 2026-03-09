import os, httpx, json
from dotenv import load_dotenv

load_dotenv()
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')

headers={'apikey': SUPABASE_KEY, 'Authorization': f'Bearer {SUPABASE_KEY}'}

def get_data(table_name):
    r = httpx.get(f'{SUPABASE_URL}/rest/v1/{table_name}?limit=5', headers=headers)
    return r.json() if r.status_code == 200 else [{"error": r.text}]

with open('db_output.txt', 'w') as f:
    f.write("--- PATIENTS ---\n")
    f.write(json.dumps(get_data("patients"), indent=2) + "\n")
    
    f.write("\n--- CHECKINS ---\n")
    f.write(json.dumps(get_data("checkins"), indent=2) + "\n")
    
    f.write("\n--- EXERCISE LOGS ---\n")
    f.write(json.dumps(get_data("exercise_logs"), indent=2) + "\n")
    
    f.write("\n--- MEDICATION LOGS ---\n")
    f.write(json.dumps(get_data("medication_logs"), indent=2) + "\n")
    
    f.write("\n--- ALERTS ---\n")
    f.write(json.dumps(get_data("alerts"), indent=2) + "\n")
