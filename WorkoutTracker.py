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

# ============================================================================
# ← SEZIONE NUOVA: FUNZIONI DI AUTENTICAZIONE
# ============================================================================

def generate_or_get_device_id():
    """Genera o recupera un deviceId persistente dal localStorage del browser"""
    
    # Se già abbiamo il device_id in questa sessione, usalo
    if 'device_id' in st.session_state and st.session_state.device_id:
        return st.session_state.device_id
    
    # Altrimenti, carica il componente HTML con una key univoca per forzare il rendering
    component_key = f"device_id_loader_{st.session_state.get('device_load_attempt', 0)}"
    
    result = components.html("""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
    </head>
    <body>
        <div id="status" style="font-family: monospace; font-size: 10px; color: #666;">
            Caricamento device ID...
        </div>
        <script>
            (function(){
                console.log('[Device ID] Script avviato');
                
                function getOrCreateDeviceId() {
                    try {
                        // Prova a usare crypto.randomUUID (browser moderni)
                        var id = localStorage.getItem('workout_device_id');
                        console.log('[Device ID] Valore da localStorage:', id);
                        
                        if (!id) {
                            if (typeof crypto !== 'undefined' && crypto.randomUUID) {
                                id = crypto.randomUUID();
                                console.log('[Device ID] Generato con crypto.randomUUID:', id);
                            } else {
                                // Fallback per browser più vecchi
                                id = 'dev-' + Date.now().toString(36) + '-' + Math.random().toString(36).substr(2, 9);
                                console.log('[Device ID] Generato con fallback:', id);
                            }
                            
                            try {
                                localStorage.setItem('workout_device_id', id);
                                console.log('[Device ID] Salvato in localStorage');
                            } catch(e) {
                                console.error('[Device ID] Errore salvataggio localStorage:', e);
                                // Anche se non può salvare, usiamo l'ID generato per questa sessione
                            }
                        }
                        
                        return id;
                    } catch(e) {
                        console.error('[Device ID] Errore generale:', e);
                        // Ultimo fallback
                        return 'error-' + Date.now().toString(36);
                    }
                }
                
                // Aspetta un attimo per essere sicuri che il DOM sia pronto
                setTimeout(function() {
                    try {
                        var deviceId = getOrCreateDeviceId();
                        console.log('[Device ID] Device ID finale:', deviceId);
                        
                        document.getElementById('status').innerText = 'Device ID: ' + deviceId.substring(0, 8) + '...';
                        
                        // Invia il risultato a Streamlit
                        window.parent.postMessage({
                            type: 'streamlit:setComponentValue',
                            data: { 
                                deviceId: deviceId,
                                timestamp: Date.now(),
                                success: true
                            }
                        }, '*');
                        
                        console.log('[Device ID] Messaggio inviato a Streamlit');
                    } catch(e) {
                        console.error('[Device ID] Errore invio messaggio:', e);
                        document.getElementById('status').innerText = 'Errore: ' + e.message;
                        
                        // Invia comunque un messaggio di errore
                        window.parent.postMessage({
                            type: 'streamlit:setComponentValue',
                            data: { 
                                deviceId: 'error-' + Date.now(),
                                timestamp: Date.now(),
                                success: false,
                                error: e.message
                            }
                        }, '*');
                    }
                }, 250);
            })();
        </script>
    </body>
    </html>
    """, height=30, key=component_key)
    
    # Incrementa il contatore dei tentativi
    if 'device_load_attempt' not in st.session_state:
        st.session_state.device_load_attempt = 0
    
    # Analizza il risultato
    if result and isinstance(result, dict):
        device_id = result.get('deviceId')
        success = result.get('success', False)
        
        if device_id and success:
            # Device ID caricato con successo
            st.session_state.device_id = device_id
            st.session_state.device_id_loaded = True
            return device_id
        elif device_id:
            # Device ID ricevuto ma con possibili errori
            st.session_state.device_id = device_id
            st.session_state.device_id_loaded = True
            return device_id
    
    # Se arriviamo qui, il componente non ha ancora restituito il valore
    # Usa un fallback TEMPORANEO e prova a ricaricare
    if st.session_state.device_load_attempt < 5:
        st.session_state.device_load_attempt += 1
        # Non salvare il fallback, forza un rerun per riprovare
        import uuid
        temp_id = f"loading-{str(uuid.uuid4())}"
        return temp_id
    else:
        # Dopo 5 tentativi, usa un fallback permanente
        import uuid
        fallback_id = f"fallback-{str(uuid.uuid4())}"
        st.session_state.device_id = fallback_id
        st.session_state.device_id_loaded = True
        return fallback_id
    

def check_login_expiry(login_date_str):
    """Verifica se sono passati più di 30 giorni dall'ultimo login"""
    if not login_date_str:
        return True
    
    try:
        login_date = datetime.strptime(login_date_str, "%Y-%m-%d")
        days_passed = (datetime.now() - login_date).days
        return days_passed > 30
    except:
        return True
        
def hash_password(password):
    """Crea hash della password"""
    return hashlib.sha256(password.encode()).hexdigest()

def verify_user_exists(username):
    """Verifica se l'utente esiste (senza password)"""
    try:
        worksheet = get_worksheet("Users")
        if not worksheet:
            return False
        
        records = worksheet.get_all_records()
        return any(record.get('Username') == username for record in records)
    except:
        return False

def save_device_mapping_to_sheets(device_id, username):
    """Salva/aggiorna la mappatura DeviceID -> LastUsername + LastLoginDate nel worksheet 'Devices'."""
    try:
        if not device_id or not username:
            return False
        worksheet = get_worksheet("Devices")
        if not worksheet:
            return False

        # Assicurati header
        try:
            headers = worksheet.row_values(1)
            if not headers or headers[0] != 'DeviceID':
                worksheet.update('A1', [['DeviceID', 'LastUsername', 'LastLoginDate', 'AutoLoginEnabled']])
        except:
            worksheet.update('A1', [['DeviceID', 'LastUsername', 'LastLoginDate', 'AutoLoginEnabled']])

        all_records = worksheet.get_all_records()
        row_to_update = None
        for i, record in enumerate(all_records, start=2):
            if record.get('DeviceID') == device_id:
                row_to_update = i
                break

        now_str = datetime.now().strftime("%Y-%m-%d")
        if row_to_update:
            worksheet.update(f'A{row_to_update}:D{row_to_update}', [[device_id, username, now_str, 'YES']])
        else:
            worksheet.append_row([device_id, username, now_str, 'YES'])

        return True
    except Exception as e:
        st.error(f"Errore salvataggio device mapping: {e}")
        return False

def load_device_mapping_from_sheets(device_id):
    """Carica la mappatura per un device_id. Ritorna dict {'username':..., 'last_login':..., 'auto_login':...} o None."""
    try:
        if not device_id:
            return None
        worksheet = get_worksheet("Devices")
        if not worksheet:
            return None

        all_records = worksheet.get_all_records()
        for record in all_records:
            if record.get('DeviceID') == device_id:
                return {
                    'username': record.get('LastUsername'),
                    'last_login': record.get('LastLoginDate'),
                    'auto_login': record.get('AutoLoginEnabled', 'YES') == 'YES'
                }
        return None
    except Exception as e:
        st.error(f"Errore caricamento device mapping: {e}")
        return None

def disable_auto_login_for_device(device_id):
    """Disabilita l'auto-login per un dispositivo specifico"""
    try:
        if not device_id:
            return False
        worksheet = get_worksheet("Devices")
        if not worksheet:
            return False

        all_records = worksheet.get_all_records()
        for i, record in enumerate(all_records, start=2):
            if record.get('DeviceID') == device_id:
                worksheet.update(f'D{i}', [['NO']])
                return True
        return False
    except Exception as e:
        st.error(f"Errore disabilitazione auto-login: {e}")
        return False

def test_device_persistence():
    """Testa se il localStorage funziona correttamente"""
    result = components.html("""
    <!DOCTYPE html>
    <html>
    <body>
    <script>
        (function(){
            try {
                // Test localStorage
                var testKey = 'workout_test_' + Date.now();
                localStorage.setItem(testKey, 'test');
                var retrieved = localStorage.getItem(testKey);
                localStorage.removeItem(testKey);
                
                var works = (retrieved === 'test');
                
                window.parent.postMessage({
                    type: 'streamlit:setComponentValue',
                    data: { 
                        localStorageWorks: works,
                        error: null
                    }
                }, '*');
            } catch (e) {
                window.parent.postMessage({
                    type: 'streamlit:setComponentValue',
                    data: { 
                        localStorageWorks: false,
                        error: e.message
                    }
                }, '*');
            }
        })();
    </script>
    </body>
    </html>
    """, height=0)
    
    return result
    
def verify_user(username, password):
    """Verifica le credenziali utente"""
    try:
        worksheet = get_worksheet("Users")
        if not worksheet:
            return False
        
        records = worksheet.get_all_records()
        for record in records:
            if record.get('Username') == username:
                stored_password = record.get('Password', '')
                # Supporta sia password in chiaro (per migrazione) che hash
                if stored_password == password or stored_password == hash_password(password):
                    return True
        return False
    except Exception as e:
        st.error(f"Errore verifica utente: {e}")
        return False

def get_user_full_name(username):
    """Ottiene il nome completo dell'utente"""
    try:
        worksheet = get_worksheet("Users")
        if not worksheet:
            return username
        
        records = worksheet.get_all_records()
        for record in records:
            if record.get('Username') == username:
                return record.get('Nome_Completo', username)
        return username
    except:
        return username

def show_login_page():
    """Mostra la pagina di login con auto-login basato su device"""
    
    # STEP 1: Ottieni il device_id
    device_id = generate_or_get_device_id()
    
    # Se il device_id è ancora in fase di caricamento, mostra spinner e riprova
    if device_id.startswith('loading-'):
        with st.spinner("🔄 Inizializzazione dispositivo..."):
            import time
            time.sleep(0.5)  # Breve pausa
            st.rerun()
        return
    
    # STEP 2: Controlla auto-login SOLO se non è già stato fatto
    if not st.session_state.get('login_check_done', False):
        with st.spinner("🔄 Controllo sessione..."):
            # Verifica che il device_id sia valido (non fallback/error)
            if device_id and not device_id.startswith('fallback-') and not device_id.startswith('error-'):
                mapping = load_device_mapping_from_sheets(device_id)
                
                if mapping and mapping.get('auto_login') and mapping.get('username'):
                    mapped_user = mapping.get('username')
                    mapped_login_date = mapping.get('last_login')
                    
                    if not check_login_expiry(mapped_login_date):
                        if verify_user_exists(mapped_user):
                            st.session_state.logged_in = True
                            st.session_state.current_user = mapped_user
                            st.session_state.user_full_name = get_user_full_name(mapped_user)
                            st.session_state.login_check_done = True
                            st.success(f"✅ Accesso automatico: bentornato, {mapped_user}!")
                            save_device_mapping_to_sheets(device_id, mapped_user)
                            st.rerun()
                        else:
                            disable_auto_login_for_device(device_id)
            
            st.session_state.login_check_done = True
    
    # STEP 3: Mostra form di login
    st.title("🔐 Login - Workout Tracker")
    
    # Mostra avviso se device_id è fallback
    if device_id.startswith('fallback-') or device_id.startswith('error-'):
        st.warning("⚠️ **Modalità Limitata**: Il tuo browser potrebbe essere in modalità privata o bloccare i cookie. Il login persistente potrebbe non funzionare correttamente.")
        with st.expander("ℹ️ Come risolvere"):
            st.markdown("""
            **Per abilitare il login automatico:**
            1. Esci dalla modalità navigazione privata/incognito
            2. Assicurati che i cookie siano abilitati nel browser
            3. Su Safari mobile: Impostazioni → Safari → Blocca cookie → disabilita "Blocca tutti i cookie"
            4. Su Chrome mobile: Impostazioni → Impostazioni sito → Cookie → abilita i cookie
            
            **Device ID attuale:** `{}`
            """.format(device_id[:20] + "..."))
    
    # Debug info (rimuovi in produzione)
    if st.checkbox("🔧 Mostra info debug", value=False):
        st.code(f"Device ID completo: {device_id}")
        st.code(f"Tentativi di caricamento: {st.session_state.get('device_load_attempt', 0)}")
        st.code(f"Device ID caricato: {st.session_state.get('device_id_loaded', False)}")
        
        # Test localStorage
        test_result = test_device_persistence()
        if test_result:
            if test_result.get('localStorageWorks'):
                st.success("✅ localStorage funzionante")
            else:
                st.error(f"❌ localStorage non disponibile: {test_result.get('error', 'Errore sconosciuto')}")
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("### Accedi al tuo account")
        
        username = st.text_input("Username", key="login_username")
        password = st.text_input("Password", type="password", key="login_password")
        
        # Mostra checkbox solo se device_id è valido
        if not device_id.startswith('fallback-') and not device_id.startswith('error-'):
            remember_me = st.checkbox("🔒 Ricordami per 30 giorni su questo dispositivo", value=True)
        else:
            remember_me = False
            st.info("💡 Login automatico non disponibile in questa modalità")
        
        col_btn1, col_btn2 = st.columns(2)
        with col_btn1:
            if st.button("🔓 Accedi", use_container_width=True):
                if not username or not password:
                    st.error("⚠️ Inserisci username e password")
                elif verify_user(username, password):
                    st.session_state.logged_in = True
                    st.session_state.current_user = username
                    st.session_state.user_full_name = get_user_full_name(username)
                    
                    # Salva device mapping solo se device_id è valido e remember_me è attivo
                    if remember_me and device_id and not device_id.startswith('fallback-') and not device_id.startswith('error-'):
                        if save_device_mapping_to_sheets(device_id, username):
                            st.success("✅ Dispositivo registrato!")
                    
                    st.rerun()
                else:
                    st.error("❌ Username o password errati")
        
        with col_btn2:
            if st.button("📝 Registrati", use_container_width=True):
                st.session_state.show_register = True
                st.rerun()
                
        st.markdown("---")
        st.caption("💡 **Suggerimento:** Abilita 'Ricordami' per accedere automaticamente da questo dispositivo per 30 giorni")

def show_register_page():
    """Mostra la pagina di registrazione"""
    st.title("📝 Registrazione - Workout Tracker")
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("### Crea un nuovo account")
        
        new_username = st.text_input("Username (sarà visibile)", key="reg_username")
        new_full_name = st.text_input("Nome Completo", key="reg_fullname")
        new_password = st.text_input("Password", type="password", key="reg_password")
        new_password_confirm = st.text_input("Conferma Password", type="password", key="reg_password_confirm")
        
        col_btn1, col_btn2 = st.columns(2)
        with col_btn1:
            if st.button("✅ Registrati", use_container_width=True):
                if not new_username or not new_full_name or not new_password:
                    st.error("⚠️ Compila tutti i campi")
                elif new_password != new_password_confirm:
                    st.error("⚠️ Le password non coincidono")
                elif len(new_password) < 6:
                    st.error("⚠️ Password troppo corta (minimo 6 caratteri)")
                else:
                    # Verifica che username non esista già
                    try:
                        worksheet = get_worksheet("Users")
                        records = worksheet.get_all_records()
                        if any(r.get('Username') == new_username for r in records):
                            st.error("⚠️ Username già esistente")
                        else:
                            # Aggiungi nuovo utente
                            new_row = [new_username, new_password, new_full_name]
                            worksheet.append_row(new_row)
                            st.success("✅ Registrazione completata! Effettua il login.")
                            st.session_state.show_register = False
                            st.rerun()
                    except Exception as e:
                        st.error(f"❌ Errore durante la registrazione: {e}")
        
        with col_btn2:
            if st.button("🔙 Torna al Login", use_container_width=True):
                st.session_state.show_register = False
                st.rerun()

# ============================================================================
# ← FINE SEZIONE NUOVA
# ============================================================================

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
    """Salva il template su Google Sheets - SAFE per multi-utente"""
    try:
        username = st.session_state.current_user
        worksheet = get_worksheet("Template")
        if not worksheet:
            return False
        
        # Assicurati che esista l'header
        try:
            headers = worksheet.row_values(1)
            if not headers or headers[0] != 'Username':
                worksheet.update('A1', [['Username', 'Giorno', 'Esercizio_JSON']])
        except:
            worksheet.update('A1', [['Username', 'Giorno', 'Esercizio_JSON']])
        
        # Trova tutte le righe dell'utente corrente e eliminale
        all_records = worksheet.get_all_records()
        rows_to_delete = []
        for i, record in enumerate(all_records, start=2):  # start=2 perché row 1 è l'header
            if record.get('Username') == username:
                rows_to_delete.append(i)
        
        # Elimina le righe dell'utente dall'alto verso il basso (per non sballare gli indici)
        for row_idx in sorted(rows_to_delete, reverse=True):
            worksheet.delete_rows(row_idx)
        
        # Aggiungi i nuovi dati dell'utente
        data = []
        for day, exercises in st.session_state.workout_template.items():
            if exercises:
                data.append([username, day, json.dumps(exercises, ensure_ascii=False)])
        
        if data:
            worksheet.append_rows(data)
        
        return True
    except Exception as e:
        st.error(f"Errore salvataggio template: {e}")
        return False
        
def load_template_from_sheets():
    """Carica il template da Google Sheets"""
    try:
        username = st.session_state.current_user  # ← AGGIUNTO
        worksheet = get_worksheet("Template")
        if not worksheet:
            return False
        
        records = worksheet.get_all_records()
        st.session_state.workout_template = {day: [] for day in GIORNI}
        
        # ← MODIFICATO: Filtra solo i dati dell'utente corrente
        for record in records:
            if record.get('Username') == username:  # ← AGGIUNTO
                day = record.get('Giorno')
                exercises_json = record.get('Esercizio_JSON')
                if day and exercises_json:
                    st.session_state.workout_template[day] = json.loads(exercises_json)
        
        return True
    except Exception as e:
        st.error(f"Errore caricamento template: {e}")
        return False

def save_config_to_sheets():
    """Salva la configurazione (data inizio scheda) - SAFE per multi-utente"""
    try:
        username = st.session_state.current_user
        worksheet = get_worksheet("Config")
        if not worksheet:
            return False
        
        # Assicurati che esista l'header
        try:
            headers = worksheet.row_values(1)
            if not headers or headers[0] != 'Username':
                worksheet.update('A1', [['Username', 'Chiave', 'Valore']])
        except:
            worksheet.update('A1', [['Username', 'Chiave', 'Valore']])
        
        # Trova la riga dell'utente corrente per 'data_inizio_scheda'
        all_records = worksheet.get_all_records()
        row_to_update = None
        for i, record in enumerate(all_records, start=2):
            if record.get('Username') == username and record.get('Chiave') == 'data_inizio_scheda':
                row_to_update = i
                break
        
        # Aggiorna o aggiungi
        if row_to_update:
            worksheet.update(f'A{row_to_update}:C{row_to_update}', 
                           [[username, 'data_inizio_scheda', st.session_state.data_inizio_scheda]])
        else:
            worksheet.append_row([username, 'data_inizio_scheda', st.session_state.data_inizio_scheda])
        
        return True
    except Exception as e:
        st.error(f"Errore salvataggio config: {e}")
        return False

def load_config_from_sheets():
    """Carica la configurazione"""
    try:
        username = st.session_state.current_user  # ← AGGIUNTO
        worksheet = get_worksheet("Config")
        if not worksheet:
            return False
        
        records = worksheet.get_all_records()
        # ← MODIFICATO: Filtra per utente
        for record in records:
            if record.get('Username') == username and record.get('Chiave') == 'data_inizio_scheda':  # ← MODIFICATO
                st.session_state.data_inizio_scheda = record.get('Valore', '')
        
        return True
    except Exception as e:
        st.error(f"Errore caricamento config: {e}")
        return False

def save_weight_calories_to_sheets():
    """Salva lo storico peso e calorie su Google Sheets"""
    try:
        username = st.session_state.current_user
        worksheet = get_worksheet("WeightCalories")
        if not worksheet:
            return False
        
        # Assicurati che esista l'header
        try:
            headers = worksheet.row_values(1)
            if not headers or headers[0] != 'Username':
                worksheet.update('A1', [['Username', 'Data', 'Peso', 'Calorie']])
        except:
            worksheet.update('A1', [['Username', 'Data', 'Peso', 'Calorie']])
        
        # Trova tutte le righe dell'utente corrente e eliminale
        all_records = worksheet.get_all_records()
        rows_to_delete = []
        for i, record in enumerate(all_records, start=2):
            if record.get('Username') == username:
                rows_to_delete.append(i)
        
        # Elimina le righe dell'utente dall'alto verso il basso
        for row_idx in sorted(rows_to_delete, reverse=True):
            worksheet.delete_rows(row_idx)
        
        # Aggiungi tutti i dati dell'utente
        data = []
        for entry in st.session_state.weight_calories_history:
            data.append([
                username,
                entry['data'],
                entry['peso'],
                entry['calorie']
            ])
        
        if data:
            worksheet.append_rows(data)
        
        return True
    except Exception as e:
        st.error(f"Errore salvataggio peso/calorie: {e}")
        return False

def load_weight_calories_from_sheets():
    """Carica lo storico peso e calorie da Google Sheets"""
    try:
        username = st.session_state.current_user
        worksheet = get_worksheet("WeightCalories")
        if not worksheet:
            return False
        
        records = worksheet.get_all_records()
        st.session_state.weight_calories_history = []
        
        # Filtra per utente
        for record in records:
            if record.get('Username') == username:
                entry = {
                    'data': record.get('Data'),
                    'peso': record.get('Peso', ''),
                    'calorie': record.get('Calorie', '')
                }
                st.session_state.weight_calories_history.append(entry)
        
        return True
    except Exception as e:
        st.error(f"Errore caricamento peso/calorie: {e}")
        return False
        
def save_history_to_sheets():
    """Salva lo storico su Google Sheets - SAFE per multi-utente"""
    try:
        username = st.session_state.current_user
        worksheet = get_worksheet("History")
        if not worksheet:
            return False
        
        # Assicurati che esista l'header
        try:
            headers = worksheet.row_values(1)
            if not headers or headers[0] != 'Username':
                worksheet.update('A1', [['Username', 'Data', 'Giorno', 'Settimana', 'Esercizi_JSON']])
        except:
            worksheet.update('A1', [['Username', 'Data', 'Giorno', 'Settimana', 'Esercizi_JSON']])
        
        # Trova tutte le righe dell'utente corrente e eliminale
        all_records = worksheet.get_all_records()
        rows_to_delete = []
        for i, record in enumerate(all_records, start=2):
            if record.get('Username') == username:
                rows_to_delete.append(i)
        
        # Elimina le righe dell'utente dall'alto verso il basso
        for row_idx in sorted(rows_to_delete, reverse=True):
            worksheet.delete_rows(row_idx)
        
        # Aggiungi tutti gli allenamenti dell'utente
        data = []
        for session in st.session_state.workout_history:
            data.append([
                username,
                session['data'],
                session['giorno'],
                session.get('settimana', 1),
                json.dumps(session['esercizi'], ensure_ascii=False)
            ])
        
        if data:
            worksheet.append_rows(data)
        
        return True
    except Exception as e:
        st.error(f"Errore salvataggio storico: {e}")
        return False
        
def load_history_from_sheets():
    """Carica lo storico da Google Sheets"""
    try:
        username = st.session_state.current_user  # ← AGGIUNTO
        worksheet = get_worksheet("History")
        if not worksheet:
            return False
        
        records = worksheet.get_all_records()
        st.session_state.workout_history = []
        
        # ← MODIFICATO: Filtra per utente
        for record in records:
            if record.get('Username') == username:  # ← AGGIUNTO
                session = {
                    'data': record.get('Data'),
                    'giorno': record.get('Giorno'),
                    'settimana': record.get('Settimana', 1),
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
    if 'login_check_done' not in st.session_state:
        st.session_state.login_check_done = False
    
    # NON generare device_id qui - verrà generato da generate_or_get_device_id()
    # quando necessario, per permettere al componente HTML di caricarsi correttamente
    
    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False
    
    if 'current_user' not in st.session_state:
        st.session_state.current_user = None
    
    if 'user_full_name' not in st.session_state:
        st.session_state.user_full_name = None
    
    if 'show_register' not in st.session_state:
        st.session_state.show_register = False
    
    if 'workout_template' not in st.session_state:
        st.session_state.workout_template = {day: [] for day in GIORNI}
    
    if 'workout_history' not in st.session_state:
        st.session_state.workout_history = []
    
    if 'data_inizio_scheda' not in st.session_state:
        st.session_state.data_inizio_scheda = "2025-11-03"

    if 'weight_calories_history' not in st.session_state:
        st.session_state.weight_calories_history = []
        
    # Carica dati solo se loggato
    if 'data_loaded' not in st.session_state and st.session_state.logged_in:
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

# CONTROLLA LOGIN
if not st.session_state.logged_in:
    # Mostra pagina appropriata
    if st.session_state.get('show_register', False):
        show_register_page()
    else:
        show_login_page()
    st.stop()
    
# Sidebar
st.sidebar.title("💪 Workout Tracker")

# Info utente e logout
st.sidebar.markdown(f"👤 **{st.session_state.user_full_name}**")

col_logout1, col_logout2 = st.sidebar.columns([2, 1])
with col_logout1:
    if st.button("🚪 Logout", use_container_width=True):
        # Disabilita auto-login per questo dispositivo
        device_id = st.session_state.get('device_id')
        if device_id:
            disable_auto_login_for_device(device_id)
        
        # Pulisci sessione
        st.session_state.logged_in = False
        st.session_state.current_user = None
        st.session_state.user_full_name = None
        st.session_state.data_loaded = False
        st.session_state.login_check_done = False
        st.session_state.workout_template = {day: [] for day in GIORNI}
        st.session_state.workout_history = []
        st.session_state.weight_calories_history = []
        st.session_state.data_inizio_scheda = "2025-11-03"
        st.rerun()

with col_logout2:
    if st.button("ℹ️", use_container_width=True, help="Info dispositivo"):
        device_id = st.session_state.get('device_id', 'Non disponibile')
        st.sidebar.info(f"**Device ID:**\n`{device_id[:8]}...`")
        
# Dopo il blocco logout, aggiungi questa sezione
if st.sidebar.button("🔄 Reset Device ID", help="Genera un nuovo device ID se ci sono problemi"):
    if 'device_id' in st.session_state:
        old_device = st.session_state.device_id
        # Rimuovi il device ID da localStorage
        components.html("""
        <script>
            try {
                localStorage.removeItem('workout_device_id');
                console.log('Device ID rimosso da localStorage');
            } catch(e) {
                console.error('Errore rimozione device ID:', e);
            }
        </script>
        """, height=0)
        
        # Pulisci session state
        del st.session_state.device_id
        st.session_state.device_load_attempt = 0
        st.session_state.device_id_loaded = False
        st.session_state.login_check_done = False
        
        st.sidebar.success("✅ Device ID resettato! Ricarica la pagina.")
        st.rerun()
        
# Nel blocco sidebar, dopo il logout
if st.sidebar.button("🔍 Diagnosi Dispositivo"):
    with st.sidebar:
        st.markdown("### 🔧 Diagnostica")
        device_id = st.session_state.get('device_id', 'Non disponibile')
        st.code(f"Device ID:\n{device_id}", language=None)
        
        if device_id:
            mapping = load_device_mapping_from_sheets(device_id)
            if mapping:
                st.success("✅ Dispositivo registrato")
                st.json(mapping)
            else:
                st.warning("⚠️ Dispositivo non registrato")
        
        # Test localStorage
        test_result = test_device_persistence()
        if test_result:
            if test_result.get('localStorageWorks'):
                st.success("✅ localStorage funzionante")
            else:
                st.error(f"❌ localStorage non disponibile: {test_result.get('error', 'Errore sconosciuto')}")
                
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
