import copy
import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from controllers import controllerFirma


def response(data, status=200):
    return SimpleNamespace(status_code=status, content=json.dumps(data).encode())


@pytest.mark.parametrize('stage', [None, 1, 2, 3])
@pytest.mark.parametrize('count', [1, 3])
def test_metadata_preserves_people_and_json_values(monkeypatch, tmp_path, stage, count):
    monkeypatch.chdir(tmp_path)
    (tmp_path / 'documents').mkdir()
    monkeypatch.setenv('DOCUMENTOS_CRUD_URL', 'http://crud/')
    monkeypatch.setenv('GESTOR_DOCUMENTAL_URL', 'http://gestor/')
    people = [{'nombre': f'Ana O\'Connor "{i}" [á]', 'cargo': 'Revisión',
               'tipoId': 'TEST', 'identificacion': str(i)} for i in range(count)]
    representatives = [{'nombre': 'Representante uno'}, {'nombre': 'Representante dos'}]
    metadata = {'firmantes': copy.deepcopy(people), 'representantes': representatives,
                'extra': {'lista': [1, True, None], 'texto': 'O\'Connor "[acta]"'}}
    item = {'IdTipoDocumento': 2, 'nombre': 'prueba.pdf', 'descripcion': 'Prueba',
            'file': 'YQ==' * 400, 'firmantes': people if stage is None else people[-1:],
            'representantes': representatives, 'metadatos': metadata}
    if stage is not None:
        item['etapa_firma'] = stage
    original = copy.deepcopy(item)
    electronic = MagicMock()
    electronic.verificaEsPdf.return_value = True
    electronic.return_value.docFirmadoBase64.return_value = 'PDF_BASE64'
    monkeypatch.setattr(controllerFirma, 'ElectronicSign', electronic)
    monkeypatch.setattr(controllerFirma, 'build_qr_url', lambda *_: 'https://example.test/?token=test')
    monkeypatch.setattr(controllerFirma, 'firmar', lambda _: {
        'codigo_autenticidad': '123', 'llaves': {'firma': 'test'}})
    monkeypatch.setattr(controllerFirma.requests, 'get', lambda *_: response({'Id': 2, 'Nombre': 'PDF'}))
    captured = {}

    def post(url, json):
        if url.endswith('/documento'):
            captured['initial'] = json['Metadatos']
            return response({'Id': 1, **json}, 201)
        return response({'Id': 'signature-id'}, 201)

    def put(url, json):
        if url.endswith('/document/putUpdate'):
            captured['final'] = json[0]['metadatos']
            return response({'Status': '200', 'res': {'Id': 1, 'Metadatos': captured['final']}})
        captured['signature_people'] = json['Firmantes']
        return response({})

    monkeypatch.setattr(controllerFirma.requests, 'post', post)
    monkeypatch.setattr(controllerFirma.requests, 'put', put)
    handler = controllerFirma.postFirmaElectronica if stage is None else controllerFirma.FirmaMultiple
    result = handler([item])
    assert result.status_code == 200, result.get_data(as_text=True)
    assert json.loads(captured['initial']) == original['metadatos']
    stored = json.loads(captured['final'])
    assert stored['firmantes'] == people
    assert stored['representantes'] == representatives
    assert stored['extra'] == original['metadatos']['extra']
    assert item['metadatos'] == original['metadatos']
    if stage in (None, 3):
        assert stored['codigo_autenticidad'] == '123'
        assert stored['qr_url_segura'] == 'https://example.test/?token=test'
        assert 'llaves' not in stored
        assert json.loads(captured['signature_people'])['firmantes'] == people
