import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import json
from datetime import datetime, date
from google.oauth2.service_account import Credentials
import gspread

# Configurazione pagina per mobile
st.set_page_config(
    page_title="Workout Tracker", 
    page_icon="💪", 
    layout="wide",
    initial_sidebar_state="collapsed"  # Sidebar chiusa su mobile
)

# CSS personalizzato per mobile
st.markdown("""
<style>
    /* Ottimizzazione mobile */
    @media (max-width: 768px) {
        .block-container {
            padding: 1rem 0.5rem;
        }
        h1 {
            font-size: 1.5rem !important;
        }
        h2 {
            font-size: 1.2rem !important;
        }
        h3 {
            font-size: 1rem !important;
        }
        .stButton button {
            width: 100%;
            padding: 0.75rem;
            font-size: 1rem;
        }
        .stSelectbox, .stTextInput, .stTextArea {
            margin-bottom: 0.5rem;
        }
        /* Expander più compatti */
        .streamlit-expanderHeader {
            font-size: 0.9rem;
            padding: 0.5rem;
        }
        /* Riduci padding dei form */
        .stForm {
            padding: 0.5rem;
        }
    }
    
    /* Pulsanti colorati */
    .stButton button {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border: none;
        border-radius: 8px;
        font-weight: 600;
    }
    
    /* Card per esercizi */
    .exercise-card {
        background: white;
        border-radius: 10px;
        padding: 1rem;
        margin-bottom: 1rem;
        box-shadow: 0 2px 8px rgba(0,0,0,0.1);
    }
</style>
""", unsafe_allow_html=True)

# Giorni della settimana
GIORNI = ["Lunedì", "Martedì", "Mercoledì", "Giovedì", "Venerdì", "Sabato", "Domenica"]

# --- CONNESSIONE GOOGLE SHEETS ---
@st.cache_resource
def get_gsheet_client():
    """Connessione a Google Sheets"""
    try:
        credentials = Credentials.from_service_account_info(
            st.secrets["gcp_service_account"],
            scopes=[
                "https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive"
            ]
        )
        return gspread.authorize(credentials)
    except Exception as e:
        st.error(f"❌ Errore connessione: {e}")
        return None

def get_worksheet(sheet_name):
    """Ottiene un worksheet specifico"""
    try:
        client = get_gsheet_client()
        if not client:
            return None
        
        spreadsheet_id = st.secrets.get("spreadsheet_id", "")
        spreadsheet_url = st.secrets.get("spreadsheet_url", "")
        
        if spreadsheet_url:
            spreadsheet = client.open_by_url(spreadsheet_url)
        elif spreadsheet_id:
            spreadsheet = client.open_by_key(spreadsheet_id)
        else:
            spreadsheet = client.open(st.secrets["spreadsheet_name"])
        
        try:
            worksheet = spreadsheet.worksheet(sheet_name)
        except gspread.exceptions.WorksheetNotFound:
            worksheet = spreadsheet.add_worksheet(title=sheet_name, rows=1000, cols=20)
        
        return worksheet
    except Exception as e:
        st.error(f"❌ Errore worksheet '{sheet_name}': {e}")
        return None

def save_template_to_sheets():
    """Salva il template su Google Sheets"""
    try:
        worksheet = get_worksheet("Template")
        if not worksheet:
            return False
        
        worksheet.clear()
        worksheet.update('A1', [['Giorno', 'Esercizio_JSON']])
        
        data = []
        for day, exercises in st.session_state.workout_template.items():
            if exercises:
                data.append([day, json.dumps(exercises, ensure_ascii=False)])
        
        if data:
            worksheet.update(f'A2:B{len(data)+1}', data)
        
        return True
    except Exception as e:
        st.error(f"❌ Errore salvataggio: {e}")
        return False

def load_template_from_sheets():
    """Carica il template da Google Sheets"""
    try:
        worksheet = get_worksheet("Template")
        if not worksheet:
            return False
        
        records = worksheet.get_all_records()
        st.session_state.workout_template = {day: [] for day in GIORNI}
        
        for record in records:
            day = record.get('Giorno')
            exercises_json = record.get('Esercizio_JSON')
            if day and exercises_json:
                st.session_state.workout_template[day] = json.loads(exercises_json)
        
        return True
    except Exception as e:
        st.error(f"❌ Errore caricamento: {e}")
        return False

def save_history_to_sheets():
    """Salva lo storico su Google Sheets"""
    try:
        worksheet = get_worksheet("History")
        if not worksheet:
            return False
        
        worksheet.clear()
        worksheet.update('A1', [['Data', 'Giorno', 'Esercizi_JSON']])
        
        data = []
        for session in st.session_state.workout_history:
            data.append([
                session['data'],
                session['giorno'],
                json.dumps(session['esercizi'], ensure_ascii=False)
            ])
        
        if data:
            worksheet.update(f'A2:C{len(data)+1}', data)
        
        return True
    except Exception as e:
        st.error(f"❌ Errore salvataggio: {e}")
        return False

def load_history_from_sheets():
    """Carica lo storico da Google Sheets"""
    try:
        worksheet = get_worksheet("History")
        if not worksheet:
            return False
        
        records = worksheet.get_all_records()
        st.session_state.workout_history = []
        
        for record in records:
            session = {
                'data': record.get('Data'),
                'giorno': record.get('Giorno'),
                'esercizi': json.loads(record.get('Esercizi_JSON', '[]'))
            }
            st.session_state.workout_history.append(session)
        
        return True
    except Exception as e:
        st.error(f"❌ Errore caricamento: {e}")
        return False

def save_all_data():
    """Salva tutto"""
    success = save_template_to_sheets() and save_history_to_sheets()
    return success

def load_all_data():
    """Carica tutto"""
    success = load_template_from_sheets() and load_history_from_sheets()
    return success

def init_session_state():
    """Inizializza la struttura dati"""
    if 'workout_template' not in st.session_state:
        st.session_state.workout_template = {day: [] for day in GIORNI}
    
    if 'workout_history' not in st.session_state:
        st.session_state.workout_history = []
    
    if 'data_loaded' not in st.session_state:
        load_all_data()
        st.session_state.data_loaded = True

def add_exercise_to_template(day):
    """Aggiunge un esercizio al template"""
    new_exercise = {
        'nome': '',
        'serie': '',
        'ripetizioni': '',
        'recupero': '',
        'note': ''
    }
    st.session_state.workout_template[day].append(new_exercise)

def delete_exercise_from_template(day, idx):
    """Elimina un esercizio dal template"""
    st.session_state.workout_template[day].pop(idx)

def save_workout_session(day, date_str, exercises_data):
    """Salva una sessione di allenamento completata"""
    session = {
        'data': date_str,
        'giorno': day,
        'esercizi': exercises_data
    }
    st.session_state.workout_history.append(session)

def get_exercise_history(exercise_name):
    """Ottiene lo storico di un esercizio specifico"""
    history = []
    for session in st.session_state.workout_history:
        for ex in session['esercizi']:
            if ex['nome'].lower() == exercise_name.lower():
                history.append({
                    'data': session['data'],
                    'giorno': session['giorno'],
                    'peso': ex.get('peso', ''),
                    'serie_target': ex.get('serie_target', ''),
                    'rip_target': ex.get('rip_target', ''),
                    'serie_eseguite': ex.get('serie_eseguite', ''),
                    'rip_eseguite': ex.get('rip_eseguite', ''),
                    'recupero': ex.get('recupero', ''),
                    'completato': ex.get('completato', False)
                })
    return sorted(history, key=lambda x: x['data'])

# Inizializza
init_session_state()

# Header compatto
col1, col2, col3 = st.columns([1, 2, 1])
with col2:
    st.title("💪 Workout")

# Menu principale con tabs (più mobile-friendly)
tab1, tab2, tab3, tab4 = st.tabs(["📋 Scheda", "✍️ Registra", "📅 Storico", "📈 Progressi"])

# Pulsanti salva/carica sempre visibili in alto
col_save, col_load = st.columns(2)
with col_save:
    if st.button("💾 Salva Dati", use_container_width=True):
        with st.spinner("Salvataggio..."):
            if save_all_data():
                st.success("✅ Salvato!")
            else:
                st.error("❌ Errore")

with col_load:
    if st.button("🔄 Ricarica Dati", use_container_width=True):
        with st.spinner("Caricamento..."):
            if load_all_data():
                st.success("✅ Caricato!")
                st.rerun()

st.divider()

# --- TAB 1: SCHEDA ALLENAMENTO ---
with tab1:
    st.subheader("📋 Scheda Settimanale")
    
    selected_day = st.selectbox("Giorno", GIORNI, key="day_template")
    
    if st.button("➕ Nuovo Esercizio", use_container_width=True, key="add_ex_btn"):
        add_exercise_to_template(selected_day)
        st.rerun()
    
    exercises = st.session_state.workout_template[selected_day]
    
    if not exercises:
        st.info(f"💡 Nessun esercizio per {selected_day}")
    else:
        for idx, exercise in enumerate(exercises):
            with st.expander(f"🏋️ {exercise.get('nome', '') or f'Esercizio {idx+1}'}", expanded=False):
                exercise['nome'] = st.text_input(
                    "Nome",
                    value=exercise.get('nome', ''),
                    key=f"tpl_n_{selected_day}_{idx}"
                )
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    exercise['serie'] = st.text_input(
                        "Serie",
                        value=exercise.get('serie', ''),
                        key=f"tpl_s_{selected_day}_{idx}"
                    )
                with col2:
                    exercise['ripetizioni'] = st.text_input(
                        "Rip.",
                        value=exercise.get('ripetizioni', ''),
                        key=f"tpl_r_{selected_day}_{idx}"
                    )
                with col3:
                    exercise['recupero'] = st.text_input(
                        "Rec.",
                        value=exercise.get('recupero', ''),
                        key=f"tpl_rec_{selected_day}_{idx}"
                    )
                
                exercise['note'] = st.text_area(
                    "Note",
                    value=exercise.get('note', ''),
                    height=60,
                    key=f"tpl_note_{selected_day}_{idx}"
                )
                
                if st.button("🗑️ Elimina", key=f"tpl_del_{selected_day}_{idx}", use_container_width=True):
                    delete_exercise_from_template(selected_day, idx)
                    st.rerun()

# --- TAB 2: REGISTRA ALLENAMENTO ---
with tab2:
    st.subheader("✍️ Nuovo Allenamento")
    
    col1, col2 = st.columns(2)
    with col1:
        selected_day_reg = st.selectbox("Giorno", GIORNI, key="day_reg")
    with col2:
        workout_date = st.date_input("Data", value=date.today())
    
    template_exercises = st.session_state.workout_template[selected_day_reg]
    
    if not template_exercises:
        st.warning(f"⚠️ Configura prima gli esercizi per {selected_day_reg}")
    else:
        with st.form(f"workout_form_{selected_day_reg}"):
            exercises_data = []
            
            for idx, template_ex in enumerate(template_exercises):
                st.markdown(f"### 🏋️ {template_ex['nome']}")
                st.caption(f"Target: {template_ex['serie']}×{template_ex['ripetizioni']} | Rec: {template_ex['recupero']}")
                
                peso = st.text_input(
                    "Peso",
                    placeholder="65kg",
                    key=f"reg_p_{idx}"
                )
                
                col1, col2 = st.columns(2)
                with col1:
                    serie_fatte = st.text_input(
                        "Serie",
                        value=template_ex['serie'],
                        key=f"reg_s_{idx}"
                    )
                with col2:
                    rip_fatte = st.text_input(
                        "Ripetizioni",
                        placeholder="4,4,4,4",
                        key=f"reg_r_{idx}"
                    )
                
                completato = st.checkbox(
                    "✅ Obiettivo raggiunto",
                    key=f"reg_c_{idx}"
                )
                
                exercises_data.append({
                    'nome': template_ex['nome'],
                    'serie_target': template_ex['serie'],
                    'rip_target': template_ex['ripetizioni'],
                    'recupero': template_ex['recupero'],
                    'peso': peso,
                    'serie_eseguite': serie_fatte,
                    'rip_eseguite': rip_fatte,
                    'completato': completato
                })
                
                st.divider()
            
            if st.form_submit_button("💾 Salva Allenamento", use_container_width=True):
                save_workout_session(selected_day_reg, workout_date.strftime("%Y-%m-%d"), exercises_data)
                save_all_data()
                st.success(f"✅ Salvato!")
                st.balloons()

# --- TAB 3: STORICO ---
with tab3:
    st.subheader("📅 Storico")
    
    if not st.session_state.workout_history:
        st.info("💡 Nessun allenamento registrato")
    else:
        giorni_disponibili = ["Tutti"] + sorted(list(set([s['giorno'] for s in st.session_state.workout_history])))
        filtro_giorno = st.selectbox("Filtra", giorni_disponibili)
        
        history = st.session_state.workout_history
        if filtro_giorno != "Tutti":
            history = [s for s in history if s['giorno'] == filtro_giorno]
        
        history = sorted(history, key=lambda x: x['data'], reverse=True)
        
        for session in history[:10]:  # Mostra solo ultimi 10 su mobile
            with st.expander(f"📆 {session['data']} - {session['giorno']}", expanded=False):
                for ex in session['esercizi']:
                    status = "✅" if ex['completato'] else "❌"
                    st.markdown(f"**{status} {ex['nome']}**")
                    st.caption(f"Target: {ex['serie_target']}×{ex['rip_target']} | Fatto: {ex['serie_eseguite']}×{ex['rip_eseguite']} | {ex['peso']}")
                    st.divider()

# --- TAB 4: PROGRESSIONE ---
with tab4:
    st.subheader("📈 Progressione")
    
    all_exercises = set()
    for day in GIORNI:
        for ex in st.session_state.workout_template[day]:
            if ex.get('nome'):
                all_exercises.add(ex['nome'])
    
    if not all_exercises:
        st.info("💡 Configura prima la scheda")
    else:
        selected_exercise = st.selectbox("Esercizio", sorted(all_exercises))
        
        history = get_exercise_history(selected_exercise)
        
        if not history:
            st.warning(f"⚠️ Nessun dato per '{selected_exercise}'")
        else:
            # Grafico peso
            dates = [h['data'] for h in history]
            weights = []
            
            for h in history:
                try:
                    peso_val = float(h['peso'].replace('kg', '').replace('Kg', '').strip())
                    weights.append(peso_val)
                except:
                    weights.append(None)
            
            valid_weights = [(d, w) for d, w in zip(dates, weights) if w is not None]
            
            if valid_weights:
                valid_dates, valid_weight_values = zip(*valid_weights)
                
                fig = go.Figure()
                fig.add_trace(go.Scatter(
                    x=valid_dates,
                    y=valid_weight_values,
                    mode='lines+markers',
                    line=dict(color='#667eea', width=3),
                    marker=dict(size=8)
                ))
                
                fig.update_layout(
                    xaxis_title="Data",
                    yaxis_title="Peso (kg)",
                    template='plotly_white',
                    height=300,
                    margin=dict(l=20, r=20, t=20, b=20)
                )
                
                st.plotly_chart(fig, use_container_width=True)
                
                # Metriche compatte
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Inizio", f"{valid_weight_values[0]:.0f}kg")
                with col2:
                    st.metric("Oggi", f"{valid_weight_values[-1]:.0f}kg")
                with col3:
                    diff = valid_weight_values[-1] - valid_weight_values[0]
                    st.metric("Δ", f"{diff:+.0f}kg")
            
            # Dettagli ultimi 5
            st.markdown("### 📋 Ultimi 5 allenamenti")
            for h in history[-5:]:
                status = "✅" if h['completato'] else "❌"
                st.markdown(f"**{status} {h['data']}** - {h['peso']} | {h['serie_eseguite']}×{h['rip_eseguite']}")

st.markdown("---")
st.caption("💪 Workout Tracker v2.1 Mobile")
