import os
import dotenv
from google.oauth2.service_account import Credentials
import gspread

dotenv.load_dotenv()
SCOPES = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
creds = Credentials.from_service_account_file('credentials.json', scopes=SCOPES)
client = gspread.authorize(creds)
sheet = client.open_by_key(os.getenv("SPREADSHEET_ID"))

ws = sheet.worksheet("Users")
values = ws.row_values(1)
headers = ["user_id", "name", "email", "password_hash", "role", "created_by", "created_at"]
if values != headers:
    print("Inserting headers to Users sheet...")
    ws.insert_row(headers, index=1)
    print("Done.")
else:
    print("Headers already correct.")
