import os
import dotenv
from database import init_db, get_customers_sheet, get_festivals_sheet
from video_engine import generate_video, get_next_photo_index

dotenv.load_dotenv()

print("Initializing DB...")
sheet = init_db()
customers = get_customers_sheet(sheet).get_all_records()
festivals = get_festivals_sheet(sheet).get_all_records()

if not customers:
    print("No customers found.")
    exit(1)
if not festivals:
    print("No festivals found.")
    exit(1)

customer = customers[0]
festival = festivals[0]

print(f"Generating video for {customer['company_name']} for {festival['name']}...")
last_used = int(customer.get("last_used_photo") or 0)
next_idx = get_next_photo_index(last_used)

video_path = generate_video(customer, festival['name'], next_idx)

if video_path:
    # Move to root dir so user can easily find it
    final_path = f"generated_{festival['name'].replace(' ', '_')}.mp4"
    import shutil
    shutil.copy(video_path, final_path)
    print(f"Success! Video saved locally to: {final_path}")
else:
    print("Failed to generate video.")
