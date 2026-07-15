"""
faq_assistant/wsgi.py
WSGI entry point for the DeKUT FAQ Assistant (Gunicorn / uWSGI).
"""

import os
from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "faq_assistant.settings")
application = get_wsgi_application()
