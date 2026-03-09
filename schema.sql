-- Supabase SQL Schema for KneeGuide System

CREATE TABLE patients (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name TEXT NOT NULL,
    surgery_date TIMESTAMP WITH TIME ZONE NOT NULL,
    phone TEXT,
    address TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE daily_checkins (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    patient_id UUID REFERENCES patients(id),
    pain_score INTEGER CHECK (pain_score >= 0 AND pain_score <= 10),
    pain_location TEXT,
    swelling TEXT,
    wound_status TEXT,
    temperature TEXT,
    mobility TEXT,
    mood_score INTEGER CHECK (mood_score >= 1 AND mood_score <= 5),
    escalation_level TEXT CHECK (escalation_level IN ('GREEN', 'AMBER', 'RED', 'CRITICAL')),
    flags TEXT[],  -- Array of flag rules hit
    actions TEXT[],
    ai_summary TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE medication_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    patient_id UUID REFERENCES patients(id),
    medication_name TEXT NOT NULL,
    time TEXT NOT NULL,
    taken BOOLEAN DEFAULT false,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE activity_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    patient_id UUID REFERENCES patients(id),
    activity_type TEXT NOT NULL, -- "exercise", "walk", etc
    details TEXT,
    pain_score INTEGER CHECK (pain_score >= 0 AND pain_score <= 10),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE caregiver_alerts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    patient_id UUID REFERENCES patients(id),
    level TEXT CHECK (level IN ('RED', 'CRITICAL')),
    message TEXT NOT NULL,
    status TEXT DEFAULT 'unresolved', -- "unresolved", "contacted", "resolved"
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    resolved_at TIMESTAMP WITH TIME ZONE
);
