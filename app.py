import streamlit as st
import os
import json
import requests
import pandas as pd
from dotenv import load_dotenv
from datetime import datetime

# Charger les variables d'environnement
load_dotenv()

# Configuration de la page Streamlit
st.set_page_config(
    page_title="SmartLOTO - HSE Administration",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Style CSS pour une interface premium, ultra-épurée (Light Theme - Minimaliste)
st.markdown("""
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
<style>
    /* Style Global */
    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
        background-color: #FAFAFA;
        color: #0F172A;
    }
    
    /* En-tête Supérieur - Contraste Sombre Luxe */
    .header-container {
        background: linear-gradient(135deg, #0F172A 0%, #1E293B 100%);
        padding: 2rem;
        border-radius: 12px;
        border: none;
        margin-bottom: 2rem;
        box-shadow: 0 10px 25px -5px rgba(15, 23, 42, 0.08), 0 8px 10px -6px rgba(15, 23, 42, 0.08);
        display: flex;
        justify-content: space-between;
        align-items: center;
        position: relative;
        overflow: hidden;
    }
    .header-container::before {
        content: '';
        position: absolute;
        top: -50%;
        left: -50%;
        width: 200%;
        height: 200%;
        background: radial-gradient(circle, rgba(99, 102, 241, 0.1) 0%, rgba(99, 102, 241, 0) 60%);
        pointer-events: none;
    }
    .header-text h1 {
        font-size: 1.7rem;
        font-weight: 700;
        color: #FFFFFF;
        margin: 0;
        letter-spacing: -0.4px;
    }
    .header-text p {
        font-size: 0.88rem;
        color: #94A3B8;
        margin-top: 0.3rem;
        margin-bottom: 0;
    }
    .header-badge {
        background: rgba(255, 255, 255, 0.06);
        color: #F8FAFC;
        border: 1px solid rgba(255, 255, 255, 0.1);
        padding: 6px 14px;
        border-radius: 30px;
        font-size: 0.75rem;
        font-weight: 600;
        display: flex;
        align-items: center;
        gap: 6px;
        backdrop-filter: blur(4px);
    }
    
    /* Panneau Latéral (Sidebar) */
    [data-testid="stSidebar"] {
        background-color: #FFFFFF;
        border-right: 1px solid #E2E8F0;
    }
    
    /* Indicateurs de Statut */
    .sidebar-status-container {
        display: flex;
        flex-direction: column;
        gap: 10px;
        margin: 1rem 0;
        padding: 0.85rem;
        background-color: #F8FAFC;
        border-radius: 8px;
        border: 1px solid #E2E8F0;
    }
    .sidebar-status-item {
        display: flex;
        align-items: center;
        gap: 8px;
        font-size: 0.75rem;
        color: #475569;
    }
    .status-dot {
        width: 6px;
        height: 6px;
        border-radius: 50%;
        display: inline-block;
    }
    .status-dot-active {
        background-color: #10B981;
        box-shadow: 0 0 6px rgba(16, 185, 129, 0.4);
    }
    .status-dot-inactive {
        background-color: #EF4444;
        box-shadow: 0 0 6px rgba(239, 68, 68, 0.4);
    }
    
    /* Cartes Métriques Premium avec Pop-Interactions */
    .metric-card {
        background: #FFFFFF;
        padding: 1.5rem;
        border-radius: 12px;
        border: 1px solid #E2E8F0;
        margin-bottom: 1rem;
        box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.01), 0 1px 2px -1px rgba(0, 0, 0, 0.01);
        transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
        position: relative;
        overflow: hidden;
    }
    .metric-card:hover {
        transform: translateY(-3px);
        box-shadow: 0 12px 20px -8px rgba(0, 0, 0, 0.06), 0 4px 6px -2px rgba(0, 0, 0, 0.01);
        border-color: #CBD5E1;
    }
    .metric-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
    }
    .metric-title {
        font-size: 0.72rem;
        color: #64748B;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.8px;
    }
    .metric-icon-wrapper {
        width: 32px;
        height: 32px;
        border-radius: 8px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 0.95rem;
        transition: transform 0.2s ease;
    }
    .metric-card:hover .metric-icon-wrapper {
        transform: scale(1.1);
    }
    .metric-value {
        font-size: 1.8rem;
        font-weight: 700;
        color: #0F172A;
        margin-top: 0.5rem;
        margin-bottom: 0.15rem;
        letter-spacing: -0.5px;
    }
    .metric-subtitle {
        font-size: 0.78rem;
        color: #94A3B8;
    }
    
    /* Cartes d'Actions et d'Étapes */
    .step-card {
        background: #F8FAFC;
        border: 1px solid #E2E8F0;
        border-radius: 8px;
        padding: 1rem;
        margin-bottom: 0.6rem;
        display: flex;
        gap: 12px;
        align-items: flex-start;
        transition: border-color 0.2s ease;
    }
    .step-card:hover {
        border-color: #CBD5E1;
    }
    .step-badge {
        background: #FFFFFF;
        color: #475569;
        border: 1px solid #E2E8F0;
        font-weight: 600;
        font-size: 0.7rem;
        padding: 3px 8px;
        border-radius: 4px;
        white-space: nowrap;
    }
    .step-content {
        flex-grow: 1;
    }
    .step-desc {
        font-size: 0.85rem;
        font-weight: 500;
        color: #0F172A;
    }
    .step-prompt {
        font-size: 0.78rem;
        color: #64748B;
        margin-top: 3px;
    }
    code {
        background: #E2E8F0;
        color: #0F172A;
        padding: 1px 3px;
        border-radius: 3px;
        font-family: monospace;
        font-size: 0.78rem;
    }
    
    /* Badges de Statut */
    .badge {
        display: inline-block;
        padding: 0.25rem 0.6rem;
        font-size: 0.72rem;
        font-weight: 600;
        border-radius: 6px;
        text-align: center;
    }
    .badge-approved {
        background-color: #ECFDF5;
        color: #065F46;
        border: 1px solid #A7F3D0;
    }
    .badge-pending {
        background-color: #FFFBEB;
        color: #92400E;
        border: 1px solid #FDE68A;
    }
    .badge-completed {
        background-color: #ECFDF5;
        color: #065F46;
        border: 1px solid #A7F3D0;
    }
    .badge-inprogress {
        background-color: #EFF6FF;
        color: #1E40AF;
        border: 1px solid #BFDBFE;
    }
    
    /* Journal des Logs */
    .log-item {
        padding: 10px 14px;
        border-radius: 6px;
        font-size: 0.82rem;
        margin-bottom: 6px;
        border-left: 3px solid;
    }
    .log-success {
        background-color: #F0FDF4;
        color: #166534;
        border-left-color: #10B981;
        border: 1px solid #DCFCE7;
    }
    .log-warning {
        background-color: #FFFBEB;
        color: #92400E;
        border-left-color: #F59E0B;
        border: 1px solid #FEF3C7;
    }
    
    /* Tab Styling */
    .stTabs [data-baseweb="tab-list"] {
        gap: 16px;
    }
    .stTabs [data-baseweb="tab"] {
        height: 42px;
        padding-top: 10px;
        padding-bottom: 10px;
        font-size: 0.85rem;
        font-weight: 500;
        color: #64748B !important;
        border-bottom: 2px solid transparent !important;
        transition: all 0.25s ease !important;
    }
    .stTabs [aria-selected="true"] {
        color: #0F172A !important;
        border-bottom-color: #0F172A !important;
        font-weight: 600 !important;
    }
    
    /* Surcharge des inputs natifs */
    div[data-testid="stTextInput"] input, div[data-testid="stTextArea"] textarea {
        border-radius: 8px !important;
        border: 1px solid #E2E8F0 !important;
        background-color: #FFFFFF !important;
        color: #0F172A !important;
        transition: all 0.2s ease !important;
    }
    div[data-testid="stTextInput"] input:focus, div[data-testid="stTextArea"] textarea:focus {
        border-color: #0F172A !important;
        box-shadow: 0 0 0 3px rgba(15, 23, 42, 0.06) !important;
    }
    div[data-testid="stSelectbox"] > div {
        border-radius: 8px !important;
        border: 1px solid #E2E8F0 !important;
        background-color: #FFFFFF !important;
        transition: all 0.2s ease !important;
    }
    
    /* Boutons Primaires (Sombre Luxe) */
    button[data-testid="stBaseButton-primary"] {
        background: linear-gradient(135deg, #0F172A 0%, #1E293B 100%) !important;
        color: #FFFFFF !important;
        border: none !important;
        border-radius: 8px !important;
        font-weight: 600 !important;
        box-shadow: 0 4px 6px -1px rgba(15, 23, 42, 0.08) !important;
        transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1) !important;
    }
    button[data-testid="stBaseButton-primary"]:hover {
        background: linear-gradient(135deg, #1E293B 0%, #334155 100%) !important;
        transform: translateY(-1px) !important;
        box-shadow: 0 10px 15px -3px rgba(15, 23, 42, 0.12) !important;
    }
    
    /* Boutons Secondaires (Épuré) */
    button[data-testid="stBaseButton-secondary"] {
        background-color: #FFFFFF !important;
        color: #475569 !important;
        border: 1px solid #E2E8F0 !important;
        border-radius: 8px !important;
        font-weight: 500 !important;
        transition: all 0.2s ease !important;
    }
    button[data-testid="stBaseButton-secondary"]:hover {
        background-color: #F8FAFC !important;
        color: #0F172A !important;
        border-color: #CBD5E1 !important;
    }

    /* Style des containers avec bordure (Cartes et formulaires) */
    div[data-testid="stVerticalBlockBorderWrapper"] {
        border: 1px solid #E2E8F0 !important;
        border-radius: 8px !important;
        background-color: #FFFFFF !important;
        box-shadow: none !important;
        transition: background-color 0.2s ease, border-color 0.2s ease !important;
        padding: 1rem !important;
    }
    div[data-testid="stVerticalBlockBorderWrapper"]:hover {
        background-color: #F8FAFC !important;
        border-color: #CBD5E1 !important;
    }

    /* Alignement vertical parfait des éléments dans les cartes du catalogue */
    div[data-testid="stVerticalBlockBorderWrapper"]:has(.fa-industry) div[data-testid="stHorizontalBlock"] {
        align-items: center !important;
    }

    /* Style général des boutons dans les colonnes imbriquées du catalogue (Inspecter/Supprimer) */
    div[data-testid="stColumn"] div[data-testid="stColumn"] button {
        height: 32px !important;
        min-height: 32px !important;
        padding: 2px 12px !important;
        font-size: 0.78rem !important;
        border-radius: 6px !important;
    }

    /* Bouton de suppression spécifique dans les cartes du catalogue */
    div[data-testid="stColumn"] div[data-testid="stColumn"]:last-child button {
        color: #EF4444 !important;
        border-color: #FEE2E2 !important;
        background-color: #FEF2F2 !important;
    }
    div[data-testid="stColumn"] div[data-testid="stColumn"]:last-child button:hover {
        color: #DC2626 !important;
        border-color: #FCA5A5 !important;
        background-color: #FEE2E2 !important;
        box-shadow: none !important;
    }
</style>

""", unsafe_allow_html=True)

# Helper pour modifier le fichier .env
def update_env_file(key, value):
    env_path = ".env"
    lines = []
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
            
    updated = False
    new_lines = []
    for line in lines:
        if line.strip().startswith(f"{key}="):
            new_lines.append(f"{key}={value}\n")
            updated = True
        else:
            new_lines.append(line)
            
    if not updated:
        new_lines.append(f"{key}={value}\n")
        
    with open(env_path, "w", encoding="utf-8") as f:
        f.writelines(new_lines)
    
    os.environ[key] = value

# Initialisation des variables dans st.session_state
if "openrouter_key" not in st.session_state:
    st.session_state["openrouter_key"] = os.getenv("OPENROUTER_API_KEY", "")
if "openrouter_model" not in st.session_state:
    st.session_state["openrouter_model"] = os.getenv("OPENROUTER_MODEL", "qwen/qwen-2.5-7b-instruct")
if "supabase_key" not in st.session_state:
    st.session_state["supabase_key"] = os.getenv("SUPABASE_KEY", "")
if "supabase_url" not in st.session_state:
    st.session_state["supabase_url"] = os.getenv("SUPABASE_URL", "")
if "selected_inspect_machine_id" not in st.session_state:
    st.session_state["selected_inspect_machine_id"] = None


# Client Supabase
def get_supabase_client():
    url = st.session_state["supabase_url"]
    key = st.session_state["supabase_key"]
    if not url or not key or "your-supabase" in url:
        return None
    try:
        from supabase import create_client
        return create_client(url, key)
    except Exception:
        return None

# Appel OpenRouter LLM
def call_llm_generation(machine_id, machine_name, created_by, components):
    api_key = st.session_state["openrouter_key"]
    if not api_key:
        raise ValueError("Clé API OpenRouter manquante.")

    prompt = f"""
    En tant qu'ingénieur HSE expert en Lockout-Tagout (LOTO) et conformité OSHA 1910.147, génère une procédure de consignation et déconsignation détaillée sous forme de fichier JSON valide.
    
    Données d'entrée :
    - ID Machine : {machine_id}
    - Nom Machine : {machine_name}
    - Créé par : {created_by}
    - Organes à consigner (liste fournie par le HSE) :
    {components}
    
    Règles de génération :
    1. Crée un enchaînement logique d'étapes (stages) regroupant des actions de consignation de l'énergie (électricité, pression, fluide) puis de déconsignation (rétablissement).
    2. Pour chaque action, fournis une description claire et sécuritaire en français pour guider l'opérateur en réalité mixte.
    3. Pour chaque action, définis obligatoirement un `vision_prompt` en ANGLAIS précis pour le modèle de vision zero-shot YOLO-World (ex: "red padlock", "black lever pointing down", "yellow gate valve").
    4. La structure de retour doit être UNIQUEMENT un objet JSON valide structuré comme suit (sans préambule ni texte explicatif additionnel) :
    
    {{
      "machine_id": "{machine_id}",
      "machine_name": "{machine_name}",
      "created_by_hse": "{created_by}",
      "status": "APPROVED",
      "workflow_stages": [
        {{
          "stage_id": 1,
          "type": "consignation",
          "title": "Isolation Électrique",
          "actions": [
            {{
              "action_id": "1.1",
              "description": "Abaissez le levier du disjoncteur principal de la boîte noire.",
              "vision_prompt": "black marker pointing down",
              "completion_check": "vision_detection"
            }},
            {{
              "action_id": "1.2",
              "description": "Posez le cadenas de condamnation sur le point d'isolation électrique.",
              "vision_prompt": "red pen",
              "completion_check": "vision_detection"
            }}
          ]
        }},
        {{
          "stage_id": 2,
          "type": "deconsignation",
          "title": "Rétablissement",
          "actions": [
            {{
              "action_id": "2.1",
              "description": "Retirez le cadenas de condamnation.",
              "vision_prompt": "red pen",
              "completion_check": "inverse_vision_absence"
            }}
          ]
        }}
      ]
    }}
    """

    headers = {
        "Authorization": f"Bearer {api_key}",
        "HTTP-Referer": "https://github.com/smartloto",
        "Content-Type": "application/json"
    }
    
    data = {
        "model": st.session_state["openrouter_model"],
        "messages": [
            {"role": "system", "content": "Tu es un ingénieur HSE spécialisé en LOTO industrielle. Tu réponds uniquement par du JSON valide conforme au schéma demandé. Pas d'explications en dehors."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.2
    }
    
    response = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=data)
    response.raise_for_status()
    res_json = response.json()
    
    if 'choices' not in res_json or len(res_json['choices']) == 0:
        raise ValueError("Réponse invalide de l'API OpenRouter.")
        
    content = res_json['choices'][0]['message']['content'].strip()
    
    # Nettoyage si markdown
    if content.startswith("```json"):
        content = content[7:]
    if content.endswith("```"):
        content = content[:-3]
    content = content.strip()
    
    return json.loads(content)


# Appel OpenRouter VLLM (Alternative sans blocage DNS)
def call_openrouter_vllm(machine_id, machine_name, created_by, components, base64_image, model_id="qwen/qwen2.5-vl-72b-instruct"):
    api_key = st.session_state["openrouter_key"]
    if not api_key:
        raise ValueError("Clé API OpenRouter manquante.")

    prompt = f"""
    En tant qu'ingénieur HSE expert en Lockout-Tagout (LOTO) et conformité OSHA 1910.147, analyse l'image de la machine et la liste des composants pour générer une procédure de consignation et déconsignation détaillée sous forme de fichier JSON valide.
    
    Données d'entrée :
    - ID Machine : {machine_id}
    - Nom Machine : {machine_name}
    - Créé par : {created_by}
    - Organes physiques à isoler (suggérés ou complétés par rapport à l'image) :
    {components}
    
    Règles de génération :
    1. Regarde attentivement l'image pour identifier les organes de coupure. Si des organes d'énergie critiques sont visibles mais absents de la liste, intègre-les.
    2. Crée un enchaînement logique d'étapes (stages) regroupant des actions de consignation (électricité, pression, fluide) puis de déconsignation (rétablissement).
    3. Pour chaque action, fournis une description claire et sécuritaire en français pour guider l'opérateur.
    4. Pour chaque action, définis obligatoirement un `vision_prompt` en ANGLAIS extrêmement précis basé sur ce que tu vois (ex: "black lever pointing down", "red padlock", "yellow valve handle").
    5. La structure de retour doit être UNIQUEMENT un objet JSON valide structuré comme suit (sans préambule ni texte explicatif additionnel) :
    
    {{
      "machine_id": "{machine_id}",
      "machine_name": "{machine_name}",
      "created_by_hse": "{created_by}",
      "status": "APPROVED",
      "workflow_stages": [
        {{
          "stage_id": 1,
          "type": "consignation",
          "title": "Isolation Électrique",
          "actions": [
            {{
              "action_id": "1.1",
              "description": "Abaissez le disjoncteur principal noir visible sur le panneau.",
              "vision_prompt": "black switch lever pointing down",
              "completion_check": "vision_detection"
            }}
          ]
        }}
      ]
    }}
    """

    headers = {
        "Authorization": f"Bearer {api_key}",
        "HTTP-Referer": "https://github.com/smartloto",
        "Content-Type": "application/json"
    }

    # Format de messages OpenAI compatible avec les images
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{base64_image}"
                    }
                }
            ]
        }
    ]

    payload = {
        "model": model_id,
        "messages": messages,
        "temperature": 0.2
    }

    api_url = "https://openrouter.ai/api/v1/chat/completions"
    response = requests.post(api_url, headers=headers, json=payload)
    
    if response.status_code != 200:
        raise ValueError(f"Erreur OpenRouter VLLM (Status {response.status_code}): {response.text}")
        
    res_json = response.json()
    if 'choices' not in res_json or len(res_json['choices']) == 0:
        raise ValueError("Réponse de l'API OpenRouter invalide.")
        
    content = res_json['choices'][0]['message']['content'].strip()
    
    # Nettoyage si markdown
    if content.startswith("```json"):
        content = content[7:]
    if content.endswith("```"):
        content = content[:-3]
    content = content.strip()
    
    return json.loads(content)

def convert_flat_to_twophase(res_json):
    if not res_json:
        return res_json
    stages = res_json.get("workflow_stages", [])
    if isinstance(stages, dict) and ("lockout" in stages or "restoration" in stages):
        return res_json
    lockout_stages = []
    restoration_stages = []
    if isinstance(stages, list):
        for s in stages:
            s_type = s.get("type", "consignation")
            s_id = s.get("stage_id")
            if not s_id:
                import uuid
                s_id = f"stg_{uuid.uuid4().hex[:6]}"
            actions = s.get("actions", [])
            cleaned_actions = []
            for a in actions:
                a_id = a.get("action_id")
                if not a_id:
                    import uuid
                    a_id = f"act_{uuid.uuid4().hex[:6]}"
                cleaned_actions.append({
                    "action_id": a_id,
                    "description": a.get("description", ""),
                    "vision_prompt": a.get("vision_prompt", ""),
                    "completion_check": a.get("completion_check", "vision_detection")
                })
            stage_copy = {
                "stage_id": s_id,
                "title": s.get("title", "Module sans titre"),
                "actions": cleaned_actions
            }
            if s_type == "deconsignation":
                restoration_stages.append(stage_copy)
            else:
                lockout_stages.append(stage_copy)
    res_json["workflow_stages"] = {
        "lockout": lockout_stages,
        "restoration": restoration_stages
    }
    return res_json

# Composant de carte métrique premium avec couleur
def render_metric_card(title, value, subtitle, icon_class, bg_color, text_color):
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-header">
            <span class="metric-title">{title}</span>
            <div class="metric-icon-wrapper" style="background-color: {bg_color}; color: {text_color};">
                <i class="{icon_class}"></i>
            </div>
        </div>
        <div class="metric-value">{value}</div>
        <div class="metric-subtitle">{subtitle}</div>
    </div>
    """, unsafe_allow_html=True)

# En-tête de page principal
st.markdown("""
<div class="header-container">
    <div class="header-text">
        <h1>SmartLOTO HSE Portal</h1>
        <p>Console d'administration sémantique et de supervision pour la consignation assistée par IA & AR</p>
    </div>
    <div class="header-badge">
        <i class="fa-solid fa-shield-halved"></i>
        Conformité OSHA 1910.147
    </div>
</div>
""", unsafe_allow_html=True)

# Navigation et Barre Latérale
with st.sidebar:
    st.markdown("<h3 style='margin-top:0;color:#0F172A;font-weight:600;font-size:1.15rem;'>SmartLOTO Console</h3>", unsafe_allow_html=True)
    
    # Statuts de connexion
    db_client = get_supabase_client()
    or_status = "status-dot-active" if st.session_state["openrouter_key"] else "status-dot-inactive"
    sb_status = "status-dot-active" if db_client else "status-dot-inactive"
    
    # Noms des modèles pour l'affichage premium
    llm_name = "Qwen 2.5 7B"
    vlm_name = "Qwen-VL / Gemini"
    
    st.markdown(f"""
    <div class="sidebar-status-container">
        <div class="sidebar-status-item">
            <span class="status-dot {or_status}"></span>
            <span class="status-text">LLM : {llm_name if st.session_state["openrouter_key"] else "Déconnecté"}</span>
        </div>
        <div class="sidebar-status-item">
            <span class="status-dot {or_status}"></span>
            <span class="status-text">VLM : {vlm_name if st.session_state["openrouter_key"] else "Déconnecté"}</span>
        </div>
        <div class="sidebar-status-item">
            <span class="status-dot {sb_status}"></span>
            <span class="status-text">Supabase : {"Connecté" if db_client else "Déconnecté"}</span>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    menu = st.radio(
        "Navigation",
        ["Vue d'ensemble", "Configuration LOTO", "Suivi des Interventions", "Diagnostics & Paramètres"],
        index=0
    )
    
    st.write("---")
    st.markdown("<p style='font-size:0.7rem;color:#94A3B8;'>SmartLOTO Panel v1.0.0<br>© 2026 SmartLOTO</p>", unsafe_allow_html=True)

# --- Moteur de rendu selon le menu ---

if menu == "Vue d'ensemble":
    st.markdown("### Vue d'ensemble")
    
    proc_count = 0
    int_count = 0
    completed_count = 0
    override_count = 0
    
    if db_client:
        try:
            p_res = db_client.table("procedures").select("machine_id", count="exact").execute()
            proc_count = p_res.count if p_res.count else 0
            
            i_res = db_client.table("interventions").select("id, status, logs", count="exact").execute()
            int_count = i_res.count if i_res.count else 0
            
            for row in i_res.data:
                if row.get("status") == "COMPLETED":
                    completed_count += 1
                logs = row.get("logs", [])
                if isinstance(logs, list):
                    for log in logs:
                        if "override" in str(log.get("type", "")).lower() or "override" in str(log.get("action", "")).lower():
                            override_count += 1
        except Exception:
            pass
    else:
        proc_count = 1
        int_count = 5
        completed_count = 4
        override_count = 1

    # Cartes de métriques premium
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        render_metric_card("Équipements Configurés", proc_count, "Fiches techniques approuvées", "fa-solid fa-industry", "#EFF6FF", "#3B82F6")
    with col2:
        render_metric_card("Interventions Totales", int_count, "Historique d'exécution", "fa-solid fa-route", "#F5F3FF", "#8B5CF6")
    with col3:
        render_metric_card("Interventions Clôturées", completed_count, "Sécurisées et signées", "fa-solid fa-circle-check", "#ECFDF5", "#10B981")
    with col4:
        override_rate = f"{(override_count / int_count * 100):.1f}%" if int_count > 0 else "0%"
        render_metric_card("Taux de dérogation", override_rate, f"{override_count} cas d'override", "fa-solid fa-triangle-exclamation", "#FFFBEB", "#F59E0B")

    st.write("---")
    st.markdown("#### Activités Récentes des Interventions")
    
    if db_client:
        try:
            i_data = db_client.table("interventions").select("id, machine_id, operator_name, status, started_at").order("started_at", desc=True).limit(5).execute()
            if i_data.data:
                df = pd.DataFrame(i_data.data)
                df.columns = ["ID Intervention", "Code Machine", "Opérateur", "Statut", "Débuté le"]
                st.dataframe(df, use_container_width=True)
            else:
                st.info("Aucune intervention enregistrée.")
        except Exception:
            st.info("Initialisation de la base de données requise.")
    else:
        dummy_data = [
            {"ID": "f8a7e2...", "Machine": "SIM-CHP-2026", "Opérateur": "Sofiane B.", "Statut": "IN_PROGRESS", "Date": "2026-05-25 14:15"},
            {"ID": "a1b2c3...", "Machine": "SIM-CHP-2026", "Opérateur": "Jean M.", "Statut": "COMPLETED", "Date": "2026-05-25 10:30"}
        ]
        st.dataframe(pd.DataFrame(dummy_data), use_container_width=True)

elif menu == "Configuration LOTO":
    st.markdown("### Configuration des Procédures LOTO")
    st.markdown("Générez et figez les fiches techniques contenant la logique fonctionnelle d'isolation machine.")

    tab1, tab2 = st.tabs(["Créer une Procédure", "Procédures Enregistrées"])
    
    with tab1:
        col_left, col_right = st.columns([1.2, 2])
        
        with col_left:
            st.markdown("<p style='font-weight:600;font-size:0.85rem;color:#0F172A;text-transform:uppercase;letter-spacing:0.5px;margin-bottom:0.8rem;'>🔧 Paramètres de l'Équipement</p>", unsafe_allow_html=True)
            with st.container(border=True):
                m_id = st.text_input("Identifiant Unique de la Machine", "SIM-CHP-2026")
                m_name = st.text_input("Nom de l'Équipement", "Compresseur HP")
                hse_name = st.text_input("Responsable HSE", "W. SERRAJI")
                components_list = st.text_area(
                    "Organes physiques à isoler (un par ligne) :",
                    "Disjoncteur électrique principal (noir)\nCadenas rouge sur moraillon électrique\nVanne de décharge de pression (rouge)\nCadenas jaune sur la vanne de fluide",
                    height=120
                )
                
                gen_mode = st.selectbox(
                    "Moteur de génération",
                    options=[
                        "Texte seul (LLM - Qwen-2.5-7B via OpenRouter)", 
                        "Texte + Image (VLLM - Qwen2.5-VL via OpenRouter)",
                        "Texte + Image (VLLM - Gemini 2.0 Flash via OpenRouter)"
                    ],
                    index=0
                )
                
                base64_img = None
                if "VLLM" in gen_mode:
                    uploaded_file = st.file_uploader("Photo de la machine (Analyse Visuelle)", type=["png", "jpg", "jpeg"])
                    if uploaded_file is not None:
                        import base64
                        bytes_data = uploaded_file.getvalue()
                        base64_img = base64.b64encode(bytes_data).decode("utf-8")
                        st.image(uploaded_file, caption="Aperçu de la machine chargée", use_container_width=True)
                
                generate_clicked = st.button("Générer la procédure", type="primary", use_container_width=True)
                
                if generate_clicked:
                    if "VLLM" in gen_mode:
                        if base64_img is None:
                            st.error("Veuillez uploader une photo de la machine pour utiliser le mode VLLM.")
                        else:
                            with st.spinner("Analyse visuelle et génération LOTO par l'IA Multimodale..."):
                                try:
                                    if "Qwen2.5-VL" in gen_mode:
                                        res_json = call_openrouter_vllm(m_id, m_name, hse_name, components_list, base64_img, "qwen/qwen2.5-vl-72b-instruct")
                                        st.session_state["generated_loto_json"] = res_json
                                        st.success("Procédure visuelle générée avec succès (Qwen2.5-VL) !")
                                    else: # Gemini 2.0 Flash
                                        res_json = call_openrouter_vllm(m_id, m_name, hse_name, components_list, base64_img, "google/gemini-2.0-flash-001")
                                        st.session_state["generated_loto_json"] = res_json
                                        st.success("Procédure visuelle générée avec succès (Gemini 2.0 Flash) !")
                                except Exception as e:
                                    st.error(f"Erreur de génération visuelle : {e}")
                    else:
                        if not st.session_state["openrouter_key"]:
                            st.error("Veuillez configurer votre clé OpenRouter dans les paramètres.")
                        else:
                            with st.spinner("Analyse technique et génération des étapes LOTO par l'IA..."):
                               try:
                                    res_json = call_llm_generation(m_id, m_name, hse_name, components_list)
                                    st.session_state["generated_loto_json"] = res_json
                                    st.success("Procédure générée avec succès !")
                               except Exception as e:
                                   st.error(f"Erreur lors de la génération : {e}")
                               
        with col_right:
            st.markdown("<p style='font-weight:600;font-size:0.85rem;color:#0F172A;text-transform:uppercase;letter-spacing:0.5px;margin-bottom:0.8rem;'>📝 Édition du Protocole de Sécurité</p>", unsafe_allow_html=True)
            
            if "generated_loto_json" in st.session_state:
                proc_json = st.session_state["generated_loto_json"]
                
                # Lier dynamiquement les modifications des inputs principaux aux valeurs du JSON final
                proc_json["machine_id"] = m_id
                proc_json["machine_name"] = m_name
                proc_json["created_by_hse"] = hse_name
                
                stages = proc_json.get("workflow_stages", [])
                
                # 1. Synchronisation initiale des widgets vers la session state JSON
                for s in stages:
                    s_id = s.get("stage_id")
                    if not s_id:
                        import uuid
                        s_id = f"stg_{uuid.uuid4().hex[:6]}"
                        s["stage_id"] = s_id
                        
                    title_key = f"edit_s_title_{s_id}"
                    type_key = f"edit_s_type_{s_id}"
                    
                    if title_key in st.session_state:
                        s["title"] = st.session_state[title_key]
                    if type_key in st.session_state:
                        s["type"] = st.session_state[type_key]
                        
                    for a in s.get("actions", []):
                        a_id = a.get("action_id")
                        if not a_id:
                            import uuid
                            a_id = f"act_{uuid.uuid4().hex[:6]}"
                            a["action_id"] = a_id
                            
                        desc_key = f"edit_a_desc_{s_id}_{a_id}"
                        prompt_key = f"edit_a_prompt_{s_id}_{a_id}"
                        check_key = f"edit_a_check_{s_id}_{a_id}"
                        
                        if desc_key in st.session_state:
                            a["description"] = st.session_state[desc_key]
                        if prompt_key in st.session_state:
                            a["vision_prompt"] = st.session_state[prompt_key]
                        if check_key in st.session_state:
                            a["completion_check"] = st.session_state[check_key]

                # 2. Rendu et Contrôles
                for s_idx, s in enumerate(stages):
                    s_id = s.get("stage_id")
                    
                    # En-tête de l'étape avec boutons de contrôle
                    col_title, col_ctrls = st.columns([3.8, 1.2])
                    with col_title:
                        st.markdown(f"<p style='font-size:0.88rem;font-weight:700;color:#0F172A;margin-top:0.6rem;margin-bottom:0.4rem;'><i class='fa-solid fa-folder-open' style='color:#64748B;margin-right:6px;'></i> Étape {s_idx + 1} : {s.get('title')} <span style='font-size:0.75rem;font-weight:500;color:#64748B;'>({s.get('type')})</span></p>", unsafe_allow_html=True)
                    with col_ctrls:
                        c_up, c_down, c_del = st.columns(3)
                        with c_up:
                            if st.button("▲", key=f"up_{s_id}", disabled=(s_idx == 0), use_container_width=True):
                                stages[s_idx], stages[s_idx - 1] = stages[s_idx - 1], stages[s_idx]
                                st.session_state["generated_loto_json"]["workflow_stages"] = stages
                                st.rerun()
                        with c_down:
                            if st.button("▼", key=f"down_{s_id}", disabled=(s_idx == len(stages) - 1), use_container_width=True):
                                stages[s_idx], stages[s_idx + 1] = stages[s_idx + 1], stages[s_idx]
                                st.session_state["generated_loto_json"]["workflow_stages"] = stages
                                st.rerun()
                        with c_del:
                            if st.button("🗑️", key=f"del_{s_id}", use_container_width=True):
                                stages.pop(s_idx)
                                st.session_state["generated_loto_json"]["workflow_stages"] = stages
                                st.rerun()
                                
                    # Paramètres de l'étape
                    col_s_name, col_s_type = st.columns([3, 1])
                    with col_s_name:
                        st.text_input("Titre de l'étape", value=s.get("title"), key=f"edit_s_title_{s_id}")
                    with col_s_type:
                        st.selectbox(
                            "Type", 
                            options=["consignation", "deconsignation"], 
                            index=0 if s.get("type") == "consignation" else 1, 
                            key=f"edit_s_type_{s_id}"
                        )
                        
                    # Actions de l'étape
                    actions = s.get("actions", [])
                    for a_idx, a in enumerate(actions):
                        a_id = a.get("action_id")
                        with st.container(border=True):
                            col_act_title, col_act_ctrls = st.columns([3.5, 1.5])
                            with col_act_title:
                                st.markdown(f"<span style='font-size:0.75rem;font-weight:600;color:#475569;'><i class='fa-solid fa-clipboard-check' style='color:#D4AF37;margin-right:6px;'></i> Action {s_idx + 1}.{a_idx + 1} (ID: {a_id})</span>", unsafe_allow_html=True)
                            with col_act_ctrls:
                                ca_up, ca_down, ca_del = st.columns(3)
                                with ca_up:
                                    if st.button("▲", key=f"up_act_{s_id}_{a_id}", disabled=(a_idx == 0), use_container_width=True):
                                        actions[a_idx], actions[a_idx - 1] = actions[a_idx - 1], actions[a_idx]
                                        st.session_state["generated_loto_json"]["workflow_stages"] = stages
                                        st.rerun()
                                with ca_down:
                                    if st.button("▼", key=f"down_act_{s_id}_{a_id}", disabled=(a_idx == len(actions) - 1), use_container_width=True):
                                        actions[a_idx], actions[a_idx + 1] = actions[a_idx + 1], actions[a_idx]
                                        st.session_state["generated_loto_json"]["workflow_stages"] = stages
                                        st.rerun()
                                with ca_del:
                                    if st.button("🗑️", key=f"del_act_{s_id}_{a_id}", use_container_width=True):
                                        actions.pop(a_idx)
                                        st.session_state["generated_loto_json"]["workflow_stages"] = stages
                                        st.rerun()
                                    
                            col_a1, col_a2 = st.columns([2, 1])
                            with col_a1:
                                st.text_area(
                                    "Description de l'action", 
                                    value=a.get("description"), 
                                    key=f"edit_a_desc_{s_id}_{a_id}", 
                                    height=85
                                )
                            with col_a2:
                                st.text_input(
                                    "Détection YOLO (anglais)", 
                                    value=a.get("vision_prompt"), 
                                    key=f"edit_a_prompt_{s_id}_{a_id}"
                                )
                                st.selectbox(
                                    "Mode de contrôle", 
                                    options=["vision_detection", "inverse_vision_absence"], 
                                    index=0 if a.get("completion_check") == "vision_detection" else 1, 
                                    key=f"edit_a_check_{s_id}_{a_id}"
                                )
                                
                    # Ajouter une action dans l'étape
                    if st.button("➕ Ajouter une action", key=f"add_act_{s_id}", use_container_width=True):
                        import uuid
                        new_act_id = f"act_{uuid.uuid4().hex[:6]}"
                        actions.append({
                            "action_id": new_act_id,
                            "description": "Nouvelle action à réaliser",
                            "vision_prompt": "lock",
                            "completion_check": "vision_detection"
                        })
                        st.session_state["generated_loto_json"]["workflow_stages"] = stages
                        st.rerun()
                        
                    st.write("---")
                
                # 3. Ajouter une étape globale
                if st.button("➕ Ajouter une Étape", key="add_new_stage_btn", use_container_width=True):
                    import uuid
                    new_stage_id = f"stg_{uuid.uuid4().hex[:6]}"
                    new_stage = {
                        "stage_id": new_stage_id,
                        "type": "consignation",
                        "title": "Nouvelle Étape",
                        "actions": [
                            {
                                "action_id": f"act_{uuid.uuid4().hex[:6]}",
                                "description": "Nouvelle action à réaliser",
                                "vision_prompt": "red lever",
                                "completion_check": "vision_detection"
                            }
                        ]
                    }
                    stages.append(new_stage)
                    st.session_state["generated_loto_json"]["workflow_stages"] = stages
                    st.rerun()
                    
                st.write("---")
                with st.expander("Spécification JSON brute de sécurité (Générée automatiquement)"):
                    st.json(proc_json)
                    
                col_save, _ = st.columns([1.5, 4])
                with col_save:
                    if st.button("Figer & Enregistrer", type="primary", key="save_loto_proc_btn", use_container_width=True):
                        if not db_client:
                            st.error("Aucune base de données Supabase connectée.")
                        else:
                            try:
                                # Normaliser les IDs séquentiellement pour la base de données (et la réalité mixte AR)
                                normalized_stages = []
                                for s_idx, s in enumerate(stages):
                                    norm_actions = []
                                    for a_idx, a in enumerate(s.get("actions", [])):
                                        norm_actions.append({
                                            "action_id": f"{s_idx + 1}.{a_idx + 1}",
                                            "description": a.get("description"),
                                            "vision_prompt": a.get("vision_prompt"),
                                            "completion_check": a.get("completion_check")
                                        })
                                    normalized_stages.append({
                                        "stage_id": s_idx + 1,
                                        "type": s.get("type"),
                                        "title": s.get("title"),
                                        "actions": norm_actions
                                    })
                                    
                                data_to_upsert = {
                                    "machine_id": proc_json.get("machine_id"),
                                    "machine_name": proc_json.get("machine_name"),
                                    "created_by_hse": proc_json.get("created_by_hse"),
                                    "status": "APPROVED",
                                    "workflow_stages": normalized_stages
                                }
                                db_client.table("procedures").upsert(data_to_upsert).execute()
                                
                                # Mettre à jour localement pour correspondre aux ID normalisés
                                proc_json["workflow_stages"] = normalized_stages
                                st.session_state["generated_loto_json"] = proc_json
                                
                                st.success("Procédure sauvegardée et verrouillée dans Supabase !")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Erreur d'enregistrement : {e}")
            else:
                with st.container(border=True):
                    st.markdown("""
                    <div style="text-align: center; padding: 4.5rem 1.5rem; color: #64748B;">
                        <i class="fa-solid fa-wand-magic-sparkles" style="font-size: 2.5rem; color: #CBD5E1; margin-bottom: 1.2rem;"></i>
                        <h4 style="margin:0; font-size:1rem; font-weight:600; color:#475569;">En attente de génération</h4>
                        <p style="margin: 0.5rem 0 0 0; font-size: 0.82rem; color: #94A3B8;">Remplissez les paramètres de l'équipement à gauche et cliquez sur <b>Générer la procédure</b> pour éditer le protocole pas-à-pas.</p>
                    </div>
                    """, unsafe_allow_html=True)

    with tab2:
        if db_client:
            try:
                p_data = db_client.table("procedures").select("*").execute()
                if p_data.data:
                    # Gérer l'inspection d'une fiche spécifique
                    inspect_id = st.session_state.get("selected_inspect_machine_id")
                    
                    if inspect_id:
                        selected_proc = next((item for item in p_data.data if item.get("machine_id") == inspect_id), None)
                        
                        if selected_proc:
                            if st.button("← Retour au catalogue des fiches"):
                                st.session_state["selected_inspect_machine_id"] = None
                                st.rerun()
                                
                            st.markdown(f"""
                            <div style="border-left: 4px solid #D4AF37; padding: 1.5rem; border-radius: 12px; background: #FFFFFF; border-top: 1px solid #E2E8F0; border-right: 1px solid #E2E8F0; border-bottom: 1px solid #E2E8F0; margin-top: 1rem; margin-bottom: 1.5rem; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.01), 0 2px 4px -1px rgba(0, 0, 0, 0.01);">
                                <div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid #F1F5F9; padding-bottom:12px; margin-bottom:12px;">
                                    <h3 style="margin:0; font-size:1.2rem; font-weight:700; color:#0F172A;">{selected_proc.get('machine_name')}</h3>
                                    <span class="badge badge-approved" style="background-color: #ECFDF5; color: #065F46; border: 1px solid #A7F3D0; font-size: 0.72rem; padding: 4px 10px; border-radius: 30px;">APPROVED & LOCKED</span>
                                </div>
                                <p style="font-size:0.78rem; color:#64748B; margin:0; display:flex; align-items:center; gap:12px;">
                                    <span>Identifiant : <code style="background-color:#F1F5F9; color:#0F172A; padding:2px 6px; border-radius:4px; font-family:monospace; border:1px solid #E2E8F0;">{selected_proc.get('machine_id')}</code></span>
                                    <span style="color:#E2E8F0;">•</span>
                                    <span>HSE : <b>{selected_proc.get('created_by_hse')}</b></span>
                                    <span style="color:#E2E8F0;">•</span>
                                    <span>Publication : {selected_proc.get('created_at')[:10]}</span>
                                </p>
                            </div>
                            """, unsafe_allow_html=True)
                            
                            # S'assurer du format two-phase pour la lecture
                            selected_proc = convert_flat_to_twophase(selected_proc)
                            stages_data = selected_proc.get("workflow_stages", {})
                            lockout_stages = stages_data.get("lockout", [])
                            restoration_stages = stages_data.get("restoration", [])
                            
                            # Rendu Phase 1 : Consignation
                            st.markdown("<p style='font-size:0.85rem;font-weight:700;color:#0F172A;text-transform:uppercase;letter-spacing:0.5px;margin-top:1.2rem;border-bottom:1px solid #E2E8F0;padding-bottom:4px;'>🔒 Phase 1 : Consignation (Lockout)</p>", unsafe_allow_html=True)
                            if not lockout_stages:
                                st.info("Aucun module de consignation.")
                            for s_idx, s in enumerate(lockout_stages):
                                st.markdown(f"<p style='font-size:0.8rem;font-weight:600;color:#475569;margin-top:0.8rem;margin-bottom:0.4rem;'>Module {s_idx + 1} : {s.get('title')}</p>", unsafe_allow_html=True)
                                for a in s.get("actions", []):
                                    st.markdown(f"""
                                    <div class="step-card">
                                        <div class="step-badge">Action {a.get('action_id')}</div>
                                        <div class="step-content">
                                            <div class="step-desc">{a.get('description')}</div>
                                            <div class="step-prompt">Détection visuelle : <code>{a.get('vision_prompt')}</code> | validation : <code>{a.get('completion_check')}</code></div>
                                        </div>
                                    </div>
                                    """, unsafe_allow_html=True)
                                    
                            # Rendu Phase 2 : Déconsignation
                            st.markdown("<p style='font-size:0.85rem;font-weight:700;color:#0F172A;text-transform:uppercase;letter-spacing:0.5px;margin-top:1.5rem;border-bottom:1px solid #E2E8F0;padding-bottom:4px;'>🔓 Phase 2 : Déconsignation (Restoration)</p>", unsafe_allow_html=True)
                            if not restoration_stages:
                                st.info("Aucun module de déconsignation.")
                            for s_idx, s in enumerate(restoration_stages):
                                st.markdown(f"<p style='font-size:0.8rem;font-weight:600;color:#475569;margin-top:0.8rem;margin-bottom:0.4rem;'>Module {s_idx + 1} : {s.get('title')}</p>", unsafe_allow_html=True)
                                for a in s.get("actions", []):
                                    st.markdown(f"""
                                    <div class="step-card">
                                        <div class="step-badge">Action {a.get('action_id')}</div>
                                        <div class="step-content">
                                            <div class="step-desc">{a.get('description')}</div>
                                            <div class="step-prompt">Détection visuelle : <code>{a.get('vision_prompt')}</code> | validation : <code>{a.get('completion_check')}</code></div>
                                        </div>
                                    </div>
                                    """, unsafe_allow_html=True)
                                    
                            st.write("---")
                            with st.expander("Spécification JSON brute de sécurité"):
                                st.json(selected_proc)
                        else:
                            st.error("Procédure introuvable.")
                            st.session_state["selected_inspect_machine_id"] = None
                    else:
                        st.markdown("""
                        <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 1.2rem; border-bottom: 1px solid #E2E8F0; padding-bottom: 8px;">
                            <i class="fa-solid fa-folder-open" style="color: #64748B; font-size: 1rem;"></i>
                            <span style="font-weight: 600; font-size: 0.85rem; color: #0F172A; text-transform: uppercase; letter-spacing: 0.5px;">Catalogue des Fiches Techniques Actives</span>
                        </div>
                        """, unsafe_allow_html=True)
                        
                        # Afficher la liste de manière synthétique et élégante
                        for p in p_data.data:
                            with st.container(border=True):
                                col_info, col_actions = st.columns([4.5, 2])
                                with col_info:
                                    st.markdown(f"""
                                    <div style="display: flex; align-items: center; gap: 14px;">
                                        <div style="color: #64748B; width: 38px; height: 38px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 1.15rem; background-color: #F1F5F9; border: 1px solid #E2E8F0;">
                                            <i class="fa-solid fa-industry"></i>
                                        </div>
                                        <div>
                                            <h4 style="margin: 0; font-size: 1.02rem; font-weight: 600; color: #0F172A; display: flex; align-items: center; gap: 8px;">
                                                {p.get('machine_name')}
                                                <span style="font-size: 0.72rem; color: #475569; font-weight: 500; background-color: #F1F5F9; padding: 2px 8px; border-radius: 4px; font-family: monospace; border: 1px solid #E2E8F0;">{p.get('machine_id')}</span>
                                            </h4>
                                            <p style="font-size: 0.75rem; color: #64748B; margin: 5px 0 0 0; display: flex; align-items: center; gap: 12px;">
                                                <span><i class="fa-regular fa-user" style="color: #94A3B8; margin-right: 4px;"></i> HSE : <b>{p.get('created_by_hse')}</b></span>
                                                <span style="color: #E2E8F0;">•</span>
                                                <span><i class="fa-regular fa-calendar" style="color: #94A3B8; margin-right: 4px;"></i> {p.get('created_at')[:10]}</span>
                                            </p>
                                        </div>
                                    </div>
                                    """, unsafe_allow_html=True)
                                with col_actions:
                                    col_inspect, col_del = st.columns(2)
                                    with col_inspect:
                                        if st.button("Inspecter", type="primary", key=f"inspect_{p.get('machine_id')}", use_container_width=True):
                                            st.session_state["selected_inspect_machine_id"] = p.get("machine_id")
                                            st.rerun()
                                    with col_del:
                                        if st.button("Supprimer", key=f"del_{p.get('machine_id')}", use_container_width=True):
                                            db_client.table("procedures").delete().eq("machine_id", p.get("machine_id")).execute()
                                            st.success(f"Fiche {p.get('machine_id')} supprimée.")
                                            st.rerun()
                else:
                    st.info("Aucune procédure enregistrée.")
            except Exception as e:
                st.error(f"Erreur lors du chargement : {e}")
        else:
            st.warning("Veuillez configurer Supabase dans l'onglet Diagnostics.")

elif menu == "Suivi des Interventions":
    st.markdown("### Supervision des Interventions Terrain")
    st.markdown("Suivi en temps réel des actions effectuées par les opérateurs équipés de casques de réalité mixte.")

    if db_client:
        try:
            i_data = db_client.table("interventions").select("*").order("started_at", desc=True).execute()
            if i_data.data:
                for i in i_data.data:
                    with st.container(border=True):
                        col_i1, col_i2 = st.columns([3, 1])
                        with col_i1:
                            st.markdown(f"<h3 style='margin:0;font-size:1.05rem;font-weight:600;color:#0F172A;'>Opérateur : <b>{i.get('operator_name')}</b></h3>", unsafe_allow_html=True)
                            st.markdown(f"<p style='font-size:0.8rem;color:#64748B;margin:4px 0 0 0;'>Machine : <code>{i.get('machine_id')}</code> | Début : {i.get('started_at')}</p>", unsafe_allow_html=True)
                        with col_i2:
                            status = i.get('status')
                            if status == "COMPLETED":
                                st.markdown('<div style="text-align:right;"><span class="badge badge-completed">Terminé</span></div>', unsafe_allow_html=True)
                            else:
                                st.markdown(f'<div style="text-align:right;"><span class="badge badge-inprogress">En cours (Étape {i.get("current_stage_id")})</span></div>', unsafe_allow_html=True)
                        
                        st.write("---")
                        st.markdown("<p style='font-size:0.8rem;font-weight:600;color:#475569;margin-bottom:0.5rem;'>Historique d'Audit :</p>", unsafe_allow_html=True)
                        logs = i.get("logs", [])
                        if logs:
                            for log in logs:
                                time_str = log.get("timestamp")[11:19]
                                action_desc = log.get("action_description", "")
                                check_type = log.get("type", "Nominal")
                                details = log.get("details", "")
                                
                                if "override" in check_type.lower():
                                    st.markdown(f"""
                                    <div class="log-item log-warning">
                                        <i class="fa-solid fa-triangle-exclamation"></i> <b>[{time_str}] Dérogation manuelle :</b> {action_desc} ({details})
                                    </div>
                                    """, unsafe_allow_html=True)
                                else:
                                    st.markdown(f"""
                                    <div class="log-item log-success">
                                        <i class="fa-solid fa-circle-check"></i> <b>[{time_str}] Validation Vision :</b> {action_desc} ({details})
                                    </div>
                                    """, unsafe_allow_html=True)
                        else:
                            st.info("Aucune action n'a été enregistrée pour cette intervention.")
                        
                        if i.get("pdf_report_url"):
                            st.markdown(f"<div style='margin-top:1rem;'><a href='{i.get('pdf_report_url')}' target='_blank' style='text-decoration:none;color:#1D4ED8;font-size:0.82rem;font-weight:600;'><i class='fa-solid fa-file-pdf'></i> Télécharger le rapport d'audit officiel</a></div>", unsafe_allow_html=True)
            else:
                st.info("Aucune intervention enregistrée.")
        except Exception as e:
            st.error(f"Erreur de chargement des interventions : {e}")
    else:
        st.warning("Veuillez connecter Supabase dans l'onglet Diagnostics.")

elif menu == "Diagnostics & Paramètres":
    st.markdown("### Diagnostics & Paramètres Système")
    st.markdown("Gérez les identifiants d'API, les modèles de génération LLM, et le schéma de base de données.")

    col_diag1, col_diag2 = st.columns([1, 1])

    with col_diag1:
        st.markdown("<p style='font-weight:600;font-size:0.85rem;color:#0F172A;text-transform:uppercase;letter-spacing:0.5px;margin-bottom:0.8rem;'>Configuration des API</p>", unsafe_allow_html=True)
        
        or_key = st.text_input("Clé API OpenRouter", value=st.session_state["openrouter_key"], type="password")
        
        model_options = [
            "qwen/qwen-2.5-7b-instruct",
            "openrouter/free",
            "qwen/qwen-2.5-72b-instruct"
        ]
        current_model = st.session_state["openrouter_model"]
        if current_model not in model_options:
            model_options.append(current_model)
            
        or_model = st.selectbox("Modèle de génération de procédure", options=model_options, index=model_options.index(current_model))
        
        if st.button("Enregistrer les Paramètres OpenRouter"):
            update_env_file("OPENROUTER_API_KEY", or_key)
            update_env_file("OPENROUTER_MODEL", or_model)
            st.session_state["openrouter_key"] = or_key
            st.session_state["openrouter_model"] = or_model
            st.success("Paramètres OpenRouter enregistrés dans le fichier .env !")
            st.rerun()

        st.write("---")
        
        sb_url = st.text_input("URL Supabase Project", value=st.session_state["supabase_url"])
        sb_key = st.text_input("Clé Secrète API Supabase (Service Role)", value=st.session_state["supabase_key"], type="password")
        
        if st.button("Enregistrer les Paramètres Supabase"):
            update_env_file("SUPABASE_URL", sb_url)
            update_env_file("SUPABASE_KEY", sb_key)
            st.session_state["supabase_url"] = sb_url
            st.session_state["supabase_key"] = sb_key
            st.success("Paramètres Supabase enregistrés dans le fichier .env !")
            st.rerun()

    with col_diag2:
        st.markdown("<p style='font-weight:600;font-size:0.85rem;color:#0F172A;text-transform:uppercase;letter-spacing:0.5px;margin-bottom:0.8rem;'>Migration de Base de Données SQL</p>", unsafe_allow_html=True)
        st.markdown("Exécutez ce script SQL dans l'éditeur de votre console Supabase pour initialiser les tables et les règles de sécurité RLS.")
        
        sql_schema = """-- Script d'initialisation SmartLOTO
CREATE TABLE IF NOT EXISTS procedures (
    machine_id TEXT PRIMARY KEY,
    machine_name TEXT NOT NULL,
    created_by_hse TEXT NOT NULL,
    status TEXT DEFAULT 'PENDING' CHECK (status IN ('PENDING', 'APPROVED')),
    workflow_stages JSONB NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

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

-- Activation de Row Level Security (RLS)
ALTER TABLE procedures ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Allow public read access to procedures" ON procedures FOR SELECT USING (true);
CREATE POLICY "Allow public write access to procedures" ON procedures FOR INSERT WITH CHECK (true);
CREATE POLICY "Allow public update access to procedures" ON procedures FOR UPDATE USING (true);
CREATE POLICY "Allow public delete access to procedures" ON procedures FOR DELETE USING (true);

ALTER TABLE interventions ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Allow public read access to interventions" ON interventions FOR SELECT USING (true);
CREATE POLICY "Allow public write access to interventions" ON interventions FOR INSERT WITH CHECK (true);
CREATE POLICY "Allow public update access to interventions" ON interventions FOR UPDATE USING (true);
CREATE POLICY "Allow public delete access to interventions" ON interventions FOR DELETE USING (true);"""
        
        st.code(sql_schema, language="sql")
