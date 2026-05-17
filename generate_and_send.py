import requests
import time

BASE_URL = "http://127.0.0.1:8080"

print("Logging in...")
res = requests.post(f"{BASE_URL}/login", json={"email": "admin@example.com", "password": "adminpassword123"})
if not res.ok:
    print("Login failed:", res.text)
    exit(1)
token = res.json()["access_token"]
headers = {"Authorization": f"Bearer {token}"}

print("Fetching customers...")
res = requests.get(f"{BASE_URL}/customers", headers=headers)
customers = res.json().get("customers", [])
if not customers:
    print("No customers found.")
    exit(1)
customer = customers[0]
print(f"Selected Customer: {customer.get('company_name')} ({customer.get('customer_id')})")

print("Fetching festivals...")
res = requests.get(f"{BASE_URL}/festivals", headers=headers)
festivals = res.json().get("festivals", [])
if not festivals:
    print("No festivals found.")
    exit(1)
festival = festivals[0]
print(f"Selected Festival: {festival.get('name')}")

print("Sending WhatsApp video generation request (this may take a minute)...")
payload = {
    "customer_id": customer.get("customer_id"),
    "festival_name": festival.get("name"),
    "template_name": "hello_world"
}
res = requests.post(f"{BASE_URL}/send-whatsapp", json=payload, headers=headers)
print("Status Code:", res.status_code)
print("Response:", res.text)
