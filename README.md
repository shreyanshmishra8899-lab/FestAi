# SimplyPromised - Festival Video Marketing Hub
la la la la 
A full-stack platform that enables agencies to onboard businesses and automatically generate and deliver personalized festival greeting videos directly to business owners via WhatsApp.

## 🚀 Tech Stack

*   **Frontend**: React (Vite), Tailwind CSS v3, Plus Jakarta Sans font.
*   **Backend**: Python 3.11+, FastAPI
*   **Database**: Google Sheets (via `gspread` and Google Cloud APIs)
*   **Video Engine**: MoviePy (v1.0.3), OpenCV, Pillow, gTTS (Google Text-to-Speech)
*   **Automation**: APScheduler for daily WhatsApp dispatches
*   **Integration**: Meta WhatsApp Cloud API

---

## ⚙️ Prerequisites

1.  **Node.js** (v18+) for the frontend.
2.  **Python** (v3.10+) for the backend.
3.  **ImageMagick**: Required by MoviePy to render text overlays in videos.
    *   **Windows**: Download and install [ImageMagick](https://imagemagick.org/script/download.php). Make sure to check the box "Install legacy utilities (e.g. convert)" during installation.
    *   **Linux/Mac**: `sudo apt install imagemagick` or `brew install imagemagick`.

---

## 🔐 Environment Variables (.env)

You must configure your `.env` file in the root directory for the application to interact with the database and WhatsApp.

Create a `.env` file based on `.env.example`:

```ini
# Security
JWT_SECRET=your_super_secret_jwt_key

# Google Sheets Database
SPREADSHEET_ID=your_google_sheet_id_here
GOOGLE_CREDENTIALS_JSON=credentials.json

# Meta WhatsApp API
WHATSAPP_TOKEN=your_meta_whatsapp_token
WHATSAPP_API_URL=https://graph.facebook.com/v17.0/YOUR_PHONE_ID/messages
```

*Note: You must generate a `credentials.json` file from your Google Cloud Console (Service Account) and share your Google Sheet with the Service Account email address.*

---

## 💻 Running the Project Locally

The project is decoupled into two separate processes.

### 1. Start the Backend (FastAPI)
Open a terminal in the root directory:
```bash
# Install Python dependencies
pip install -r requirements.txt

# Start the API server
uvicorn main:app --reload --port 8080
```
*The backend will run on http://localhost:8080*

### 2. Start the Frontend (React)
Open a second terminal and navigate to the frontend directory:
```bash
cd frontend_app

# Install Node dependencies
npm install

# Start the Vite development server
npm run dev
```
*The frontend will run on http://localhost:5173*

---

## 📂 Project Structure

```
festival_video_platform/
├── main.py                # FastAPI entry point & routes
├── database.py            # Google Sheets gspread integration
├── auth.py                # JWT & Role-based access control
├── video_engine.py        # MoviePy text-to-speech and rendering logic
├── scheduler.py           # APScheduler background tasks
├── requirements.txt       # Python dependencies
├── .env                   # Environment variables (do not commit)
├── credentials.json       # Google Cloud Service Account key (do not commit)
└── frontend_app/          # React Vite Frontend Application
    ├── src/App.jsx        # Main Dashboard UI & Logic
    ├── src/index.css      # Tailwind & Custom CSS
    └── tailwind.config.js # Tailwind v3 Configuration
```
