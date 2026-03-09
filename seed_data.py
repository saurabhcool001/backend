import os, json, httpx
from dotenv import load_dotenv

load_dotenv()
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')

headers={'apikey': SUPABASE_KEY, 'Authorization': f'Bearer {SUPABASE_KEY}', 'Content-Type': 'application/json'}

# 1. Fetch patient ID to use
patients_res = httpx.get(f'{SUPABASE_URL}/rest/v1/patients?limit=1', headers=headers)
actual_patient_id = patients_res.json()[0]['id']
print(f"Using patient ID: {actual_patient_id}")

# 2. Insert mock checkin
checkin_data = {
    "patient_id": actual_patient_id,
    "pain_score": 6,
    "pain_location": "knee",
    "swelling": "same",
    "wound_status": "dry",
    "temperature_feeling": "fine",
    "mobility": "same",
    "mood_score": 3,
    "escalation_level": "AMBER",
    "flags": ["MODERATE_PAIN"]
}
httpx.post(f'{SUPABASE_URL}/rest/v1/checkins', headers=headers, json=checkin_data)

# 3. Insert mock exercises
e1_data = {
    "patient_id": actual_patient_id,
    "exercise_name": "Heel Slides",
    "reps_completed": 10,
    "sets_completed": 3,
    "pain_during": 5
}
e2_data = {
    "patient_id": actual_patient_id,
    "exercise_name": "Quad Sets",
    "reps_completed": 10,
    "sets_completed": 3,
    "pain_during": 4
}
httpx.post(f'{SUPABASE_URL}/rest/v1/exercise_logs', headers=headers, json=e1_data)
httpx.post(f'{SUPABASE_URL}/rest/v1/exercise_logs', headers=headers, json=e2_data)

# 4. Insert mock medications
m1_data = {
    "patient_id": actual_patient_id,
    "medication_name": "Rivaroxaban 10mg",
    "dose_time": "08:00",
    "taken": True
}
m2_data = {
    "patient_id": actual_patient_id,
    "medication_name": "Paracetamol 1g",
    "dose_time": "14:00",
    "taken": True
}
m3_data = {
    "patient_id": actual_patient_id,
    "medication_name": "Naproxen 500mg",
    "dose_time": "20:00",
    "taken": True
}
httpx.post(f'{SUPABASE_URL}/rest/v1/medication_logs', headers=headers, json=m1_data)
httpx.post(f'{SUPABASE_URL}/rest/v1/medication_logs', headers=headers, json=m2_data)
httpx.post(f'{SUPABASE_URL}/rest/v1/medication_logs', headers=headers, json=m3_data)

print("Mock data seeded successfully!")
