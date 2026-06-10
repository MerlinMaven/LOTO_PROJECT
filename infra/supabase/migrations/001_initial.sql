-- Script d'initialisation de la base de données pour SmartLOTO
-- À exécuter dans l'éditeur SQL de votre console Supabase.

-- Table des procédures
CREATE TABLE IF NOT EXISTS procedures (
    machine_id TEXT PRIMARY KEY,
    machine_name TEXT NOT NULL,
    created_by_hse TEXT NOT NULL,
    status TEXT DEFAULT 'PENDING' CHECK (status IN ('PENDING', 'APPROVED')),
    workflow_stages JSONB NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Table des interventions de maintenance (LOTO)
CREATE TABLE IF NOT EXISTS interventions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    machine_id TEXT REFERENCES procedures(machine_id) ON DELETE CASCADE,
    operator_name TEXT NOT NULL,
    status TEXT DEFAULT 'IN_PROGRESS' CHECK (status IN ('IN_PROGRESS', 'COMPLETED')),
    current_stage_id INT DEFAULT 1,
    logs JSONB DEFAULT '[]'::jsonb,
    signature_url TEXT,
    pdf_report_url TEXT,
    started_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE
);

-- Activation de l'accès aux buckets de stockage si nécessaire
-- Note : Il est recommandé de créer un bucket nommé 'smartloto-assets'
-- avec un accès public pour simplifier la récupération des rapports et images de validation.

-- ======================================================
-- Sécurisation avec Row Level Security (RLS)
-- ======================================================

-- 1. Table procedures
ALTER TABLE procedures ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Allow public read access to procedures" 
ON procedures FOR SELECT USING (true);

CREATE POLICY "Allow public write access to procedures" 
ON procedures FOR INSERT WITH CHECK (true);

CREATE POLICY "Allow public update access to procedures" 
ON procedures FOR UPDATE USING (true);

CREATE POLICY "Allow public delete access to procedures" 
ON procedures FOR DELETE USING (true);

-- 2. Table interventions
ALTER TABLE interventions ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Allow public read access to interventions" 
ON interventions FOR SELECT USING (true);

CREATE POLICY "Allow public write access to interventions" 
ON interventions FOR INSERT WITH CHECK (true);

CREATE POLICY "Allow public update access to interventions" 
ON interventions FOR UPDATE USING (true);

CREATE POLICY "Allow public delete access to interventions" 
ON interventions FOR DELETE USING (true);

