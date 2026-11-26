"""Ejecutar con Postman local y ANTIVIRUS_SIMULATION_URL; no usa AWS real."""
import base64
import hashlib
import json
import os
from unittest.mock import patch

import pytest
from flask import Flask

from models.firma import firmar

pytestmark = pytest.mark.skipif(not os.getenv('ANTIVIRUS_SIMULATION_URL'),
                                reason='requiere antivirus simulado por HTTP')


@pytest.mark.parametrize('marker,status,archive', [
    ('clean-test', 200, 'clean'), ('infected-test', 200, 'infected'),
    ('scanner-failure-test', 502, None),
])
def test_manual_verification_with_real_http_scanner(monkeypatch, marker, status, archive):
    from routers.router import api_bp

    monkeypatch.setenv('ESCANEAR_ARCHIVO_URL', os.environ['ANTIVIRUS_SIMULATION_URL'])
    monkeypatch.setenv('DIPLOMAS_DYNAMODB_FIRMA_TABLE', 'test-only')
    app = Flask('verification-http-simulation')
    app.register_blueprint(api_bp)
    identifier = '00000000-0000-0000-0000-000000000001'
    binary = f'%PDF-1.7\n{marker}\n%%EOF'.encode()
    encoded = base64.b64encode(binary).decode()
    metadata = {'firma_id': identifier, 'uuid_documento': identifier, 'activo': True,
                'repositorio_documental': 'diplomas', 'hash_sha256': hashlib.sha256(binary).hexdigest(),
                'llaves': json.dumps(firmar(encoded)['llaves'])}
    with app.test_client() as browser, patch('controllers.verification.get_firma_metadata', return_value=metadata):
        response = browser.post('/api/v1/verificar_firma', json=[{
            'firma': identifier, 'pdf_base64': encoded, 'urlFileUp': 'blob:test'}])
    assert response.status_code == status
    payload = response.get_json()
    if archive:
        assert payload['Data']['Virus']['archive'] == archive
        if archive == 'clean':
            assert payload['Data']['Verificacion']['fileEqual'] is True
        else:
            assert payload['Data']['Verificacion'] is None
    else:
        assert payload['Success'] is False
