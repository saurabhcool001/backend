import os
import json
from datetime import datetime
from typing import List, Optional, Dict, Any

from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

try:
    from supabase import create_client, Client
except ImportError:
    create_client = None
    Client = None
    print("WARNING: supabase package not installed. DB operations will be mocked.")

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    print("WARNING: python-dotenv not installed. Reading env vars from system only.")

try:
    import anthropic
except Exception as e:
    anthropic = None
    print(f"WARNING: anthropic import failed: {e}")

# ---------------------------------------------------------
# Configuration & Setup
# ---------------------------------------------------------

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://xivnxfgtomiizbftzkwl.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Inhpdm54Zmd0b21paXpiZnR6a3dsIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzI5ODczODUsImV4cCI6MjA4ODU2MzM4NX0.rTBPmD1qck6GPS3YDtWKpe3cTJBYE1iho1x_MXVYSmc")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "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")

# Initialize Supabase Client if keys exist (mock safely if not)
supabase = None
if SUPABASE_URL and SUPABASE_KEY and create_client:
    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        print("INFO: Supabase connected OK.")
    except Exception as e:
        print(f"WARNING: Supabase init failed: {e}")
        supabase = None
else:
    print("WARNING: Supabase credentials not found or module missing. DB operations will fail.")

# Initialize Anthropic Client
claude = None
if ANTHROPIC_API_KEY and anthropic:
    try:
        claude = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        print("INFO: Anthropic client initialized OK.")
    except Exception as e:
        print(f"WARNING: Anthropic init failed: {e}")
        claude = None
else:
    print("WARNING: Anthropic credentials not found or module missing. AI features will fallback.")

app = FastAPI(title="KneeGuide API", version="1.0.0")

# Allow mobile app and local dashboard
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------
# Pydantic Schemas
# ---------------------------------------------------------
class CheckinRequest(BaseModel):
    patient_id: str
    pain_score: int
    pain_location: str
    swelling: str
    wound_status: str
    temperature_feeling: str
    mobility: str
    mood_score: Optional[int] = None

class ExerciseProgressRequest(BaseModel):
    patient_id: str
    exercises: List[dict]

class MedicationLogRequest(BaseModel):
    patient_id: str
    medication_name: str
    time: str
    taken: bool

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    patient_id: str
    message: str
    history: List[ChatMessage] = []

class CoachRequest(BaseModel):
    exercise_name: str
    current_angle: int
    target_angle: int
    current_rep: int
    total_reps: int
    current_set: int
    total_sets: int
    pain_scores: List[int] = []
    days_post_op: int = 7
    phase: str = "exercising"  # exercising, resting, completed

# ---------------------------------------------------------
# Escalation Engine Logic (Server-Side)
# ---------------------------------------------------------
def calculate_escalation(data: dict) -> dict:
    """
    Evaluates check-in symptoms against clinical rules.
    Outputs the severity level (GREEN, AMBER, RED, CRITICAL),
    flags the specific concern, and defines actions.
    """
    level = "GREEN"
    flags = []
    actions = []

    # CRITICAL Conditions
    if data.get('pain_location') == 'calf' and data.get('swelling') in ['more', 'much_more']:
        level = "CRITICAL"
        flags.append("POSSIBLE_DVT")
        actions.append("Call 999 immediately - Possible blood clot")
    
    if data.get('temperature_feeling') == 'feverish' and data.get('wound_status') in ['wet', 'discharge']:
        level = "CRITICAL"
        flags.append("POSSIBLE_INFECTION")
        if "Call 999 immediately" not in actions[0] if actions else "":
            actions.append("Call 999 immediately or go to A&E")

    # RED Conditions (Elevate if lower)
    if level != "CRITICAL":
        if data.get('pain_score', 0) >= 8:
            level = "RED"
            flags.append("HIGH_PAIN")
            actions.append("Contact GP or 111 today for pain management")
        
        if data.get('temperature_feeling') == 'feverish':
            level = "RED"
            flags.append("FEVER")
            actions.append("Contact GP today")

        if data.get('wound_status') in ['wet', 'discharge']:
            level = "RED"
            flags.append("WOUND_CONCERN")
            actions.append("Contact Community Nurse or GP today")

    # AMBER Conditions
    if level == "GREEN":
        if 6 <= data.get('pain_score', 0) <= 7:
            level = "AMBER"
            flags.append("MODERATE_PAIN")
            actions.append("Rest, elevate your leg, and ensure painkillers are taken")
        
        if data.get('swelling') == 'much_more':
            level = "AMBER"
            flags.append("INCREASED_SWELLING")
            actions.append("Elevate leg above heart level, reduce walking today")
            
        if data.get('mobility') == 'worse':
            level = "AMBER"
            flags.append("REDUCED_MOBILITY")
            actions.append("Take it easy today, prioritize resting over exercises")

    # GREEN Fallback
    if level == "GREEN":
        actions.append("Continue current recovery plan. Great job!")

    return {
        "level": level,
        "flags": flags,
        "actions": actions
    }


# ---------------------------------------------------------
# API Endpoints
# ---------------------------------------------------------

@app.get("/health")
def health_check():
    return {"status": "ok", "timestamp": datetime.now().isoformat()}

@app.get("/api/patient/{patient_id}")
async def get_patient_info(patient_id: str):
    if not supabase:
        return {"id": patient_id, "name": "System Unavailable", "surgery_date": "2023-10-01", "days_post_op": 1}
        
    try:
        res = supabase.table("patients").select("*").eq("id", patient_id).execute()
        if not res.data:
            # Create a mock patient if missing to prevent UI crash
            mock_patient = {
                "id": patient_id,
                "name": f"Patient {str(patient_id)[:4]}",
                "surgery_date": datetime.now().isoformat(),
                "phone": "+441234567890",
                "address": "123 Knee Way"
            }
            supabase.table("patients").insert(mock_patient).execute()
            return mock_patient
        return res.data[0]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/checkin")
async def process_checkin(request: CheckinRequest):
    """
    Process daily check-in, calculate escalation, ask Claude to generate
    patient-friendly advice, and store in Supabase.
    """
    escalation = calculate_escalation(request.dict())
    
    # Generate AI Feedback
    ai_message = ""
    if claude:
        prompt = f"""
        You are 'KneeGuide', an empathetic AI assistant for patients recovering from Knee Replacement surgery.
        Based on this daily checkin data, write a short, warm, 2-3 sentence response directly to the patient.
        
        Pain Score: {request.pain_score}/10
        Pain Location: {request.pain_location}
        Swelling: {request.swelling}
        Mood: {request.mood_score}/5
        
        Escalation Level calculated by our rules engine: {escalation['level']}
        Actions recommended: {', '.join(escalation['actions'])}
        
        If it's GREEN, be encouraging. If it's AMBER, be cautious and remind them to rest.
        If it's RED or CRITICAL, be firm but calm, telling them they must follow the recommended actions.
        """
        try:
            message = claude.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=200,
                temperature=0.3,
                messages=[{"role": "user", "content": prompt}]
            )
            ai_message = message.content[0].text
        except Exception as e:
            print(f"Claude error: {e}")
            ai_message = "Your check-in has been recorded. Please follow the actions listed below."
    else:
        ai_message = "Your check-in has been logged successfully based on offline rules."

    # Store in database
    if supabase:
        try:
            payload = {
                "patient_id": request.patient_id,
                "pain_score": request.pain_score,
                "pain_location": request.pain_location,
                "swelling": request.swelling,
                "wound_status": request.wound_status,
                "temperature": request.temperature_feeling,
                "mobility": request.mobility,
                "mood_score": request.mood_score,
                "escalation_level": escalation['level'],
                "flags": escalation['flags'],
                "actions": escalation['actions'],
                "ai_summary": ai_message,
                "created_at": datetime.now().isoformat()
            }
            supabase.table("daily_checkins").insert(payload).execute()
            
            # If Red/Critical, dispatch caregiver alert
            if escalation['level'] in ['RED', 'CRITICAL']:
                alert_payload = {
                    "patient_id": request.patient_id,
                    "level": escalation['level'],
                    "message": f"Elevated symptom flag: {', '.join(escalation['flags'])}",
                    "status": "unresolved"
                }
                supabase.table("caregiver_alerts").insert(alert_payload).execute()
                
        except Exception as e:
            print(f"Supabase write error: {e}")

    return {
        "status": "success",
        "escalation": escalation,
        "ai_message": ai_message
    }

@app.post("/api/exercises/progress")
async def sync_exercises(request: ExerciseProgressRequest):
    """Saves daily exercise completion state"""
    if not supabase: return {"status": "mock_success"}
    
    try:
        # Instead of parsing the exact nested JSON list each time,
        # we will just store a raw log to a new table or overwrite a `completed_exercises` 
        # column in a status table. Here we write a general activity log:
        for ex in request.exercises:
            if ex.get('completed', False):
                supabase.table("activity_logs").insert({
                    "patient_id": request.patient_id,
                    "activity_type": "exercise",
                    "details": ex.get('name', 'Unknown')
                }).execute()
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/medications/log")
async def log_medication(request: MedicationLogRequest):
    """Logs when a patient checks off a drug"""
    if not supabase: return {"status": "mock_success"}
    try:
        payload = {
            "patient_id": request.patient_id,
            "medication_name": request.medication_name,
            "time": request.time,
            "taken": request.taken,
            "timestamp": datetime.now().isoformat()
        }
        supabase.table("medication_logs").insert(payload).execute()
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/chat")
async def chat_interaction(request: ChatRequest):
    """
    AI chat using Google Gemini API (via built-in urllib, no pip install needed).
    Falls back to smart hardcoded responses if no API key or if Gemini fails.
    """
    import urllib.request
    import urllib.error
    import ssl
    
    GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "AIzaSyCJRyadIFd5juCD8Um2izWLwTMvsF5eitY")
    
    system_prompt = (
        "You are KneeGuide, a warm and helpful AI assistant for a patient recovering from Knee Replacement surgery. "
        "Give practical advice about recovery (RICE method, exercises, medication timing, wound care). "
        "Be concise (2-3 sentences). Do NOT provide medical diagnoses. "
        "If the patient mentions severe pain, bleeding, fever, or chest pain, tell them to call 999 or 111 immediately "
        "and include the exact phrase URGENT_MEDICAL_ATTENTION in your response."
    )
    
    # Build conversation for Gemini
    gemini_contents = []
    for msg in request.history:
        role = "user" if msg.role == "user" else "model"
        gemini_contents.append({"role": role, "parts": [{"text": msg.content}]})
    gemini_contents.append({"role": "user", "parts": [{"text": request.message}]})
    
    reply_text = ""
    
    if GEMINI_API_KEY:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"
            
            payload = json.dumps({
                "system_instruction": {"parts": [{"text": system_prompt}]},
                "contents": gemini_contents,
                "generationConfig": {
                    "temperature": 0.3,
                    "maxOutputTokens": 300
                }
            }).encode("utf-8")
            
            # Create SSL context that doesn't verify (workaround for broken SSL on this machine)
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            
            req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
            with urllib.request.urlopen(req, context=ctx, timeout=15) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                reply_text = result["candidates"][0]["content"]["parts"][0]["text"]
                print(f"Gemini OK: {reply_text[:80]}...")
                
        except Exception as e:
            print(f"Gemini API error: {e}")
            reply_text = ""
    
    # Try Anthropic as second fallback
    if not reply_text and claude:
        try:
            anthropic_msgs = [{"role": m.role, "content": m.content} for m in request.history if m.role in ['user', 'assistant']]
            anthropic_msgs.append({"role": "user", "content": request.message})
            response = claude.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=300,
                system=system_prompt,
                messages=anthropic_msgs
            )
            reply_text = response.content[0].text
        except Exception as e:
            print(f"Anthropic API error: {e}")
            reply_text = ""
    
    # Smart hardcoded fallback
    if not reply_text:
        msg_lower = request.message.lower()
        if any(w in msg_lower for w in ['pain', 'hurt', 'ache', 'sore']):
            reply_text = "Pain after knee replacement is normal in the first few weeks. Use the RICE method: Rest, Ice (20 mins on/off), Compression, and Elevation above heart level. Take your prescribed painkillers on schedule. If pain is above 8/10 or in your calf, please contact your GP or call 111."
        elif any(w in msg_lower for w in ['swelling', 'swollen', 'swell']):
            reply_text = "Some swelling is completely normal for 3-6 months after surgery. Elevate your leg above heart level, apply ice for 20 minutes at a time, and do your ankle pump exercises regularly. If swelling suddenly worsens or your calf becomes very painful, call 111."
        elif any(w in msg_lower for w in ['exercise', 'walk', 'move', 'physio']):
            reply_text = "Gentle exercises are key to recovery! Start with ankle pumps and straight leg raises. Walk short distances with your frame or crutches. Increase gradually each day. Stop if pain rises above 7/10 — never push through sharp pain."
        elif any(w in msg_lower for w in ['wound', 'scar', 'dressing', 'stitches']):
            reply_text = "Keep your wound clean and dry. Change dressings as instructed by your nurse. Look out for redness spreading, pus, or increasing warmth — these could be signs of infection. If concerned, contact your community nurse or GP."
        elif any(w in msg_lower for w in ['sleep', 'night', 'bed']):
            reply_text = "Sleeping can be tricky after knee surgery. Try sleeping on your back with a pillow under your knee, or on your side with a pillow between your knees. Take your evening painkillers 30 minutes before bed. Avoid caffeine after 2pm."
        elif any(w in msg_lower for w in ['medication', 'medicine', 'pill', 'tablet', 'drug']):
            reply_text = "Take all prescribed medications on schedule — especially blood thinners and painkillers. Set alarms if needed. Don't skip doses of blood-thinning medication as it prevents clots. If you experience side effects, contact your GP."
        elif any(w in msg_lower for w in ['fever', 'temperature', 'hot', 'cold', 'shiver']):
            reply_text = "A temperature above 38°C after surgery could signal an infection. URGENT_MEDICAL_ATTENTION Please call 111 or your GP immediately. Keep hydrated and monitor your temperature regularly."
        elif any(w in msg_lower for w in ['drive', 'car', 'driving']):
            reply_text = "Most patients can drive again 6-8 weeks after surgery, once you can perform an emergency stop safely. Your surgeon will advise you. Don't drive while taking strong painkillers like codeine or tramadol."
        elif any(w in msg_lower for w in ['hello', 'hi', 'hey', 'how are']):
            reply_text = "Hello! I'm here to help with your knee recovery. You can ask me about pain management, exercises, wound care, medications, or anything else about your recovery. How are you feeling today?"
        else:
            reply_text = "Thank you for your question! For the best advice about your knee recovery, I recommend discussing specific concerns with your physiotherapist or GP. In the meantime, remember to keep up with your exercises, take medications on time, and rest with your leg elevated. Is there something specific about your recovery I can help with?"
    
    is_escalated = "URGENT_MEDICAL_ATTENTION" in reply_text
    clean_reply = reply_text.replace("URGENT_MEDICAL_ATTENTION", "").strip()
    
    return {
        "reply": clean_reply,
        "escalation_detected": is_escalated
    }

@app.post("/api/exercise/coach")
async def exercise_coach(request: CoachRequest):
    """
    AI exercise coaching using Gemini. Returns short, actionable tips
    based on current exercise state (angle, reps, pain).
    """
    import urllib.request
    import urllib.error
    import ssl

    GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "AIzaSyCJRyadIFd5juCD8Um2izWLwTMvsF5eitY")

    angle_diff = request.target_angle - request.current_angle
    avg_pain = round(sum(request.pain_scores) / len(request.pain_scores), 1) if request.pain_scores else 0

    system_prompt = (
        "You are an expert physiotherapy AI coach for a patient recovering from Knee Replacement surgery. "
        "You are watching them exercise in real-time via AR camera. "
        "Give exactly ONE short coaching tip (max 12 words). Be encouraging, specific, and practical. "
        "Do NOT use medical jargon. Do NOT say 'Great job' every time — vary your encouragement. "
        "If their angle is close to target (within 10°), praise their form. "
        "If pain score is high (>=7), advise them to ease off gently. "
        "If they are resting between sets, give a recovery tip. "
        "If they completed the exercise, give a brief motivational summary sentence (max 20 words)."
    )

    context_msg = (
        f"Exercise: {request.exercise_name}\n"
        f"Phase: {request.phase}\n"
        f"Current knee angle: {request.current_angle}°, Target: {request.target_angle}°, Difference: {angle_diff}°\n"
        f"Rep {request.current_rep}/{request.total_reps}, Set {request.current_set}/{request.total_sets}\n"
        f"Past pain scores: {request.pain_scores} (avg: {avg_pain})\n"
        f"Days since surgery: {request.days_post_op}\n"
        f"Give ONE coaching tip for this exact moment."
    )

    tip = ""
    encouragement = ""

    if GEMINI_API_KEY:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"

            payload = json.dumps({
                "system_instruction": {"parts": [{"text": system_prompt}]},
                "contents": [{"role": "user", "parts": [{"text": context_msg}]}],
                "generationConfig": {
                    "temperature": 0.7,
                    "maxOutputTokens": 60
                }
            }).encode("utf-8")

            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE

            req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
            with urllib.request.urlopen(req, context=ctx, timeout=10) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                tip = result["candidates"][0]["content"]["parts"][0]["text"].strip()
                print(f"Coach Gemini OK: {tip}")

        except Exception as e:
            print(f"Coach Gemini error: {e}")
            tip = ""

    # Smart fallback if Gemini fails
    if not tip:
        if request.phase == "completed":
            tip = f"Well done! You completed {request.total_reps}x{request.total_sets} of {request.exercise_name}."
        elif request.phase == "resting":
            tip = "Breathe deeply and relax your leg. Stay hydrated."
        elif avg_pain >= 7:
            tip = "Ease off gently — listen to your body."
        elif angle_diff <= 10:
            tip = f"Almost there! Just {angle_diff}° more to your target."
        elif angle_diff <= 25:
            tip = f"Good progress! Push {angle_diff}° more if comfortable."
        else:
            tip = "Slow and steady — focus on smooth movement."

    return {
        "tip": tip,
        "angle_diff": angle_diff,
        "avg_pain": avg_pain
    }


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
