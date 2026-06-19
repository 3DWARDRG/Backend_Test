INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',        # añade esto
    'corsheaders',           # añade esto
    'api',                   # añade esto
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',  # justo después de SecurityMiddleware
    'django.middleware.security.SecurityMiddleware',
    # ... el resto
]

# Al final del archivo:
CORS_ALLOW_ALL_ORIGINS = True  # para desarrollo