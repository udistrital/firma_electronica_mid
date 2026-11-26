import os
import unittest
from unittest.mock import patch

from flask import Flask

from controllers.controllerFirma import getMetadatosReporteDiplomas
from services.document_store import get_firmas_metadata_por_uuid

UUID1 = "00000000-0000-0000-0000-000000000001"
UUID2 = "00000000-0000-0000-0000-000000000002"


def raw(identifier=UUID1, **extra):
    values = {"uuid_documento": identifier, "firma_id": "signature-1", "documento_id": "7",
              "repositorio_documental": "diplomas", "activo": True,
              "qr_url_segura": "https://verify.example.test/?token=original&context=diploma",
              "codigo_autenticidad": "code", "hash_sha256": "digest", **extra}
    return {key: ({"BOOL": value} if isinstance(value, bool) else {"S": str(value)}) for key, value in values.items()}


class ReportMetadataTests(unittest.TestCase):
    def setUp(self):
        env = patch.dict(os.environ, {}, clear=False)
        env.start()
        self.addCleanup(env.stop)
        context = Flask("report-tests").test_request_context(headers={"Authorization": "Bearer test-token"})
        context.push()
        self.addCleanup(context.pop)

    def setenv(self, key, value):
        os.environ[key] = value

    def test_unauthorized_request_never_reads_metadata(self):
        with Flask("no-auth").test_request_context(), patch("services.document_store._aws_client") as client:
            response = getMetadatosReporteDiplomas({"uuid_documentos": [UUID1]})
        assert response.status_code == 401
        client.assert_not_called()

    def test_invalid_identifiers_do_not_call_aws(self):
        identifiers = ["invalid"]
        with patch("services.document_store._aws_client") as client:
            response = getMetadatosReporteDiplomas({"uuid_documentos": identifiers})
        assert response.status_code == 400
        client.assert_not_called()


    def test_pagination_filters_and_never_exports_signing_keys(self):
        self.setenv("DIPLOMAS_DYNAMODB_FIRMA_TABLE", "report-test-table")
        first_key = {"PK": {"S": "last-signature"}}
        with patch("services.document_store._aws_client") as client:
            client.return_value.query.side_effect = [
                {"Items": [], "LastEvaluatedKey": first_key},
                {"Items": [raw(UUID1, llaves='{"llave_privada":"must-not-export"}', PK="storage-key"),
                           raw(UUID1, activo=False), raw(UUID1, repositorio_documental="other"), raw("unrequested")]},
                {"Items": [raw(UUID2)]},
            ]
            result = get_firmas_metadata_por_uuid([UUID1, UUID2, UUID1])
            calls = client.return_value.query.call_args_list
        assert [item["uuid_documento"] for item in result] == [UUID1, UUID2]
        assert result[0]["documento_id"] == 7
        assert result[0]["qr_url_segura"] == "https://verify.example.test/?token=original&context=diploma"
        assert all("llaves" not in item and "PK" not in item for item in result)
        assert len(calls) == 3
        assert calls[1].kwargs["ExclusiveStartKey"] == first_key
        assert "ExclusiveStartKey" not in calls[0].kwargs
        assert "ExclusiveStartKey" not in calls[2].kwargs
        assert [call.kwargs["ExpressionAttributeValues"][":uuid_documento"]["S"] for call in calls] == [UUID1, UUID1, UUID2]
        assert all(call.kwargs["KeyConditionExpression"] == "PK = :uuid_documento" for call in calls)
        client.return_value.scan.assert_not_called()
        assert all(call.kwargs["ConsistentRead"] for call in calls)
        assert all(call.kwargs["TableName"] == "report-test-table" for call in calls)
        assert "llaves" not in calls[0].kwargs["ExpressionAttributeNames"].values()


    def test_ambiguous_uuid_is_rejected(self):
        self.setenv("DIPLOMAS_DYNAMODB_FIRMA_TABLE", "report-test-table")
        with patch("services.document_store._aws_client") as client:
            client.return_value.query.return_value = {"Items": [raw(), raw(firma_id="other-signature")]}
            response = getMetadatosReporteDiplomas({"uuid_documentos": [UUID1]})
        assert response.status_code == 409


    def test_internal_route_requires_bearer_and_returns_only_projection(self):
        from routers.router import api_bp
        self.setenv("DIPLOMAS_DYNAMODB_FIRMA_TABLE", "report-test-table")
        app = Flask("report-metadata-test")
        app.register_blueprint(api_bp)
        with app.test_client() as browser, patch("services.document_store._aws_client") as client:
            unauthorized = browser.post("/api/v2/firma_electronica/reporte", json={"uuid_documentos": [UUID1]})
            assert unauthorized.status_code == 401
            client.assert_not_called()
            client.return_value.query.return_value = {"Items": [raw(llaves="private", SK="storage")]}
            response = browser.post("/api/v2/firma_electronica/reporte", json={"uuid_documentos": [UUID1]}, headers={"Authorization": "Bearer test-token"})
        assert response.status_code == 200
        payload = response.get_json()
        assert payload["firmas"][0]["uuid_documento"] == UUID1
        assert "llaves" not in payload["firmas"][0]


if __name__ == "__main__":
    unittest.main()
