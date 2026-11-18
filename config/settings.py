import os
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("API_KEY")
DATABASE_URL = os.getenv("DATABASE_URL")

# Atualização automática do banco pela interface web (WebGate)
AUTO_UPDATE = os.getenv("WEBGATE_AUTO_UPDATE", "1") != "0"
# Coleta diária no horário HH:MM do fuso indicado (padrão: meia-noite de Brasília)
UPDATE_TIME = os.getenv("WEBGATE_UPDATE_TIME", "00:00")
UPDATE_TIMEZONE = os.getenv("WEBGATE_TIMEZONE", "America/Sao_Paulo")
