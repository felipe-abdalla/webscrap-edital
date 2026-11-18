import os
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("API_KEY")
DATABASE_URL = os.getenv("DATABASE_URL")

# Atualização automática do banco pela interface web (WebGate)
AUTO_UPDATE = os.getenv("WEBGATE_AUTO_UPDATE", "1") != "0"
UPDATE_INTERVAL_HOURS = float(os.getenv("WEBGATE_UPDATE_HOURS", "24"))
