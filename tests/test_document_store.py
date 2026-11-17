from unittest.mock import patch

import pytest

from conf.conf import get_diplomas_dynamodb_firma_table
from services.document_store import get_firma_metadata, put_firma_metadata


@pytest.mark.parametrize("value", [None, "", "   \t\n"])
def test_missing_table_blocks_all_dynamodb_operations(monkeypatch, value):
    if value is None:
        monkeypatch.delenv("DIPLOMAS_DYNAMODB_FIRMA_TABLE", raising=False)
    else:
        monkeypatch.setenv("DIPLOMAS_DYNAMODB_FIRMA_TABLE", value)
    with patch("services.document_store._aws_client") as client:
        for operation in (
            get_diplomas_dynamodb_firma_table,
            lambda: put_firma_metadata({}),
            lambda: get_firma_metadata("signature"),
            lambda: get_firma_metadata("signature", "document-key"),
        ):
            with pytest.raises(RuntimeError, match="DIPLOMAS_DYNAMODB_FIRMA_TABLE is required"):
                operation()
        client.assert_not_called()


def test_configured_table_used_for_write_get_and_query(monkeypatch):
    monkeypatch.setenv("DIPLOMAS_DYNAMODB_FIRMA_TABLE", "  test-diplomas-metadata  ")
    item = {
        "firma_id": "signature", "repositorio_documental": "diplomas",
        "documento_id": 7, "codigo_autenticidad": "code", "llaves": "{}",
        "firmantes": "[]", "firma_encriptada": "signed", "fecha_creacion": "now",
        "uuid_documento": "document",
    }
    with patch("services.document_store._aws_client") as client:
        client.return_value.get_item.return_value = {"Item": {"firma_id": {"S": "signature"}}}
        client.return_value.query.return_value = {"Items": [{"firma_id": {"S": "signature"}}]}
        reference = put_firma_metadata(item)
        assert get_firma_metadata("signature", reference["sk"]) == {"firma_id": "signature"}
        assert get_firma_metadata("signature") == {"firma_id": "signature"}
        assert reference["table"] == "test-diplomas-metadata"
        for method in ("put_item", "get_item", "query"):
            assert getattr(client.return_value, method).call_args.kwargs["TableName"] == reference["table"]
    monkeypatch.setenv("DIPLOMAS_DYNAMODB_FIRMA_TABLE", "other-environment-table")
    assert get_diplomas_dynamodb_firma_table() == "other-environment-table"
    monkeypatch.delenv("DIPLOMAS_DYNAMODB_FIRMA_TABLE")
    with pytest.raises(RuntimeError):
        get_diplomas_dynamodb_firma_table()


def test_metadata_endpoint_returns_controlled_configuration_error(monkeypatch):
    from controllers.controllerFirma import getFirmaElectronicaV2

    monkeypatch.delenv("DIPLOMAS_DYNAMODB_FIRMA_TABLE", raising=False)
    with patch("services.document_store._aws_client") as client:
        response = getFirmaElectronicaV2("signature")
    assert response.status_code == 500
    assert "DIPLOMAS_DYNAMODB_FIRMA_TABLE is required" in response.get_json()["Error"]
    client.assert_not_called()


def test_other_repositories_do_not_require_dynamodb_configuration(monkeypatch):
    from controllers.controllerFirma import postFirmaElectronicaV2

    monkeypatch.delenv("DIPLOMAS_DYNAMODB_FIRMA_TABLE", raising=False)
    for repository in ("nuxeo", "gestor_documental", "gestor_documental_mid"):
        item = {"repositorio_documental": repository, "firmantes": [], "representantes": []}
        with patch("controllers.controllerFirma.postFirmaElectronica") as legacy, \
                patch("services.document_store._aws_client") as client:
            assert postFirmaElectronicaV2([item]) is legacy.return_value
            legacy.assert_called_once_with([item])
            client.assert_not_called()
