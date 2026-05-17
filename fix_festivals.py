import os
import dotenv
from google.oauth2.service_account import Credentials
import gspread

dotenv.load_dotenv()
SCOPES = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
creds = Credentials.from_service_account_file('credentials.json', scopes=SCOPES)
client = gspread.authorize(creds)
sheet = client.open_by_key(os.getenv("SPREADSHEET_ID"))

ws = sheet.worksheet("Festivals")
# Get current first row
values = ws.row_values(1)
if values != ["festival_id", "date", "name", "type"]:
    print("Inserting headers to Festivals sheet...")
    ws.insert_row(["festival_id", "date", "name", "type"], index=1)
    print("Done.")
else:
    print("Headers already correct.")
