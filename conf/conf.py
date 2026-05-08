import os
import sys
import re
import json

PREFIX = "FIRMA_ELECTRONICA_MID"


def _get_env(new_name, legacy_name=None, default=""):
    value = os.getenv(f"{PREFIX}_{new_name}")
    if value is None and legacy_name:
        value = os.getenv(legacy_name)
    if value is None:
        value = default
    return value.strip() if isinstance(value, str) else value


variables = [
    'DOCUMENTOS_CRUD_URL',
    'GESTOR_DOCUMENTAL_URL',
    'VERIFICACION',
    'VERIFICACION_EXTERNA',
    'QR_SECRET_PROVIDER',
    'QR_SECRET_NAME',
]

env = _get_env("RUN_MODE", "ENV", "dev").lower()
API_PORT = _get_env("API_PORT", "API_PORT", "8080")
DOCUMENTOS_CRUD_URL = _get_env("DOCUMENTOS_CRUD_URL", "DOCUMENTOS_CRUD_URL")
GESTOR_DOCUMENTAL_URL = _get_env("GESTOR_DOCUMENTAL_URL", "GESTOR_DOCUMENTAL_URL")
VERIFICACION = _get_env("VERIFICACION", "VERIFICACION")
VERIFICACION_EXTERNA = _get_env("VERIFICACION_EXTERNA", "VERIFICACION_EXTERNA")
QR_SIGNING_SECRET = _get_env("QR_SIGNING_SECRET", "QR_SIGNING_SECRET")
QR_SECRET_PROVIDER = _get_env("QR_SECRET_PROVIDER")
QR_SECRET_NAME = _get_env("QR_SECRET_NAME")
QR_SECRET_ARN = _get_env("QR_SECRET_ARN")
QR_SECRET_ACTIVE_VERSION = _get_env("QR_SECRET_ACTIVE_VERSION")
QR_SECRET_VERSIONS_JSON = _get_env("QR_SECRET_VERSIONS_JSON")
ENV = env

if env == "dev":
    origins = ["*"]
else:
    origins = [re.compile(r".*\.udistrital\.edu\.co$")]

api_cors_config = {
    "origins": origins,
    "methods": ["OPTIONS", "GET", "POST"],
    "allow_headers": ["Authorization", "Content-Type"]
}

def checkEnv():
    for variable in variables:
        prefixed_name = f"{PREFIX}_{variable}"
        if prefixed_name not in os.environ and variable not in os.environ:
            print(f"{prefixed_name} environment variable not found")
            sys.exit()


def get_api_port():
    return _get_env("API_PORT", "API_PORT", "8080")


def get_documentos_crud_url():
    return _get_env("DOCUMENTOS_CRUD_URL", "DOCUMENTOS_CRUD_URL")


def get_gestor_documental_url():
    return _get_env("GESTOR_DOCUMENTAL_URL", "GESTOR_DOCUMENTAL_URL")


def get_verificacion_url():
    return _get_env("VERIFICACION", "VERIFICACION")


def get_verificacion_externa_url():
    return _get_env("VERIFICACION_EXTERNA", "VERIFICACION_EXTERNA")


def get_qr_base_url():
    return get_verificacion_externa_url()


def get_qr_signing_secret():
    return _get_env("QR_SIGNING_SECRET", "QR_SIGNING_SECRET")


def get_qr_secret_provider():
    return _get_env("QR_SECRET_PROVIDER").lower()


def get_qr_secret_name():
    return _get_env("QR_SECRET_NAME")


def get_qr_secret_arn():
    return _get_env("QR_SECRET_ARN")


def get_qr_secret_active_version():
    return _get_env("QR_SECRET_ACTIVE_VERSION")


def get_qr_secret_versions():
    raw = _get_env("QR_SECRET_VERSIONS_JSON")
    if not raw:
        return {}
    return json.loads(raw)
