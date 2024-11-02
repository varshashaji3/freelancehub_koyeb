"""
Django settings for FreelanceHub project.

Generated by 'django-admin startproject' using Django 5.0.4.

For more information on this file, see
https://docs.djangoproject.com/en/5.0/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/5.0/ref/settings/
"""

import os
from pathlib import Path

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.0/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'django-insecure--vamx(qq%e)g0=)b$17dg&4kj0&%73+wztckvwmj8b%(8m3k-p'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

# ALLOWED_HOSTS = ['freelancehub-production.up.railway.app', 'localhost', '127.0.0.1']
ALLOWED_HOSTS = ['freelancehub.koyeb.app', 'localhost', '127.0.0.1','freelancehub-5tya.onrender.com','freelancehub-production.up.railway.app']



# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'core',
    'client',
    'administrator',
    'freelancer',
    'django.contrib.sites',  
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'allauth.socialaccount.providers.google',

]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    
    'allauth.account.middleware.AccountMiddleware',
    'django.middleware.cache.UpdateCacheMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.cache.FetchFromCacheMiddleware',
    
    
]

CACHE_MIDDLEWARE_ALIAS = 'default'
CACHE_MIDDLEWARE_SECONDS = 0
CACHE_MIDDLEWARE_KEY_PREFIX = ''


ROOT_URLCONF = 'freelancehub.urls'

CSRF_TRUSTED_ORIGINS = ['http://127.0.0.1:8000','https://freelancehub.koyeb.app','https://freelancehub-5tya.onrender.com','https://freelancehub-production.up.railway.app']

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'templates'),
            os.path.join(BASE_DIR, 'media/templates'),],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'core.context_processors.unread_notifications',
                'core.context_processors.repository_list',
                'core.context_processors.project_status',
                'core.context_processors.review_due',
                'administrator.context_processors.user_profile',
                'client.context_processors.client_context',
                'freelancer.context_processors.freelancer_context',
                'core.context_processors.refund_payment_context',
                'client.context_processors.project_completion_status',
            ],
        },
    },
]


# 'core.context_processors.project_status' ,


WSGI_APPLICATION = 'freelancehub.wsgi.application'


# Database
# https://docs.djangoproject.com/en/5.0/ref/settings/#databases

# DATABASES = {
#     'default': {
#         'ENGINE': 'django.db.backends.mysql',
#         'NAME': 'freelancehub',
#         'USER': 'varsha',
#         'PASSWORD': 'varsha',
#         'HOST': 'localhost',
#         'PORT': '3306',
#         'OPTIONS': {
#             'charset': 'utf8mb4',
#         },
#     }
# }

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'freelancehub_strangergo',
        'USER': 'freelancehub_strangergo',
        'PASSWORD': '739cd32a2c6f51df7fce54d52ff39b748c14c6c8',
        'HOST': 'l9i84.h.filess.io',
        'PORT': '3305',
        'OPTIONS': {
            'charset': 'utf8mb4',
        },
    }
}




# Password validation
# https://docs.djangoproject.com/en/5.0/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

ACCOUNT_DEFAULT_HTTP_PROTOCOL = "https"

EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_USE_TLS = True  # Use TLS for a secure connection
EMAIL_PORT = 587      # Port for TLS
EMAIL_HOST_USER = 'freelancehub76@gmail.com'  # Your Gmail address
EMAIL_HOST_PASSWORD = 'slekgltdnkmvbmha'  # Your app password (ensure it's correct)
DEFAULT_FROM_EMAIL = 'freelancehub76@gmail.com'




# Internationalization
# https://docs.djangoproject.com/en/5.0/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'Asia/Kolkata'

USE_I18N = True

# USE_TZ = True
USE_TZ = False



STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')  # Adjust as necessary
STATICFILES_DIRS = [
    os.path.join(BASE_DIR, "static"),
]

STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')
AUTH_USER_MODEL='core.CustomUser'

SITE_ID = 2

AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
    'allauth.account.auth_backends.AuthenticationBackend',
]

SOCIALACCOUNT_LOGIN_ON_GET=True
SOCIALACCOUNT_PROVIDERS = {
    'google': {
        'SCOPE': [
            'profile',
            'email',
        ],
        'AUTH_PARAMS': {
            'access_type': 'online',
        },
        'OAUTH_PKCE_ENABLED': True,
    }
}


LOGIN_REDIRECT_URL = 'login'
LOGIN_URL='login'
LOGOUT_REDIRECT_URL = 'login_view'


ACCOUNT_EMAIL_REQUIRED = True
ACCOUNT_EMAIL_VERIFICATION = 'mandatory'
ACCOUNT_AUTHENTICATION_METHOD = 'email'
ACCOUNT_USERNAME_REQUIRED = False
ACCOUNT_USER_MODEL_USERNAME_FIELD = None


RAZORPAY_KEY_ID = 'rzp_test_1vZK3GexmGW5zt'
RAZORPAY_KEY_SECRET = 'eIKYygydEQ5iicHT2N6gaVuC'



# settings.py
FILE_UPLOAD_MAX_MEMORY_SIZE = 10485760  # 10 MB (adjust as needed)

