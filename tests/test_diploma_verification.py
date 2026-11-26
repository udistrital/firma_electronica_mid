import base64
import hashlib
import io
import json
from unittest.mock import Mock, patch

import pytest
from flask import Flask

from controllers.verification import resolve_diploma_qr, verify_manual
from models.firma import firmar
from services.diploma_verification import (
    VerificationError,
    diploma_file,
    diploma_metadata,
)

IDENTIFIER = '00000000-0000-0000-0000-000000000001'
PDF = b'%PDF-1.7\nDiploma firmado\n%%EOF'


@pytest.fixture
def metadata():
    signed = firmar(base64.b64encode(PDF).decode('ascii'))
    return {'firma_id': IDENTIFIER, 'uuid_documento': IDENTIFIER,
            'documento_id': '7', 'repositorio_documental': 'diplomas', 'activo': True,
            'hash_sha256': hashlib.sha256(PDF).hexdigest(),
            'llaves': json.dumps(signed['llaves'])}


@pytest.fixture
def payload():
    return {'firma_id': IDENTIFIER, 'uuid_documento': IDENTIFIER,
            'documento_id': '7', 'repositorio_documental': 'diplomas'}


def test_qr_uses_exact_composite_key(metadata, payload):
    with patch('services.diploma_verification.get_firma_metadata', return_value=metadata) as lookup:
        assert diploma_metadata(payload) == metadata
    lookup.assert_called_once_with(IDENTIFIER, 'repositorio_documental#diplomas#documento_id#7')


@pytest.mark.parametrize('change', [
    {'activo': False}, {'documento_id': '8'}, {'firma_id': 'other'},
    {'uuid_documento': 'other'}, {'repositorio_documental': 'other'},
])
def test_mismatched_metadata_never_authorizes_document(metadata, payload, change):
    with patch('services.diploma_verification.get_firma_metadata', return_value={**metadata, **change}):
        with pytest.raises(VerificationError) as error:
            diploma_metadata(payload)
        assert error.value.status == 403


def test_pdf_is_read_from_uuid_prefix_and_cryptographically_verified(monkeypatch, metadata):
    monkeypatch.setenv('DIPLOMAS_S3_BUCKET', 'private-test')
    body = io.BytesIO(PDF)
    client = Mock()
    client.list_objects_v2.return_value = {'Contents': [{'Key': f'diplomas/{IDENTIFIER}/diploma.pdf'}]}
    client.get_object.return_value = {'Body': body}
    with patch('services.diploma_verification._aws_client', return_value=client):
        assert diploma_file(metadata) == (PDF, 'diploma.pdf')
    assert body.closed
    client.list_objects_v2.assert_called_once_with(Bucket='private-test', Prefix=f'diplomas/{IDENTIFIER}/', MaxKeys=2)
    client.get_object.assert_called_once_with(Bucket='private-test', Key=f'diplomas/{IDENTIFIER}/diploma.pdf')


@pytest.mark.parametrize('content,override', [(b'tampered', {}), (PDF, {'llaves': None})])
def test_tampered_or_missing_signature_never_returns_pdf(monkeypatch, metadata, content, override):
    monkeypatch.setenv('DIPLOMAS_S3_BUCKET', 'private-test')
    with Flask('verification').test_request_context(headers={'Accept': 'application/json'}), \
            patch('controllers.verification.diploma_metadata', return_value={**metadata, **override}), \
            patch('services.diploma_verification._aws_client') as factory:
        factory.return_value.list_objects_v2.return_value = {'Contents': [{'Key': f'diplomas/{IDENTIFIER}/diploma.pdf'}]}
        factory.return_value.get_object.return_value = {'Body': io.BytesIO(content)}
        response = resolve_diploma_qr({}, 'token', include_file=True)
    assert response.status_code in (409, 502)
    assert 'file' not in response.get_json().get('res', {})


@pytest.mark.parametrize('accept', ['application/json', 'application/pdf'])
def test_qr_file_preserves_client_contract(metadata, accept):
    with Flask('verification').test_request_context(headers={'Accept': accept}), \
            patch('controllers.verification.diploma_metadata', return_value=metadata), \
            patch('controllers.verification.diploma_file', return_value=(PDF, 'diploma.pdf')):
        response = resolve_diploma_qr({}, 'token', include_file=True)
    assert response.status_code == 200
    assert response.headers['Cache-Control'] == 'no-store'
    if accept == 'application/pdf':
        assert response.data == PDF
    else:
        assert base64.b64decode(response.get_json()['res']['file']) == PDF
        assert 'llaves' not in response.get_data(as_text=True)


def test_qr_route_validates_token_and_avoids_legacy_services(metadata, payload):
    from routers.router import api_bp
    app = Flask('verification-route')
    app.register_blueprint(api_bp)
    with app.test_client() as browser, \
            patch('controllers.controllerFirma.validate_qr_token', return_value=payload) as validate, \
            patch('controllers.verification.diploma_metadata', return_value=metadata), \
            patch('controllers.controllerFirma.requests.get') as legacy:
        response = browser.post('/api/v1/qr/resolve', json={'token': 'signed-token'})
    assert response.status_code == 200
    assert response.get_json()['res']['file_path'] == '/qr/file'
    validate.assert_called_once_with('signed-token')
    legacy.assert_not_called()


def test_invalid_qr_never_reads_aws():
    from routers.router import api_bp
    app = Flask('invalid-qr')
    app.register_blueprint(api_bp)
    with app.test_client() as browser, \
            patch('controllers.controllerFirma.validate_qr_token', side_effect=ValueError('Invalid QR token')), \
            patch('services.diploma_verification.get_firma_metadata') as lookup:
        response = browser.post('/api/v1/qr/file', json={'token': 'tampered'})
    assert response.status_code == 400
    lookup.assert_not_called()


@pytest.mark.parametrize('content,expected', [(PDF, True), (PDF + b'changed', False)])
def test_manual_verification_preserves_contract_and_checks_rsa(monkeypatch, metadata, content, expected):
    monkeypatch.setenv('DIPLOMAS_DYNAMODB_FIRMA_TABLE', 'test-table')
    monkeypatch.setenv('ESCANEAR_ARCHIVO_URL', 'https://scanner.test')
    scan = Mock(status_code=200)
    scan.json.return_value = {'statusCode': 200, 'body': '{"status":"clean"}'}
    encoded = base64.b64encode(content).decode('ascii')
    with patch('controllers.verification.requests.post', return_value=scan) as scanner, \
            patch('controllers.verification.get_firma_metadata', return_value=metadata):
        legacy = Mock()
        response = verify_manual([{'firma': IDENTIFIER, 'pdf_base64': encoded, 'urlFileUp': 'blob:client'}], legacy)
    assert response.status_code == 200
    assert response.get_json()['Data']['Verificacion']['fileEqual'] is expected
    assert response.get_json()['Data']['Virus']['archive'] == 'clean'
    scanner.assert_called_once_with('https://scanner.test/verificar', json={'pdf_base64': encoded}, timeout=(5, 30))
    legacy.assert_not_called()


def test_infected_file_does_not_verify_signature(monkeypatch):
    monkeypatch.setenv('ESCANEAR_ARCHIVO_URL', 'https://scanner.test')
    scan = Mock(status_code=200)
    scan.json.return_value = {'status': 'infected'}
    with patch('controllers.verification.requests.post', return_value=scan), \
            patch('controllers.verification.get_firma_metadata') as lookup:
        response = verify_manual([{'firma': IDENTIFIER, 'pdf_base64': base64.b64encode(PDF).decode()}], Mock())
    assert response.get_json()['Data']['Virus']['archive'] == 'infected'
    assert response.get_json()['Data']['Verificacion'] is None
    lookup.assert_not_called()


def test_scanner_failure_is_not_reported_as_clean(monkeypatch):
    monkeypatch.setenv('ESCANEAR_ARCHIVO_URL', 'https://scanner.test')
    with patch('controllers.verification.requests.post', return_value=Mock(status_code=500)):
        response = verify_manual([{'firma': IDENTIFIER, 'pdf_base64': base64.b64encode(PDF).decode()}], Mock())
    assert response.status_code == 502
    assert response.get_json()['Success'] is False


def test_manual_route_legacy_signature_keeps_existing_verifier(monkeypatch):
    monkeypatch.delenv('DIPLOMAS_DYNAMODB_FIRMA_TABLE', raising=False)
    from routers.router import api_bp
    app = Flask('manual-verification-route')
    app.register_blueprint(api_bp)
    with app.test_client() as browser, \
            patch('controllers.verification._scan_pdf', return_value={'archive': 'clean'}), \
            patch('controllers.controllerFirma.postVerify') as legacy:
        from flask import Response
        legacy.return_value = Response('{"res":[{"fileEqual":true}]}', mimetype='application/json')
        response = browser.post('/api/v1/verificar_firma', json=[{
            'firma': IDENTIFIER, 'pdf_base64': base64.b64encode(PDF).decode(), 'urlFileUp': 'blob:client'}])
    assert response.status_code == 200
    assert response.get_json()['Data']['Verificacion']['fileEqual'] is True
    legacy.assert_called_once()


def test_rsa_mismatch_is_rejected_even_when_sha256_matches(metadata):
    from services.diploma_verification import verify_pdf_signature
    metadata['llaves'] = json.dumps(firmar('otro PDF')['llaves'])
    assert verify_pdf_signature(metadata, PDF) is False


@pytest.mark.parametrize('listing,status', [
    ({'Contents': []}, 404),
    ({'Contents': [{'Key': f'diplomas/{IDENTIFIER}/a.pdf'},
                   {'Key': f'diplomas/{IDENTIFIER}/b.pdf'}]}, 409),
    ({'IsTruncated': True, 'Contents': []}, 409),
])
def test_ambiguous_or_missing_pdf_is_not_downloaded(monkeypatch, metadata, listing, status):
    monkeypatch.setenv('DIPLOMAS_S3_BUCKET', 'private-test')
    with patch('services.diploma_verification._aws_client') as factory:
        factory.return_value.list_objects_v2.return_value = listing
        with pytest.raises(VerificationError) as error:
            diploma_file(metadata)
        assert error.value.status == status
        factory.return_value.get_object.assert_not_called()


def test_missing_scanner_configuration_fails_closed(monkeypatch):
    monkeypatch.delenv('ESCANEAR_ARCHIVO_URL', raising=False)
    with patch('controllers.verification.requests.post') as scanner:
        response = verify_manual([{'firma': IDENTIFIER, 'pdf_base64': base64.b64encode(PDF).decode()}], Mock())
    assert response.status_code == 503
    scanner.assert_not_called()
