import os

# Repo root, so the app works no matter which folder it is started from.
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DATA_DIR = os.path.join(ROOT, "data")

LLM_MODEL = os.getenv("KM_LLM_MODEL", "llama-3.3-70b-versatile")   # fallback only; agent.pick_model() checks what the key can actually call
TEMPERATURE = float(os.getenv("KM_TEMPERATURE", 0))
MAX_ITERATIONS = int(os.getenv("KM_MAX_ITER", 6))          # tool-call loops before the agent must answer
DB_PATH = os.getenv("KM_DB_PATH", os.path.join(DATA_DIR, "dealership.sqlite3"))
HTTP_TIMEOUT = int(os.getenv("KM_HTTP_TIMEOUT", 20))
MAX_TOKENS = int(os.getenv("KM_MAX_TOKENS", 600))      # cap answer length to stay inside free-tier TPM
MAX_RETRIES = int(os.getenv("KM_MAX_RETRIES", 8))      # Groq client waits out 429 rate limits
EVAL_PAUSE = float(os.getenv("KM_EVAL_PAUSE", 20))     # seconds between evaluation scenarios
DATAGOV_KEY = os.getenv("DATAGOV_API_KEY", "")

# Free, key-less public APIs
GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
# data.gov.in daily mandi prices (needs a free API key)
MANDI_URL = "https://api.data.gov.in/resource/9ef84268-d588-465a-a308-a864a43d0070"

# Scheme rules used by the retriever tool
SCHEME_PDF_URLS = [
    ("smam_guidelines.pdf", "https://farmech.dac.gov.in/Content/Homepdf/Revised_Operational_Guidelines_SMAM_(2024).pdf"),
    ("smam_guidelines_2020_21.pdf", "https://agrimachinery.nic.in/Files/Guidelines/SMAMGiudeline2020-21.pdf"),
]
