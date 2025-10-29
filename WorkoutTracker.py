import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import json
from datetime import datetime

# Configurazione pagina
st.set_page_config(page_title="Workout Tracker", page_icon="💪", layout="wide")

# Inizializzazione dati
GIORNI = ["Lunedì", "Martedì", "Mercoleì", "Giovedì", "Venerdì", "Sabato", "Domenica"]
SETTIMANE = 6

def init_session_state():
    """Inizializza la struttura dati se non esiste"""
    if 'workout_data' not in st.session_state:
        st.session_state.workout_data = {}
        for week in range(1, SETTIMANE + 1):
            st.session_state.workout_data[week] = {}
            for day in GIORNI:
                st.session_state.workout_data[week][day] = []

def save_data():
    """Salva i dati in formato JSON"""
    try:
        with open('workout_data.json', 'w', encoding='utf-8') as f:
            json.dump(st.session_state.workout_data, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        st.error(f"Errore nel salvataggio: {e}")
        return False

def load_data():
    """Carica i dati dal file JSON"""
    try:
        with open('workout_data.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
            # Converti chiavi settimana da string a int
            st.session_state.workout_data = {int(k): v for k, v in data.items()}
        return True
    except FileNotFoundError:
        return False
    except Exception as e:
        st.error(f"Errore nel caricamento: {e}")
        return False

def add_exercise(week, day):
    """Aggiunge un nuovo esercizio vuoto"""
    new_exercise = {
        'nome': '',
        'serie_rip': '',
        'recupero': '',
        'peso': '',
        'rip_eseguite': '',
        'note': '',
        'completato': False
    }
    st.session_state.workout_data[week][day].append(new_exercise)

def delete_exercise(week, day, idx):
    """Elimina un esercizio"""
    st.session_state.workout_data[week][day].pop(idx)

def get_exercise_progress(exercise_name):
    """Estrae la progressione di un esercizio attraverso le settimane"""
    weeks = []
    weights = []
    
    for week in range(1, SETTIMANE + 1):
        for day in GIORNI:
            for exercise in st.session_state.workout_data[week][day]:
                if exercise['nome'].lower() == exercise_name.lower() and exercise['peso']:
                    try:
                        peso_val = float(exercise['peso'].replace('kg', '').strip())
                        weeks.append(f"W{week}-{day[:3]}")
                        weights.append(peso_val)
                    except:
                        pass
    
    return weeks, weights

# Inizializza
init_session_state()

# Sidebar per navigazione
st.sidebar.title("💪 Workout Tracker")
menu = st.sidebar.radio("Menu", ["📝 Input Allenamento", "📅 Vista Settimanale", "📈 Progressione"])

# Gestione salvataggio/caricamento
st.sidebar.markdown("---")
col1, col2 = st.sidebar.columns(2)
if col1.button("💾 Salva"):
    if save_data():
        st.sidebar.success("Salvato!")
if col2.button("📂 Carica"):
    if load_data():
        st.sidebar.success("Caricato!")
    else:
        st.sidebar.info("Nessun file trovato")

# --- PAGINA INPUT ALLENAMENTO ---
if menu == "📝 Input Allenamento":
    st.title("📝 Input Allenamento")
    
    col1, col2 = st.columns(2)
    with col1:
        selected_week = st.selectbox("Settimana", range(1, SETTIMANE + 1))
    with col2:
        selected_day = st.selectbox("Giorno", GIORNI)
    
    st.markdown("---")
    
    # Aggiungi esercizio
    if st.button("➕ Aggiungi Esercizio"):
        add_exercise(selected_week, selected_day)
        st.rerun()
    
    # Mostra esercizi
    exercises = st.session_state.workout_data[selected_week][selected_day]
    
    if not exercises:
        st.info("Nessun esercizio presente. Clicca '➕ Aggiungi Esercizio' per iniziare.")
    else:
        for idx, exercise in enumerate(exercises):
            with st.expander(f"🏋️ {exercise['nome'] or f'Esercizio {idx+1}'}", expanded=True):
                col1, col2, col3 = st.columns([3, 1, 1])
                
                with col1:
                    exercise['nome'] = st.text_input(
                        "Nome esercizio", 
                        value=exercise['nome'], 
                        key=f"nome_{selected_week}_{selected_day}_{idx}"
                    )
                
                with col2:
                    exercise['serie_rip'] = st.text_input(
                        "Serie x Rip", 
                        value=exercise['serie_rip'], 
                        placeholder="5x4",
                        key=f"serie_{selected_week}_{selected_day}_{idx}"
                    )
                
                with col3:
                    exercise['recupero'] = st.text_input(
                        "Recupero", 
                        value=exercise['recupero'], 
                        placeholder="2min",
                        key=f"rec_{selected_week}_{selected_day}_{idx}"
                    )
                
                col4, col5 = st.columns(2)
                
                with col4:
                    exercise['peso'] = st.text_input(
                        "Peso target", 
                        value=exercise['peso'], 
                        placeholder="65kg",
                        key=f"peso_{selected_week}_{selected_day}_{idx}"
                    )
                
                with col5:
                    exercise['rip_eseguite'] = st.text_input(
                        "Ripetizioni eseguite", 
                        value=exercise['rip_eseguite'], 
                        placeholder="4,4,4,4,4",
                        key=f"rip_{selected_week}_{selected_day}_{idx}"
                    )
                
                exercise['note'] = st.text_area(
                    "Note/Varianti", 
                    value=exercise['note'], 
                    height=60,
                    key=f"note_{selected_week}_{selected_day}_{idx}"
                )
                
                col6, col7 = st.columns([3, 1])
                with col6:
                    exercise['completato'] = st.checkbox(
                        "✅ Completato", 
                        value=exercise['completato'],
                        key=f"comp_{selected_week}_{selected_day}_{idx}"
                    )
                with col7:
                    if st.button("🗑️ Elimina", key=f"del_{selected_week}_{selected_day}_{idx}"):
                        delete_exercise(selected_week, selected_day, idx)
                        st.rerun()

# --- PAGINA VISTA SETTIMANALE ---
elif menu == "📅 Vista Settimanale":
    st.title("📅 Vista Settimanale")
    
    selected_week = st.selectbox("Seleziona Settimana", range(1, SETTIMANE + 1))
    
    st.markdown("---")
    
    for day in GIORNI:
        st.subheader(f"📆 {day}")
        exercises = st.session_state.workout_data[selected_week][day]
        
        if not exercises:
            st.info("Nessun esercizio programmato")
        else:
            data = []
            for ex in exercises:
                status = "✅" if ex['completato'] else "❌"
                data.append({
                    "Status": status,
                    "Esercizio": ex['nome'],
                    "Serie x Rip": ex['serie_rip'],
                    "Recupero": ex['recupero'],
                    "Peso": ex['peso'],
                    "Eseguito": ex['rip_eseguite']
                })
            
            df = pd.DataFrame(data)
            st.dataframe(df, use_container_width=True, hide_index=True)
        
        st.markdown("---")

# --- PAGINA PROGRESSIONE ---
elif menu == "📈 Progressione":
    st.title("📈 Progressione Esercizi")
    
    # Raccolta di tutti gli esercizi unici
    all_exercises = set()
    for week in range(1, SETTIMANE + 1):
        for day in GIORNI:
            for exercise in st.session_state.workout_data[week][day]:
                if exercise['nome']:
                    all_exercises.add(exercise['nome'])
    
    if not all_exercises:
        st.info("Nessun esercizio registrato. Inizia ad inserire i tuoi allenamenti!")
    else:
        selected_exercise = st.selectbox("Seleziona Esercizio", sorted(all_exercises))
        
        weeks, weights = get_exercise_progress(selected_exercise)
        
        if not weeks:
            st.warning(f"Nessun dato di peso registrato per '{selected_exercise}'")
        else:
            # Grafico Plotly
            fig = go.Figure()
            
            fig.add_trace(go.Scatter(
                x=weeks,
                y=weights,
                mode='lines+markers',
                name=selected_exercise,
                line=dict(color='#1f77b4', width=3),
                marker=dict(size=10, symbol='circle')
            ))
            
            fig.update_layout(
                title=f"Progressione: {selected_exercise}",
                xaxis_title="Allenamento",
                yaxis_title="Peso (kg)",
                hovermode='x unified',
                template='plotly_white',
                height=500
            )
            
            st.plotly_chart(fig, use_container_width=True)
            
            # Statistiche
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Peso Iniziale", f"{min(weights):.1f} kg")
            with col2:
                st.metric("Peso Attuale", f"{weights[-1]:.1f} kg")
            with col3:
                diff = weights[-1] - min(weights)
                st.metric("Incremento", f"{diff:.1f} kg", delta=f"{diff:.1f} kg")

# Footer
st.sidebar.markdown("---")
st.sidebar.markdown("💪 **Workout Tracker v1.0**")
st.sidebar.markdown("Gestisci i tuoi allenamenti con facilità!")
