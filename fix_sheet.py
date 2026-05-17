import gspread
import os
import dotenv
from google.oauth2.service_account import Credentials

dotenv.load_dotenv()
SCOPES = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
creds = Credentials.from_service_account_file('credentials.json', scopes=SCOPES)
client = gspread.authorize(creds)
sheet = client.open_by_key(os.getenv("SPREADSHEET_ID"))

for ws in sheet.worksheets():
    try:
        values = ws.get_all_values()
        if not values: continue
        headers = values[0]
        updates = []
        seen = set()
        for i, h in enumerate(headers):
            new_h = str(h).strip()
            orig = new_h
            if not new_h or new_h in seen:
                count = 1
                while not new_h or new_h in seen:
                    new_h = f"empty_{count}" if not orig else f"{orig}_{count}"
                    count += 1
                updates.append({'range': gspread.utils.rowcol_to_a1(1, i+1), 'values': [[new_h]]})
            seen.add(new_h)
        if updates:
            print(f"Updating headers in {ws.title}: {updates}")
            ws.batch_update(updates)
            
        # check if it works now
        ws.get_all_records()
        print(f"Sheet {ws.title} OK.")
    except Exception as e:
        print(f"Error on {ws.title}: {e}")
