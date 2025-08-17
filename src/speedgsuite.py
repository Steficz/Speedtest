#!/usr/bin/env python3

import speedtest
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

# Cesta k JSON souboru s klíči servisního účtu
SCOPE = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name('/home/pi/Speedtest/config/authgoogle.json', SCOPE)
client = gspread.authorize(creds)

# Název Google Sheet
SHEET_NAME = "SpeedTestDubl"
# Hlavičky, které se přidají na nový list
HEADERS = ["Timestamp", "Ping", "Download", "Upload"]

def get_or_create_worksheet():
    """Vrátí existující list, nebo vytvoří nový pro aktuální měsíc."""
    # Vytvoření názvu listu ve formátu "Měsíc Rok", např. "Srpen 2025"
    current_date = datetime.now()
    month_name = current_date.strftime("%B")  # %B vrací plný název měsíce
    year = current_date.strftime("%Y")
    worksheet_title = f"{month_name} {year}"

    try:
        # Zkusí otevřít existující list
        worksheet = client.open(SHEET_NAME).worksheet(worksheet_title)
        print(f"Používám existující list: '{worksheet_title}'")
        return worksheet
    except gspread.exceptions.WorksheetNotFound:
        # Pokud list neexistuje, vytvoří ho
        print(f"List '{worksheet_title}' nenalezen, vytvářím nový...")
        spreadsheet = client.open(SHEET_NAME)
        worksheet = spreadsheet.add_worksheet(title=worksheet_title, rows="1", cols="4")
        
        # Přidání hlaviček na nový list
        worksheet.append_row(HEADERS)
        print("Hlavičky byly přidány.")
        return worksheet

def run_speedtest():
    """Provede test rychlosti a vrátí výsledky."""
    st = speedtest.Speedtest()
    st.get_best_server()
    st.download()
    st.upload()
    results = st.results.dict()

    download_mbps = round(results['download'] / 1000000, 2)
    upload_mbps = round(results['upload'] / 1000000, 2)
    ping_ms = round(results['ping'], 2)
    
    return ping_ms, download_mbps, upload_mbps

if __name__ == "__main__":
    try:
        # Získání listu (buď existujícího, nebo nově vytvořeného)
        sheet = get_or_create_worksheet()

        ping, download, upload = run_speedtest()
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        row = [timestamp, ping, download, upload]
        
        # Přidání nového řádku do Google Sheet
        sheet.append_row(row)
        print(f"Měření úspěšně uloženo: Ping: {ping}ms, Download: {download}Mbps, Upload: {upload}Mbps")
        
    except Exception as e:
        print(f"Došlo k chybě: {e}")
