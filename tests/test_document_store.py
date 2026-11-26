import json
from unittest.mock import patch

import pytest
from botocore.exceptions import ClientError

from conf.conf import get_diplomas_dynamodb_firma_table
from services.document_store import (
    _from_dynamodb_value,
    get_firma_metadata,
    put_firma_metadata,
)


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
        "uuid_documento": "signature",
        "hash_sha256": "digest", "qr_url_segura": "https://example.test/qr",
        "activo": False, "pdfa": {"flavour": "2b"},
    }
    with patch("services.document_store._aws_client") as client:
        reference = put_firma_metadata(item)
        stored = client.return_value.put_item.call_args.kwargs
        assert stored["Item"]["PK"] == {"S": "signature"}
        assert stored["Item"]["SK"] == {"S": reference["sk"]}
        assert stored["Item"]["sk"] == stored["Item"]["SK"]
        assert stored["Item"]["firma_id"] == stored["Item"]["PK"]
        assert stored["ConditionExpression"] == "attribute_not_exists(PK) AND attribute_not_exists(SK)"
        decoded = {key: _from_dynamodb_value(value) for key, value in stored["Item"].items()}
        assert json.loads(decoded.pop("pdfa")) == item["pdfa"]
        expected = {**item, "documento_id": "7"}
        expected.pop("pdfa")
        assert decoded == {**expected, "PK": "signature", "SK": reference["sk"], "sk": reference["sk"]}
        # Read back the actual persisted representation, without exposing storage keys.
        client.return_value.get_item.return_value = {"Item": stored["Item"]}
        client.return_value.query.return_value = {"Items": [stored["Item"]]}
        expected_response = {**expected, "pdfa": json.dumps(item["pdfa"]), "sk": reference["sk"]}
        assert get_firma_metadata("signature", reference["sk"]) == expected_response
        assert client.return_value.get_item.call_args.kwargs["Key"] == {
            "PK": {"S": "signature"}, "SK": {"S": reference["sk"]},
        }
        assert get_firma_metadata("signature") == expected_response
        query = client.return_value.query.call_args.kwargs
        assert query["KeyConditionExpression"] == "PK = :firma_id"
        assert query["ExpressionAttributeValues"] == {":firma_id": {"S": "signature"}}
        assert set(reference) == {"table", "firma_id", "sk", "repositorio_documental", "documento_id"}
        assert reference["table"] == "test-diplomas-metadata"
        for method in ("put_item", "get_item", "query"):
            assert getattr(client.return_value, method).call_args.kwargs["TableName"] == reference["table"]
    monkeypatch.setenv("DIPLOMAS_DYNAMODB_FIRMA_TABLE", "other-environment-table")
    assert get_diplomas_dynamodb_firma_table() == "other-environment-table"
    monkeypatch.delenv("DIPLOMAS_DYNAMODB_FIRMA_TABLE")
    with pytest.raises(RuntimeError):
        get_diplomas_dynamodb_firma_table()


def test_duplicate_signature_is_rejected(monkeypatch):
    monkeypatch.setenv("DIPLOMAS_DYNAMODB_FIRMA_TABLE", "test-diplomas-metadata")
    item = dict.fromkeys(("firma_id", "repositorio_documental", "documento_id",
                          "codigo_autenticidad", "llaves", "firmantes",
                          "firma_encriptada", "fecha_creacion", "uuid_documento"), "value")
    error = ClientError({"Error": {"Code": "ConditionalCheckFailedException"}}, "PutItem")
    with patch("services.document_store._aws_client") as client:
        client.return_value.put_item.side_effect = error
        with pytest.raises(ValueError, match="already exists"):
            put_firma_metadata(item)
        assert client.return_value.put_item.call_count == 1


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


def test_write_rejects_independent_signature_identifier(monkeypatch):
    monkeypatch.setenv("DIPLOMAS_DYNAMODB_FIRMA_TABLE", "test-diplomas-metadata")
    with patch("services.document_store._aws_client") as client:
        with pytest.raises(ValueError, match="firma_id must match uuid_documento"):
            put_firma_metadata({"firma_id": "signature", "uuid_documento": "document"})
        client.assert_not_called()
