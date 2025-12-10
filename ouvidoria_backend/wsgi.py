# /var/www/ouvidoria/ouvidoria_backend/wsgi.py

import os
from pathlib import Path
from django.core.wsgi import get_wsgi_application
from dotenv import load_dotenv  # Importa a biblioteca

# Aponta para o diretório raiz do projeto (/var/www/ouvidoria)
BASE_DIR = Path(__file__).resolve().parent.parent

# Aponta para o arquivo .env nesse diretório
ENV_FILE_PATH = BASE_DIR / '.env'

# Carrega as variáveis de ambiente do arquivo .env
if ENV_FILE_PATH.exists():
    load_dotenv(dotenv_path=ENV_FILE_PATH)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ouvidoria_backend.settings')

application = get_wsgi_application()