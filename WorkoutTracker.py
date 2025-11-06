import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import json
from datetime import datetime, date, timedelta
from google.oauth2.service_account import Credentials
import gspread
import hashlib
import streamlit.components.v1 as components

# Configurazione pagina
st.set_page_config(page_title="Workout Tracker", page_icon="💪", layout="wide")

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
        st.error(f"Errore connessione Google Sheets: {e}")
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
        st.error(f"Errore accesso worksheet '{sheet_name}': {e}")
        return None

def save_template_to_sheets():
    """Salva il template su Google Sheets"""
    try:
        worksheet = get_worksheet("Template")
        if not worksheet:
            return False
        
        # Assicurati che esista l'header
        try:
            headers = worksheet.row_values(1)
            if not headers or headers[0] != 'Giorno':
                worksheet.update('A1', [['Giorno', 'Esercizio_JSON']])
        except:
            worksheet.update('A1', [['Giorno', 'Esercizio_JSON']])
        
        # Elimina tutte le righe esistenti (tranne header)
        all_records = worksheet.get_all_records()
        if all_records:
            worksheet.delete_rows(2, len(all_records) + 1)
        
        # Aggiungi i nuovi dati
        data = []
        for day, exercises in st.session_state.workout_template.items():
            if exercises:
                data.append([day, json.dumps(exercises, ensure_ascii=False)])
        
        if data:
            worksheet.append_rows(data)
        
        return True
    except Exception as e:
        st.error(f"Errore salvataggio template: {e}")
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
        st.error(f"Errore caricamento template: {e}")
        return False

def save_config_to_sheets():
    """Salva la configurazione (data inizio scheda)"""
    try:
        worksheet = get_worksheet("Config")
        if not worksheet:
            return False
        
        try:
            headers = worksheet.row_values(1)
            if not headers or headers[0] != 'Chiave':
                worksheet.update('A1', [['Chiave', 'Valore']])
        except:
            worksheet.update('A1', [['Chiave', 'Valore']])
        
        all_records = worksheet.get_all_records()
        row_to_update = None
        for i, record in enumerate(all_records, start=2):
            if record.get('Chiave') == 'data_inizio_scheda':
                row_to_update = i
                break
        
        if row_to_update:
            worksheet.update(f'A{row_to_update}:B{row_to_update}', 
                           [['data_inizio_scheda', st.session_state.data_inizio_scheda]])
        else:
            worksheet.append_row(['data_inizio_scheda', st.session_state.data_inizio_scheda])
        
        return True
        
def load_config_from_sheets():
    """Carica la configurazione"""
    try:
        worksheet = get_worksheet("Config")
        if not worksheet:
            return False
        
        records = worksheet.get_all_records()
        for record in records:
            if record.get('Chiave') == 'data_inizio_scheda':
                st.session_state.data_inizio_scheda = record.get('Valore', '')
        
        return True

def save_weight_calories_to_sheets():
    """Salva lo storico peso e calorie su Google Sheets"""
    try:
        worksheet = get_worksheet("WeightCalories")
        if not worksheet:
            return False
        
        try:
            headers = worksheet.row_values(1)
            if not headers or headers[0] != 'Data':
                worksheet.update('A1', [['Data', 'Peso', 'Calorie']])
        except:
            worksheet.update('A1', [['Data', 'Peso', 'Calorie']])
        
        all_records = worksheet.get_all_records()
        if all_records:
            worksheet.delete_rows(2, len(all_records) + 1)
        
        data = []
        for entry in st.session_state.weight_calories_history:
            data.append([
                entry['data'],
                entry['peso'],
                entry['calorie']
            ])
        
        if data:
            worksheet.append_rows(data)
        
        return True

def load_weight_calories_from_sheets():
    """Carica lo storico peso e calorie da Google Sheets"""
    try:
        worksheet = get_worksheet("WeightCalories")
        if not worksheet:
            return False
        
        records = worksheet.get_all_records()
        st.session_state.weight_calories_history = []
        
        for record in records:
            entry = {
                'data': record.get('Data'),
                'peso': record.get('Peso', ''),
                'calorie': record.get('Calorie', '')
            }
            st.session_state.weight_calories_history.append(entry)
        
        return True
        
def save_history_to_sheets():
    """Salva lo storico su Google Sheets"""
    try:
        worksheet = get_worksheet("History")
        if not worksheet:
            return False
        
        try:
            headers = worksheet.row_values(1)
            if not headers or headers[0] != 'Data':
                worksheet.update('A1', [['Data', 'Giorno', 'Settimana', 'Esercizi_JSON']])
        except:
            worksheet.update('A1', [['Data', 'Giorno', 'Settimana', 'Esercizi_JSON']])
        
        all_records = worksheet.get_all_records()
        if all_records:
            worksheet.delete_rows(2, len(all_records) + 1)
        
        data = []
        for session in st.session_state.workout_history:
            data.append([
                session['data'],
                session['giorno'],
                session.get('settimana', 1),
                json.dumps(session['esercizi'], ensure_ascii=False)
            ])
        
        if data:
            worksheet.append_rows(data)
        
        return True
        
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
                'settimana': record.get('Settimana', 1),
                'esercizi': json.loads(record.get('Esercizi_JSON', '[]'))
            }
            st.session_state.workout_history.append(session)
        
        return True

def save_all_data():
    """Salva tutto"""
    success = True
    success = save_template_to_sheets() and success
    success = save_history_to_sheets() and success
    success = save_config_to_sheets() and success
    success = save_weight_calories_to_sheets() and success
    return success

def load_all_data():
    """Carica tutto"""
    success = True
    success = load_template_from_sheets() and success
    success = load_history_from_sheets() and success
    success = load_config_from_sheets() and success
    success = load_weight_calories_from_sheets() and success
    return success

def calculate_current_week(start_date_str, current_date):
    """Calcola la settimana corrente (1-6) basandosi sulla data di inizio"""
    try:
        start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
        days_since_monday = start_date.weekday()
        monday_of_start_week = start_date - timedelta(days=days_since_monday)
        delta_days = (current_date - monday_of_start_week).days
        week_number = (delta_days // 7) % 6 + 1
        return week_number
    except:
        return 1

def init_session_state():
    """Inizializza la struttura dati"""
    
    if 'workout_template' not in st.session_state:
        st.session_state.workout_template = {day: [] for day in GIORNI}
    
    if 'workout_history' not in st.session_state:
        st.session_state.workout_history = []
    
    if 'data_inizio_scheda' not in st.session_state:
        st.session_state.data_inizio_scheda = "2025-11-03"

    if 'weight_calories_history' not in st.session_state:
        st.session_state.weight_calories_history = []
        
    # Carica dati all'avvio
    if 'data_loaded' not in st.session_state:
        load_all_data()
        st.session_state.data_loaded = True

def add_exercise_to_template(day):
    """Aggiunge un esercizio al template"""
    new_exercise = {
        'nome': '',
        'serie_settimane': ['', '', '', '', '', ''],  # 6 settimane
        'ripetizioni_settimane': ['', '', '', '', '', ''],  # 6 settimane
        'recupero': '',
        'note': ''
    }
    st.session_state.workout_template[day].append(new_exercise)

def delete_exercise_from_template(day, idx):
    """Elimina un esercizio dal template"""
    st.session_state.workout_template[day].pop(idx)

def save_workout_session(day, date_str, week_number, exercises_data):
    """Salva una sessione di allenamento completata"""
    # Rimuovi eventuali allenamenti già esistenti con la stessa data
    st.session_state.workout_history = [
        s for s in st.session_state.workout_history 
        if s['data'] != date_str
    ]
    
    # Aggiungi il nuovo allenamento
    session = {
        'data': date_str,
        'giorno': day,
        'settimana': week_number,
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
                    'settimana': session.get('settimana', 1),
                    'peso': ex.get('peso', ''),
                    'serie_target': ex.get('serie_target', ''),
                    'rip_target': ex.get('rip_target', ''),
                    'serie_eseguite': ex.get('serie_eseguite', ''),
                    'rip_eseguite': ex.get('rip_eseguite', ''),
                    'recupero': ex.get('recupero', ''),
                    'completato': ex.get('completato', False)
                })
    return sorted(history, key=lambda x: x['data'])

def get_last_weight_for_exercise(exercise_name):
    """Ottiene l'ultimo peso utilizzato per un esercizio"""
    history = get_exercise_history(exercise_name)
    if history:
        for h in reversed(history):
            if h['peso'] and h['peso'].strip():
                return h['peso']
    return None

# Inizializza
init_session_state()
    
st.sidebar.title("💪 Workout Tracker")
st.sidebar.markdown("---")

# Configurazione Data Inizio Scheda
st.sidebar.markdown("### ⚙️ Configurazione Scheda")
try:
    data_corrente = datetime.strptime(st.session_state.data_inizio_scheda, "%Y-%m-%d").date()
except:
    data_corrente = date(2025, 11, 3)  # Default: 3/11/2025

new_start_date = st.sidebar.date_input(
    "Data Inizio Scheda",
    value=data_corrente,
    help="La settimana 1 partirà dal lunedì di questa settimana"
)

if new_start_date.strftime("%Y-%m-%d") != st.session_state.data_inizio_scheda:
    st.session_state.data_inizio_scheda = new_start_date.strftime("%Y-%m-%d")
    save_config_to_sheets()

# Calcola il lunedì della settimana di inizio
days_since_monday = data_corrente.weekday()
monday_of_start = data_corrente - timedelta(days=days_since_monday)

# Mostra settimana corrente
current_week = calculate_current_week(st.session_state.data_inizio_scheda, date.today())
st.sidebar.info(f"📅 **Settimana corrente: {current_week}/6**")
st.sidebar.caption(f"Settimana 1 inizia: {monday_of_start.strftime('%d/%m/%Y')}")

st.sidebar.markdown("---")

menu = st.sidebar.radio("Menu", [
    "📋 Scheda Allenamento",
    "✍️ Registra Allenamento",
    "📅 Storico",
    "📈 Progressione",
    "⚖️ Peso e Calorie"
])

# Salva/Carica
st.sidebar.markdown("---")
col1, col2 = st.sidebar.columns(2)
if col1.button("💾 Salva"):
    with st.spinner("Salvataggio..."):
        if save_all_data():
            st.sidebar.success("✅ Salvato!")
        else:
            st.sidebar.error("❌ Errore")

if col2.button("🔄 Ricarica"):
    with st.spinner("Caricamento..."):
        if load_all_data():
            st.sidebar.success("✅ Caricato!")
            st.rerun()

# --- SCHEDA ALLENAMENTO (Template) ---
if menu == "📋 Scheda Allenamento":
    st.title("📋 Scheda Allenamento Settimanale (6 Settimane)")
    st.info("💡 Configura qui gli esercizi della tua scheda. Specifica serie e ripetizioni per ciascuna delle 6 settimane.")
    
    selected_day = st.selectbox("Seleziona Giorno", GIORNI)
    
    st.markdown("---")
    
    if st.button("➕ Aggiungi Esercizio"):
        add_exercise_to_template(selected_day)
        st.rerun()
    
    exercises = st.session_state.workout_template[selected_day]
    
    if not exercises:
        st.info(f"Nessun esercizio programmato per {selected_day}")
    else:
        for idx, exercise in enumerate(exercises):
            # Migrazione dati vecchi a nuovo formato
            if 'serie_settimane' not in exercise:
                old_serie = exercise.get('serie', '')
                old_rip = exercise.get('ripetizioni', '')
                exercise['serie_settimane'] = [old_serie] * 6
                exercise['ripetizioni_settimane'] = [old_rip] * 6
            
            with st.expander(f"🏋️ {exercise.get('nome', '') or f'Esercizio {idx+1}'}", expanded=True):
                col1, col2 = st.columns([3, 1])
                
                with col1:
                    exercise['nome'] = st.text_input(
                        "Nome esercizio",
                        value=exercise.get('nome', ''),
                        key=f"tpl_nome_{selected_day}_{idx}"
                    )
                
                with col2:
                    if st.button("🗑️ Elimina", key=f"tpl_del_{selected_day}_{idx}"):
                        delete_exercise_from_template(selected_day, idx)
                        st.rerun()
                
                st.markdown("**Serie e Ripetizioni per settimana:**")
                
                # Crea 3 righe x 2 colonne per le 6 settimane
                for row in range(3):
                    cols = st.columns(2)
                    for col_idx in range(2):
                        week_num = row * 2 + col_idx
                        with cols[col_idx]:
                            st.markdown(f"*Settimana {week_num + 1}*")
                            subcol1, subcol2 = st.columns(2)
                            with subcol1:
                                exercise['serie_settimane'][week_num] = st.text_input(
                                    "Serie",
                                    value=exercise['serie_settimane'][week_num],
                                    placeholder="5",
                                    key=f"tpl_serie_{selected_day}_{idx}_w{week_num}",
                                    label_visibility="collapsed"
                                )
                            with subcol2:
                                exercise['ripetizioni_settimane'][week_num] = st.text_input(
                                    "Ripetizioni",
                                    value=exercise['ripetizioni_settimane'][week_num],
                                    placeholder="4",
                                    key=f"tpl_rip_{selected_day}_{idx}_w{week_num}",
                                    label_visibility="collapsed"
                                )
                
                st.markdown("**Recupero e Note:**")
                col3, col4 = st.columns(2)
                with col3:
                    exercise['recupero'] = st.text_input(
                        "Recupero",
                        value=exercise.get('recupero', ''),
                        placeholder="2min",
                        key=f"tpl_rec_{selected_day}_{idx}"
                    )
                
                exercise['note'] = st.text_area(
                    "Note/Varianti",
                    value=exercise.get('note', ''),
                    height=60,
                    key=f"tpl_note_{selected_day}_{idx}"
                )

# --- REGISTRA ALLENAMENTO ---
elif menu == "✍️ Registra Allenamento":
    st.title("✍️ Registra Allenamento")
    
    col1, col2 = st.columns(2)
    with col1:
        selected_day = st.selectbox("Giorno", GIORNI)
    with col2:
        workout_date = st.date_input("Data", value=date.today())
    
    # Calcola la settimana per la data selezionata
    week_number = calculate_current_week(st.session_state.data_inizio_scheda, workout_date)
    st.info(f"📅 Questo allenamento è della **Settimana {week_number}/6**")
    
    st.markdown("---")
    
    template_exercises = st.session_state.workout_template[selected_day]
    
    if not template_exercises:
        st.warning(f"⚠️ Nessun esercizio configurato per {selected_day}. Vai in 'Scheda Allenamento' per configurare gli esercizi.")
    else:
        # Carica gli esercizi già salvati per questa data (se esistono)
        existing_session = next((s for s in st.session_state.workout_history if s['data'] == workout_date.strftime("%Y-%m-%d") and s['giorno'] == selected_day), None)
        existing_exercises = {ex['nome']: ex for ex in existing_session['esercizi']} if existing_session else {}
        
        for idx, template_ex in enumerate(template_exercises):
            # Migrazione dati vecchi
            if 'serie_settimane' not in template_ex:
                old_serie = template_ex.get('serie', '')
                old_rip = template_ex.get('ripetizioni', '')
                template_ex['serie_settimane'] = [old_serie] * 6
                template_ex['ripetizioni_settimane'] = [old_rip] * 6
            
            # Ottieni i valori per la settimana corrente (indice 0-5)
            week_idx = week_number - 1
            serie_target = template_ex['serie_settimane'][week_idx]
            rip_target = template_ex['ripetizioni_settimane'][week_idx]
            
            # Recupera dati esistenti se presenti
            existing_ex = existing_exercises.get(template_ex['nome'], {})
            
            with st.form(f"workout_form_{selected_day}_{workout_date}_{idx}"):
                st.subheader(f"🏋️ {template_ex['nome']}")
                note_text = template_ex.get('note', '').strip() or "Nessuna"
                st.caption(f"**Settimana {week_number}** - Target: {serie_target}x{rip_target} - Recupero: {template_ex['recupero']} - Note: {note_text}")
                
                col1, col2, col3 = st.columns(3)
                
                last_weight = get_last_weight_for_exercise(template_ex['nome'])
                peso_placeholder = last_weight if last_weight else "Da determinare"
                
                with col1:
                    peso = st.text_input(
                        "Peso utilizzato",
                        value=existing_ex.get('peso', ''),
                        placeholder=peso_placeholder,
                        key=f"reg_peso_{idx}"
                    )
                
                with col2:
                    serie_fatte = st.text_input(
                        "Serie completate",
                        value=existing_ex.get('serie_eseguite', serie_target),
                        key=f"reg_serie_{idx}"
                    )
                
                with col3:
                    rip_fatte = st.text_input(
                        "Ripetizioni per serie",
                        value=existing_ex.get('rip_eseguite', ''),
                        placeholder="4,4,4,4,4",
                        key=f"reg_rip_{idx}"
                    )
                
                completato = st.checkbox(
                    "✅ Obiettivo raggiunto (serie e ripetizioni completate)",
                    value=existing_ex.get('completato', False),
                    key=f"reg_comp_{idx}"
                )
                
                submitted = st.form_submit_button("💾 Salva Esercizio", use_container_width=True)
                
                if submitted:
                    # Crea o aggiorna la sessione di allenamento
                    exercise_data = {
                        'nome': template_ex['nome'],
                        'serie_target': serie_target,
                        'rip_target': rip_target,
                        'recupero': template_ex['recupero'],
                        'peso': peso,
                        'serie_eseguite': serie_fatte,
                        'rip_eseguite': rip_fatte,
                        'completato': completato
                    }
                    
                    # Trova o crea la sessione per questa data
                    date_str = workout_date.strftime("%Y-%m-%d")
                    session_idx = next((i for i, s in enumerate(st.session_state.workout_history) if s['data'] == date_str and s['giorno'] == selected_day), None)
                    
                    if session_idx is not None:
                        # Aggiorna esercizio esistente o aggiungine uno nuovo
                        ex_idx = next((i for i, ex in enumerate(st.session_state.workout_history[session_idx]['esercizi']) if ex['nome'] == template_ex['nome']), None)
                        if ex_idx is not None:
                            st.session_state.workout_history[session_idx]['esercizi'][ex_idx] = exercise_data
                        else:
                            st.session_state.workout_history[session_idx]['esercizi'].append(exercise_data)
                    else:
                        # Crea nuova sessione
                        new_session = {
                            'data': date_str,
                            'giorno': selected_day,
                            'settimana': week_number,
                            'esercizi': [exercise_data]
                        }
                        st.session_state.workout_history.append(new_session)
                    
                    save_all_data()
                    st.success(f"✅ Esercizio '{template_ex['nome']}' salvato!")
                    st.rerun()
            
            st.markdown("---")

# --- STORICO ---
elif menu == "📅 Storico":
    st.title("📅 Storico Allenamenti")
    
    if not st.session_state.workout_history:
        st.info("Nessun allenamento registrato. Vai in 'Registra Allenamento' per iniziare!")
    else:
        col1, col2 = st.columns(2)
        with col1:
            giorni_disponibili = ["Tutti"] + sorted(list(set([s['giorno'] for s in st.session_state.workout_history])))
            filtro_giorno = st.selectbox("Filtra per giorno", giorni_disponibili)
        
        with col2:
            settimane_disponibili = ["Tutte"] + [f"Settimana {i}" for i in range(1, 7)]
            filtro_settimana = st.selectbox("Filtra per settimana", settimane_disponibili)
        
        history = st.session_state.workout_history
        if filtro_giorno != "Tutti":
            history = [s for s in history if s['giorno'] == filtro_giorno]
        
        if filtro_settimana != "Tutte":
            week_num = int(filtro_settimana.split()[1])
            history = [s for s in history if s.get('settimana', 1) == week_num]
        
        history = sorted(history, key=lambda x: x['data'], reverse=True)
        
        for session in history:
            week_label = session.get('settimana', 1)
            with st.expander(f"📆 {session['data']} - {session['giorno']} (Settimana {week_label})"):
                data = []
                for ex in session['esercizi']:
                    status = "✅" if ex['completato'] else "❌"
                    data.append({
                        "Status": status,
                        "Esercizio": ex['nome'],
                        "Target": f"{ex['serie_target']}x{ex['rip_target']}",
                        "Eseguito": f"{ex['serie_eseguite']}x{ex['rip_eseguite']}",
                        "Peso": ex['peso'],
                        "Recupero": ex['recupero']
                    })
                
                df = pd.DataFrame(data)
                st.dataframe(df, use_container_width=True, hide_index=True)

# --- PROGRESSIONE ---
elif menu == "📈 Progressione":
    st.title("📈 Progressione Esercizi")
    
    all_exercises = set()
    for day in GIORNI:
        for ex in st.session_state.workout_template[day]:
            if ex.get('nome'):
                all_exercises.add(ex['nome'])
    
    if not all_exercises:
        st.info("Nessun esercizio nella scheda. Vai in 'Scheda Allenamento' per configurare gli esercizi.")
    else:
        selected_exercise = st.selectbox("Seleziona Esercizio", sorted(all_exercises))
        
        history = get_exercise_history(selected_exercise)
        
        if not history:
            st.warning(f"Nessun allenamento registrato per '{selected_exercise}'")
        else:
            dates = [h['data'] for h in history]
            weights = []
            completions = []
            weeks = [h.get('settimana', 1) for h in history]
            
            for h in history:
                try:
                    peso_val = float(h['peso'].replace('kg', '').replace('Kg', '').strip())
                    weights.append(peso_val)
                except:
                    weights.append(None)
                
                completions.append(1 if h['completato'] else 0)
            
            st.subheader("📊 Progressione Peso")
            fig_weight = go.Figure()
            
            valid_weights = [(d, w, wk) for d, w, wk in zip(dates, weights, weeks) if w is not None]
            if valid_weights:
                valid_dates, valid_weight_values, valid_weeks = zip(*valid_weights)
                
                # Colora i punti in base alla settimana
                colors = [f'rgb({40 + wk*30}, {100 + wk*20}, {200 - wk*20})' for wk in valid_weeks]
                
                fig_weight.add_trace(go.Scatter(
                    x=valid_dates,
                    y=valid_weight_values,
                    mode='lines+markers',
                    name='Peso',
                    line=dict(color='#1f77b4', width=3),
                    marker=dict(size=10, color=colors),
                    text=[f"Settimana {wk}" for wk in valid_weeks],
                    hovertemplate='<b>%{x}</b><br>Peso: %{y:.1f} kg<br>%{text}<extra></extra>'
                ))
                
                fig_weight.update_layout(
                    xaxis_title="Data",
                    yaxis_title="Peso (kg)",
                    hovermode='x unified',
                    template='plotly_white',
                    height=400
                )
                
                st.plotly_chart(fig_weight, use_container_width=True)
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Peso Iniziale", f"{valid_weight_values[0]:.1f} kg")
                with col2:
                    st.metric("Peso Attuale", f"{valid_weight_values[-1]:.1f} kg")
                with col3:
                    diff = valid_weight_values[-1] - valid_weight_values[0]
                    st.metric("Incremento", f"{diff:+.1f} kg")
            else:
                st.info("Nessun dato di peso registrato")
            
            st.subheader("✅ Tasso di Completamento")
            fig_comp = go.Figure()
            
            fig_comp.add_trace(go.Bar(
                x=dates,
                y=completions,
                marker_color=['#2ecc71' if c == 1 else '#e74c3c' for c in completions],
                name='Completato',
                text=[f"S{wk}" for wk in weeks],
                textposition='outside'
            ))
            
            fig_comp.update_layout(
                xaxis_title="Data",
                yaxis_title="Completato",
                yaxis=dict(tickmode='linear', tick0=0, dtick=1),
                template='plotly_white',
                height=300,
                showlegend=False
            )
            
            st.plotly_chart(fig_comp, use_container_width=True)
            
            st.subheader("📋 Dettagli Allenamenti")
            detail_data = []
            for h in history:
                detail_data.append({
                    "Data": h['data'],
                    "Settimana": h.get('settimana', 1),
                    "Giorno": h['giorno'],
                    "Target": f"{h['serie_target']}x{h['rip_target']}",
                    "Eseguito": f"{h['serie_eseguite']}x{h['rip_eseguite']}",
                    "Peso": h['peso'],
                    "Recupero": h['recupero'],
                    "✅": "Sì" if h['completato'] else "No"
                })
            
            df = pd.DataFrame(detail_data)
            st.dataframe(df, use_container_width=True, hide_index=True)

    # --- PESO E CALORIE ---
elif menu == "⚖️ Peso e Calorie":
    st.title("⚖️ Storico Peso e Calorie")
    
    st.markdown("### 📝 Inserisci Nuovo Dato")
    
    with st.form("weight_calories_form"):
        col1, col2, col3 = st.columns(3)
        
        with col1:
            entry_date = st.date_input("Data", value=date.today())
        
        with col2:
            peso = st.number_input("Peso (kg)", min_value=0.0, max_value=300.0, step=0.1, format="%.1f")
        
        with col3:
            calorie = st.number_input("Calorie", min_value=0, max_value=10000, step=50)
        
        submitted = st.form_submit_button("💾 Salva", use_container_width=True)
        
        if submitted:
            date_str = entry_date.strftime("%Y-%m-%d")
            
            # Rimuovi eventuale dato già esistente per questa data
            st.session_state.weight_calories_history = [
                e for e in st.session_state.weight_calories_history 
                if e['data'] != date_str
            ]
            
            # Aggiungi nuovo dato
            new_entry = {
                'data': date_str,
                'peso': str(peso) if peso > 0 else '',
                'calorie': str(calorie) if calorie > 0 else ''
            }
            st.session_state.weight_calories_history.append(new_entry)
            
            save_all_data()
            st.success("✅ Dati salvati!")
            st.rerun()
    
    st.markdown("---")
    
    if not st.session_state.weight_calories_history:
        st.info("Nessun dato registrato. Inserisci peso e calorie per iniziare!")
    else:
        # Ordina per data
        history = sorted(st.session_state.weight_calories_history, key=lambda x: x['data'])
        
        # Prepara dati per i grafici
        dates = [h['data'] for h in history]
        weights = []
        calories = []
        
        for h in history:
            try:
                weights.append(float(h['peso']) if h['peso'] else None)
            except:
                weights.append(None)
            
            try:
                calories.append(int(h['calorie']) if h['calorie'] else None)
            except:
                calories.append(None)
        
        # Grafico Peso
        st.subheader("📊 Andamento Peso")
        fig_weight = go.Figure()
        
        valid_weights = [(d, w) for d, w in zip(dates, weights) if w is not None]
        if valid_weights:
            valid_dates_w, valid_weight_values = zip(*valid_weights)
            
            fig_weight.add_trace(go.Scatter(
                x=valid_dates_w,
                y=valid_weight_values,
                mode='lines+markers',
                name='Peso',
                line=dict(color='#3498db', width=3),
                marker=dict(size=10),
                hovertemplate='<b>%{x}</b><br>Peso: %{y:.1f} kg<extra></extra>'
            ))
            
            fig_weight.update_layout(
                xaxis_title="Data",
                yaxis_title="Peso (kg)",
                hovermode='x unified',
                template='plotly_white',
                height=400
            )
            
            st.plotly_chart(fig_weight, use_container_width=True)
            
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Peso Iniziale", f"{valid_weight_values[0]:.1f} kg")
            with col2:
                st.metric("Peso Attuale", f"{valid_weight_values[-1]:.1f} kg")
            with col3:
                diff = valid_weight_values[-1] - valid_weight_values[0]
                st.metric("Variazione", f"{diff:+.1f} kg")
            with col4:
                avg = sum(valid_weight_values) / len(valid_weight_values)
                st.metric("Media", f"{avg:.1f} kg")
        else:
            st.info("Nessun dato di peso registrato")
        
        st.markdown("---")
        
        # Grafico Calorie
        st.subheader("🍽️ Andamento Calorie")
        fig_calories = go.Figure()
        
        valid_calories = [(d, c) for d, c in zip(dates, calories) if c is not None]
        if valid_calories:
            valid_dates_c, valid_calorie_values = zip(*valid_calories)
            
            fig_calories.add_trace(go.Scatter(
                x=valid_dates_c,
                y=valid_calorie_values,
                mode='lines+markers',
                name='Calorie',
                line=dict(color='#e74c3c', width=3),
                marker=dict(size=10),
                fill='tozeroy',
                fillcolor='rgba(231, 76, 60, 0.2)',
                hovertemplate='<b>%{x}</b><br>Calorie: %{y}<extra></extra>'
            ))
            
            fig_calories.update_layout(
                xaxis_title="Data",
                yaxis_title="Calorie",
                hovermode='x unified',
                template='plotly_white',
                height=400
            )
            
            st.plotly_chart(fig_calories, use_container_width=True)
            
            col1, col2, col3 = st.columns(3)
            with col1:
                avg_cal = sum(valid_calorie_values) / len(valid_calorie_values)
                st.metric("Media Calorie", f"{avg_cal:.0f}")
            with col2:
                st.metric("Minimo", f"{min(valid_calorie_values)}")
            with col3:
                st.metric("Massimo", f"{max(valid_calorie_values)}")
        else:
            st.info("Nessun dato di calorie registrato")
        
        st.markdown("---")
        
        # Tabella dettagli
        st.subheader("📋 Dettagli")
        detail_data = []
        for h in reversed(history):  # Mostra dal più recente
            detail_data.append({
                "Data": h['data'],
                "Peso (kg)": h['peso'] if h['peso'] else '-',
                "Calorie": h['calorie'] if h['calorie'] else '-'
            })
        
        df = pd.DataFrame(detail_data)
        st.dataframe(df, use_container_width=True, hide_index=True)
        
        # Pulsante per eliminare tutti i dati
        st.markdown("---")
        if st.button("🗑️ Elimina Tutti i Dati Peso/Calorie", type="secondary"):
            if st.session_state.get('confirm_delete_wc', False):
                st.session_state.weight_calories_history = []
                save_all_data()
                st.session_state.confirm_delete_wc = False
                st.success("✅ Tutti i dati sono stati eliminati!")
                st.rerun()
            else:
                st.session_state.confirm_delete_wc = True
                st.warning("⚠️ Clicca di nuovo per confermare l'eliminazione")
                st.rerun()

st.sidebar.markdown("---")
st.sidebar.markdown("💪 **Workout Tracker v3.0**")
