#!/usr/bin/env python3

import speedtest
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import os
import subprocess
import re # Pro parsování výstupu PING příkazu

# --- Konfigurace ---
SHEET_NAME = "SpeedTestDubl"
SERVICE_ACCOUNT_KEY_FILE = '/home/pi/Speedtest/config/authgoogle.json' 
SCOPE = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
# AKTUALIZOVANO: Přidán nový sloupec "Packet Loss (%)"
HEADERS = ["Timestamp", "Ping", "Download", "Upload", "Server Name", "Packet Loss (%)"]
PING_TARGET = "8.8.8.8"
PING_COUNT = 10 # Pocet paketů pro test

def get_google_sheet_client():
    """Autorizuje a vrací klienta pro Google Sheets."""
    try:
        creds = ServiceAccountCredentials.from_json_keyfile_name(SERVICE_ACCOUNT_KEY_FILE, SCOPE)
        return gspread.authorize(creds)
    except Exception as e:
        # Vylepšena chybová hláška pro snazší diagnostiku
        raise ConnectionError(f"Nepodařilo se autorizovat Google Sheets klienta. Zkontrolujte soubor {SERVICE_ACCOUNT_KEY_FILE} a oprávnění. Chyba: {e}")

def get_or_create_worksheet(client: gspread.Client) -> gspread.Worksheet:
    """
    Vrátí existující list (worksheet) pro aktuální měsíc a rok,
    nebo vytvoří nový, pokud neexistuje.
    """
    current_date = datetime.now()
    worksheet_title = current_date.strftime("%B %Y")
    
    try:
        spreadsheet = client.open(SHEET_NAME)
        print(f"Používám sešit: '{SHEET_NAME}'")
    except gspread.exceptions.SpreadsheetNotFound:
        raise FileNotFoundError(f"Google sešit '{SHEET_NAME}' nebyl nalezen.")

    try:
        worksheet = spreadsheet.worksheet(worksheet_title)
        print(f"Používám existující list: '{worksheet_title}'")
        return worksheet
    except gspread.exceptions.WorksheetNotFound:
        print(f"List '{worksheet_title}' nenalezen, vytvářím nový...")
        # AKTUALIZOVANO: Zvýšen počet sloupců na 6
        worksheet = spreadsheet.add_worksheet(title=worksheet_title, rows="1", cols="6")
        worksheet.append_row(HEADERS)
        print("Hlavičky byly přidány.")
        return worksheet

def run_speedtest() -> tuple[float, float, float, str]:
    """Provede test rychlosti a vrátí výsledky."""
    try:
        st = speedtest.Speedtest()
        # Získání informací o nejlepším serveru
        best_server = st.get_best_server()
        st.download()
        st.upload()
        results = st.results.dict()

        download_mbps = round(results['download'] / 1_000_000, 2)
        upload_mbps = round(results['upload'] / 1_000_000, 2)
        ping_ms = round(results['ping'], 2)
        server_name = best_server['host']  # Získání názvu serveru
        
        return ping_ms, download_mbps, upload_mbps, server_name
    except speedtest.SpeedtestException as e:
        raise ConnectionError(f"Chyba při provádění Speedtestu: {e}")

def run_ping_test(target: str, count: int) -> float:
    """Provede PING test a vrátí ztrátu paketů v procentech."""
    try:
        # Spuštění ping příkazu s 10 pakety (-c 10)
        # Výstup se zachytí
        result = subprocess.run(
            ['ping', '-c', str(count), target], 
            capture_output=True, 
            text=True, 
            timeout=10 # Nastavení timeoutu
        )
        
        # Hledání řádku se souhrnem statistiky (např. "10 packets transmitted, 10 received, 0% packet loss")
        # Regulární výraz najde číslo a znak % před "packet loss"
        match = re.search(r'(\d+)% packet loss', result.stdout)
        
        if match:
            # Ztráta paketů nalezena
            return float(match.group(1))
        else:
            # Souhrn nenalezen, pravděpodobně selhalo připojení
            print(f"Upozornění: Nepodařilo se parsovat ztrátu paketů z PING testu. Výstup: {result.stdout.strip()}")
            return 100.0 # Předpokládat 100% ztrátu

    except subprocess.TimeoutExpired:
        print("Upozornění: PING test vypršel. Předpokládám 100% ztrátu paketů.")
        return 100.0
    except Exception as e:
        print(f"Chyba při provádění PING testu: {e}")
        return 100.0


if __name__ == "__main__":
    try:
        google_client = get_google_sheet_client()
        sheet = get_or_create_worksheet(google_client)

        # --- Speedtest ---
        print("Provádím test rychlosti (Download/Upload/Ping)...")
        ping, download, upload, server_name = run_speedtest()
        
        # --- Ping Test pro Packet Loss ---
        print(f"Provádím test ztráty paketů na {PING_TARGET}...")
        packet_loss = run_ping_test(PING_TARGET, PING_COUNT)
        
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # AKTUALIZOVANO: Radek nyní obsahuje i Packet Loss
        row = [timestamp, ping, download, upload, server_name, packet_loss]
        sheet.append_row(row)
        
        print("\n--- Výsledky měření ---")
        print(f"Uloženo: {timestamp}")
        print(f"Ping: {ping} ms | Download: {download} Mbps | Upload: {upload} Mbps")
        print(f"Server: {server_name}")
        print(f"Packet Loss: {packet_loss}%")
        print("-----------------------")

    except (ConnectionError, FileNotFoundError) as e:
        # Kritická chyba (např. chyba sítě, špatná autentizace)
        print(f"KRITICKÁ CHYBA: {e}")
    except Exception as e:
        print(f"Došlo k neočekávané chybě: {e}")
