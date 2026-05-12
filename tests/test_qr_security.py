import json
from unittest.mock import patch
from flask import Flask

from controllers.controllerFirma import resolveSecureQr, resolveSecureQrFile
from services.qr_security import _build_fernet, build_qr_token, validate_qr_token
from services.secret_manager import (
    describe_secret_backend,
    get_secret_material_by_kid,
    preload_active_secret,
    reset_secret_cache,
)


@patch.dict(
    "os.environ",
    {
        "QR_SECRET_PROVIDER": "dev",
        "QR_SECRET_NAME": "qr-token-key",
        "QR_SECRET_ACTIVE_VERSION": "7",
        "QR_SECRET_VERSIONS_JSON": '{"7":"super-secret-for-tests"}',
        "VERIFICACION_EXTERNA": "https://firma.test",
    },
    clear=True,
)
def test_build_and_validate_qr_token():
    reset_secret_cache()
    preload_active_secret(force=True)
    token = build_qr_token(99, 123)

    assert token is not None
    assert "." in token

    payload = validate_qr_token(token)
    assert payload["kid"] == "qr-token-key#7"
    assert payload["firma_id"] == "99"
    assert payload["documento_id"] == "123"

    backend = describe_secret_backend()
    assert backend["preloaded_version"] == "7"

    secret_material = get_secret_material_by_kid("qr-token-key#7")
    assert secret_material.version == "7"
    assert secret_material.secret_name == "qr-token-key"


@patch.dict(
    "os.environ",
    {
        "QR_SIGNING_SECRET": "legacy-secret-for-tests",
        "VERIFICACION_EXTERNA": "https://firma.test",
    },
    clear=True,
)
def test_build_and_validate_legacy_qr_token():
    reset_secret_cache()
    fernet = _build_fernet("legacy-secret-for-tests")
    token = fernet.encrypt(
        json.dumps({"firma_id": "88", "documento_id": "321"}).encode("utf-8")
    ).decode("utf-8")

    assert token is not None

    payload = validate_qr_token(token)
    assert payload["firma_id"] == "88"
    assert payload["documento_id"] == "321"


@patch("controllers.controllerFirma.requests.get")
@patch.dict(
    "os.environ",
    {
        "DOCUMENTOS_CRUD_URL": "http://documentos/",
        "GESTOR_DOCUMENTAL_URL": "http://gestor/v1/",
        "QR_SECRET_PROVIDER": "dev",
        "QR_SECRET_NAME": "qr-token-key",
        "QR_SECRET_ACTIVE_VERSION": "3",
        "QR_SECRET_VERSIONS_JSON": '{"3":"super-secret-for-tests"}',
        "VERIFICACION_EXTERNA": "https://cliente.test/verificacion",
    },
    clear=True,
)
def test_resolve_secure_qr_redirects_to_client(mock_get):
    reset_secret_cache()
    token = build_qr_token(55, 777)

    response = resolveSecureQr({"token": token})

    payload = json.loads(response.get_data(as_text=True))
    assert response.status_code == 200
    assert payload["redirect"] == f"https://cliente.test/verificacion?token={token}"


@patch("controllers.controllerFirma.requests.get")
@patch.dict(
    "os.environ",
    {
        "DOCUMENTOS_CRUD_URL": "http://documentos/",
        "GESTOR_DOCUMENTAL_URL": "http://gestor/v1/",
        "QR_SECRET_PROVIDER": "dev",
        "QR_SECRET_NAME": "qr-token-key",
        "QR_SECRET_ACTIVE_VERSION": "3",
        "QR_SECRET_VERSIONS_JSON": '{"3":"super-secret-for-tests"}',
        "VERIFICACION_EXTERNA": "https://cliente.test/verificacion",
    },
    clear=True,
)
def test_resolve_secure_qr_file_returns_json_when_requested(mock_get):
    class MockResponse:
        def __init__(self, payload, status_code=200):
            self.content = json.dumps(payload).encode("utf-8")
            self.status_code = status_code

    reset_secret_cache()
    token = build_qr_token(55, 777)
    mock_get.side_effect = [
        MockResponse({"DocumentoId": {"Id": 777, "Enlace": "abc123"}}),
        MockResponse({
            "file": "SGVsbG8=",
            "file:content": {"name": "test.pdf", "mime-type": "application/pdf"},
            "dc:title": "test.pdf",
        }),
    ]

    app = Flask(__name__)
    with app.test_request_context(headers={"Accept": "application/json, text/plain, */*"}):
        response = resolveSecureQrFile({"token": token})

    payload = json.loads(response.get_data(as_text=True))
    assert response.status_code == 200
    assert response.mimetype == "application/json"
    assert payload["res"]["file"] == "SGVsbG8="
    assert payload["res"]["filename"] == "test.pdf"
    assert payload["res"]["mime_type"] == "application/pdf"


@patch("controllers.controllerFirma.requests.get")
@patch.dict(
    "os.environ",
    {
        "DOCUMENTOS_CRUD_URL": "http://documentos/",
        "GESTOR_DOCUMENTAL_URL": "http://gestor/v1/",
        "QR_SECRET_PROVIDER": "dev",
        "QR_SECRET_NAME": "qr-token-key",
        "QR_SECRET_ACTIVE_VERSION": "3",
        "QR_SECRET_VERSIONS_JSON": '{"3":"super-secret-for-tests"}',
        "VERIFICACION_EXTERNA": "https://cliente.test/verificacion",
    },
    clear=True,
)
def test_resolve_secure_qr_file_returns_binary_pdf_when_json_not_requested(mock_get):
    class MockResponse:
        def __init__(self, payload, status_code=200):
            self.content = json.dumps(payload).encode("utf-8")
            self.status_code = status_code

    reset_secret_cache()
    token = build_qr_token(55, 777)
    mock_get.side_effect = [
        MockResponse({"DocumentoId": {"Id": 777, "Enlace": "abc123"}}),
        MockResponse({
            "file": "SGVsbG8=",
            "file:content": {"name": "test.pdf", "mime-type": "application/pdf"},
            "dc:title": "test.pdf",
        }),
    ]

    app = Flask(__name__)
    with app.test_request_context(headers={"Accept": "application/pdf"}):
        response = resolveSecureQrFile({"token": token})

    assert response.status_code == 200
    assert response.mimetype == "application/pdf"
    assert response.get_data() == b"Hello"
    assert response.headers["Content-Disposition"] == 'inline; filename="test.pdf"'
