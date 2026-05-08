from unittest.mock import patch

from controllers.controllerFirma import resolveSecureQr
from services.qr_security import build_qr_token, validate_qr_token


@patch.dict(
    "os.environ",
    {
        "FIRMA_ELECTRONICA_MID_QR_SECRET_PROVIDER": "env",
        "FIRMA_ELECTRONICA_MID_QR_SECRET_NAME": "qr-token-key",
        "FIRMA_ELECTRONICA_MID_QR_SECRET_ACTIVE_VERSION": "7",
        "FIRMA_ELECTRONICA_MID_QR_SECRET_VERSIONS_JSON": '{"7":"super-secret-for-tests"}',
        "FIRMA_ELECTRONICA_MID_VERIFICACION_EXTERNA": "https://firma.test",
    },
    clear=True,
)
def test_build_and_validate_qr_token():
    token = build_qr_token(99, 123)

    assert token is not None
    assert "." in token

    payload = validate_qr_token(token)
    assert payload["kid"] == "qr-token-key#7"
    assert payload["firma_id"] == "99"
    assert payload["documento_id"] == "123"


@patch.dict(
    "os.environ",
    {
        "QR_SIGNING_SECRET": "legacy-secret-for-tests",
        "VERIFICACION_EXTERNA": "https://firma.test",
    },
    clear=True,
)
def test_build_and_validate_legacy_qr_token():
    token = build_qr_token(88, 321)

    assert token is not None

    payload = validate_qr_token(token)
    assert payload["firma_id"] == "88"
    assert payload["documento_id"] == "321"


@patch("controllers.controllerFirma.requests.get")
@patch.dict(
    "os.environ",
    {
        "FIRMA_ELECTRONICA_MID_DOCUMENTOS_CRUD_URL": "http://documentos/",
        "FIRMA_ELECTRONICA_MID_GESTOR_DOCUMENTAL_URL": "http://gestor/v1/",
        "FIRMA_ELECTRONICA_MID_QR_SECRET_PROVIDER": "env",
        "FIRMA_ELECTRONICA_MID_QR_SECRET_NAME": "qr-token-key",
        "FIRMA_ELECTRONICA_MID_QR_SECRET_ACTIVE_VERSION": "3",
        "FIRMA_ELECTRONICA_MID_QR_SECRET_VERSIONS_JSON": '{"3":"super-secret-for-tests"}',
        "FIRMA_ELECTRONICA_MID_VERIFICACION_EXTERNA": "https://cliente.test/verificacion",
    },
    clear=True,
)
def test_resolve_secure_qr_redirects_to_client(mock_get):
    token = build_qr_token(55, 777)

    response = resolveSecureQr(token)

    assert response.status_code == 302
    assert response.location == f"https://cliente.test/verificacion?token={token}"
