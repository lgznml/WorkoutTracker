import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import json
from datetime import datetime, date
from google.oauth2.service_account import Credentials
import gspread

# Configurazione pagina
st.set_page_config(page_title="Workout Tracker", page_icon="💪", layout="wide")

# Giorni della settimana
GIORNI = ["Lunedì", "Martedì", "Mercoledì", "Giovedì", "Venerdì", "Sabato", "Domenica"]

# --- CONNESSIONE GOOGLE SHEETS ---
@st.cache_resource
def get_gsheet_client():
    """Connessione a Google Sheets"""
    try:
        # Usa le credenziali dai secrets di Streamlit
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
        
        # Apri il foglio tramite URL o ID
        spreadsheet_id = st.secrets.get("spreadsheet_id", "")
        spreadsheet_url = st.secrets.get("spreadsheet_url", "")
        
        if spreadsheet_url:
            # Usa l'URL completo
            spreadsheet = client.open_by_url(spreadsheet_url)
        elif spreadsheet_id:
            # Usa solo l'ID del foglio
            spreadsheet = client.open_by_key(spreadsheet_id)
        else:
            # Fallback: usa il nome del foglio
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
        
        # Pulisci il foglio
        worksheet.clear()
        
        # Header
        worksheet.update('A1', [['Giorno', 'Esercizio_JSON']])
        
        # Dati
        data = []
        for day, exercises in st.session_state.workout_template.items():
            if exercises:
                data.append([day, json.dumps(exercises, ensure_ascii=False)])
        
        if data:
            worksheet.update(f'A2:B{len(data)+1}', data)
        
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
        
        # Inizializza template vuoto
        st.session_state.workout_template = {day: [] for day in GIORNI}
        
        # Carica dati
        for record in records:
            day = record.get('Giorno')
            exercises_json = record.get('Esercizio_JSON')
            if day and exercises_json:
                st.session_state.workout_template[day] = json.loads(exercises_json)
        
        return True
    except Exception as e:
        st.error(f"Errore caricamento template: {e}")
        return False

def save_history_to_sheets():
    """Salva lo storico su Google Sheets"""
    try:
        worksheet = get_worksheet("History")
        if not worksheet:
            return False
        
        # Pulisci il foglio
        worksheet.clear()
        
        # Header
        worksheet.update('A1', [['Data', 'Giorno', 'Esercizi_JSON']])
        
        # Dati
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
        st.error(f"Errore salvataggio storico: {e}")
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
        st.error(f"Errore caricamento storico: {e}")
        return False

def save_all_data():
    """Salva tutto"""
    success = True
    success = save_template_to_sheets() and success
    success = save_history_to_sheets() and success
    return success

def load_all_data():
    """Carica tutto"""
    success = True
    success = load_template_from_sheets() and success
    success = load_history_from_sheets() and success
    return success

# --- RESTO DEL CODICE ORIGINALE ---

def init_session_state():
    """Inizializza la struttura dati"""
    if 'workout_template' not in st.session_state:
        st.session_state.workout_template = {day: [] for day in GIORNI}
    
    if 'workout_history' not in st.session_state:
        st.session_state.workout_history = []
    
    if 'data_loaded' not in st.session_state:
        # Carica automaticamente all'avvio
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

def get_last_weight_for_exercise(exercise_name):
    """Ottiene l'ultimo peso utilizzato per un esercizio"""
    history = get_exercise_history(exercise_name)
    if history:
        # Cerca l'ultimo peso valido (non vuoto)
        for h in reversed(history):
            if h['peso'] and h['peso'].strip():
                return h['peso']
    return None

# Inizializza
init_session_state()

# Sidebar
st.sidebar.title("💪 Workout Tracker")
menu = st.sidebar.radio("Menu", [
    "📋 Scheda Allenamento",
    "✍️ Registra Allenamento",
    "📅 Storico",
    "📈 Progressione"
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
    st.title("📋 Scheda Allenamento Settimanale")
    st.info("💡 Configura qui gli esercizi della tua scheda. Questi saranno ripetuti ogni settimana.")
    
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
                
                col3, col4, col5 = st.columns(3)
                
                with col3:
                    exercise['serie'] = st.text_input(
                        "Serie",
                        value=exercise.get('serie', ''),
                        placeholder="5",
                        key=f"tpl_serie_{selected_day}_{idx}"
                    )
                
                with col4:
                    exercise['ripetizioni'] = st.text_input(
                        "Ripetizioni",
                        value=exercise.get('ripetizioni', ''),
                        placeholder="4",
                        key=f"tpl_rip_{selected_day}_{idx}"
                    )
                
                with col5:
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
    
    st.markdown("---")
    
    template_exercises = st.session_state.workout_template[selected_day]
    
    if not template_exercises:
        st.warning(f"⚠️ Nessun esercizio configurato per {selected_day}. Vai in 'Scheda Allenamento' per configurare gli esercizi.")
    else:
        with st.form(f"workout_form_{selected_day}_{workout_date}"):
            exercises_data = []
            
            for idx, template_ex in enumerate(template_exercises):
                st.subheader(f"🏋️ {template_ex['nome']}")
                st.caption(f"Target: {template_ex['serie']}x{template_ex['ripetizioni']} - Recupero: {template_ex['recupero']}")
                
                col1, col2, col3 = st.columns(3)
                
                # Ottieni l'ultimo peso utilizzato per questo esercizio
                last_weight = get_last_weight_for_exercise(template_ex['nome'])
                peso_placeholder = last_weight if last_weight else "Da determinare"
                
                with col1:
                    peso = st.text_input(
                        "Peso utilizzato",
                        placeholder=peso_placeholder,
                        key=f"reg_peso_{idx}"
                    )
                
                with col2:
                    serie_fatte = st.text_input(
                        "Serie completate",
                        value=template_ex['serie'],
                        key=f"reg_serie_{idx}"
                    )
                
                with col3:
                    rip_fatte = st.text_input(
                        "Ripetizioni per serie",
                        placeholder="4,4,4,4,4",
                        key=f"reg_rip_{idx}"
                    )
                
                completato = st.checkbox(
                    "✅ Obiettivo raggiunto (serie e ripetizioni completate)",
                    key=f"reg_comp_{idx}"
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
                
                st.markdown("---")
            
            submitted = st.form_submit_button("💾 Salva Allenamento", use_container_width=True)
            
            if submitted:
                save_workout_session(selected_day, workout_date.strftime("%Y-%m-%d"), exercises_data)
                save_all_data()
                st.success(f"✅ Allenamento di {selected_day} del {workout_date.strftime('%d/%m/%Y')} salvato!")
                st.balloons()

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
        
        history = st.session_state.workout_history
        if filtro_giorno != "Tutti":
            history = [s for s in history if s['giorno'] == filtro_giorno]
        
        history = sorted(history, key=lambda x: x['data'], reverse=True)
        
        for session in history:
            with st.expander(f"📆 {session['data']} - {session['giorno']}"):
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
            
            for h in history:
                try:
                    peso_val = float(h['peso'].replace('kg', '').replace('Kg', '').strip())
                    weights.append(peso_val)
                except:
                    weights.append(None)
                
                completions.append(1 if h['completato'] else 0)
            
            st.subheader("📊 Progressione Peso")
            fig_weight = go.Figure()
            
            valid_weights = [(d, w) for d, w in zip(dates, weights) if w is not None]
            if valid_weights:
                valid_dates, valid_weight_values = zip(*valid_weights)
                fig_weight.add_trace(go.Scatter(
                    x=valid_dates,
                    y=valid_weight_values,
                    mode='lines+markers',
                    name='Peso',
                    line=dict(color='#1f77b4', width=3),
                    marker=dict(size=10)
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
                name='Completato'
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
                    "Giorno": h['giorno'],
                    "Target": f"{h['serie_target']}x{h['rip_target']}",
                    "Eseguito": f"{h['serie_eseguite']}x{h['rip_eseguite']}",
                    "Peso": h['peso'],
                    "Recupero": h['recupero'],
                    "✅": "Sì" if h['completato'] else "No"
                })
            
            df = pd.DataFrame(detail_data)
            st.dataframe(df, use_container_width=True, hide_index=True)

st.sidebar.markdown("---")
st.sidebar.markdown("💪 **Workout Tracker v2.2**")
st.sidebar.markdown("Con Google Sheets!")
