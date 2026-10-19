import base64
import hashlib
import io
import json
import os
import shutil
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from pypdf import PdfReader
from reportlab.pdfgen import canvas

from models.firma import firmar
from models.firma_electronica import ElectronicSign
from services.pdfa import PdfaError, _run, finalize_pdfa, validate_pdfa


def test_rsa_preserves_legacy_verification_without_exporting_private_key():
    encoded = base64.b64encode(b"final-pdf-bytes").decode("ascii")
    result = firmar(encoded)
    keys = result["llaves"]
    assert "llave_privada" not in keys
    pem = base64.urlsafe_b64decode(keys["llave_publica"])
    public = serialization.load_pem_public_key(pem)
    assert public.key_size >= 2048
    assert result["codigo_autenticidad"] == hashlib.sha256(pem).hexdigest()
    algorithm = padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH)
    signature = base64.urlsafe_b64decode(keys["firma"])
    public.verify(signature, encoded.encode("ascii"), algorithm, hashes.SHA256())
    with pytest.raises(InvalidSignature):
        public.verify(signature, (encoded + "changed").encode("ascii"), algorithm, hashes.SHA256())


@pytest.mark.parametrize("report", [
    b"", b"garbage", b"<report/>",
    b'<report><validationReport isCompliant="false"/></report>',
    b'<report><validationReport isCompliant="true"/></report>',
    b'<report><validationReport isCompliant="true"/><batchSummary totalJobs="1" failedToParse="1"/></report>',
])
def test_validator_fails_closed_even_on_success_exit_code(report):
    with patch("services.pdfa._tool", return_value="veraPDF"), patch("services.pdfa._run", return_value=report), pytest.raises(PdfaError):
        validate_pdfa("final.pdf")


def test_missing_tool_aborts_conversion(tmp_path, monkeypatch):
    monkeypatch.setenv("GHOSTSCRIPT_BIN", "/missing/gs")
    with pytest.raises(PdfaError):
        finalize_pdfa(tmp_path / "source.pdf")


def test_tool_timeout_aborts_issuance():
    with patch("services.pdfa.subprocess.run", side_effect=subprocess.TimeoutExpired("gs", 120)), pytest.raises(PdfaError):
        _run(["gs"])


def test_mid_does_not_sign_or_persist_when_validation_fails(tmp_path, monkeypatch):
    from controllers.controllerFirma import postFirmaElectronicaV2
    monkeypatch.chdir(tmp_path)
    (tmp_path / "documents").mkdir()
    item = {"file": base64.b64encode(b"%PDF-1.7\n" * 150).decode("ascii"),
            "documento_id": 7, "repositorio_documental": "diplomas",
            "firmantes": [{"nombre": "Prueba"}], "representantes": []}
    with patch("controllers.controllerFirma.ElectronicSign.verificaEsPdf", return_value=True), \
         patch("controllers.controllerFirma.build_qr_url", return_value="https://example.test/qr"), \
         patch("controllers.controllerFirma.ElectronicSign.estamparFirmaElectronica"), \
         patch("controllers.controllerFirma.finalize_pdfa", side_effect=PdfaError("invalid PDF/A")), \
         patch("controllers.controllerFirma.firmar") as sign, \
         patch("controllers.controllerFirma.put_firma_metadata") as store:
        response = postFirmaElectronicaV2([item])
        assert response.status_code == 500
        sign.assert_not_called()
        store.assert_not_called()
        assert not list((tmp_path / "documents").iterdir())


def test_historical_metadata_response_hides_private_key():
    from controllers.controllerFirma import getFirmaElectronicaV2
    stored = {"llaves": json.dumps({"llave_publica": "public", "llave_privada": "private", "firma": "signature"})}
    with patch("controllers.controllerFirma.get_firma_metadata", return_value=stored):
        response = getFirmaElectronicaV2("historical")
    payload = response.get_json()
    assert "llave_privada" not in json.loads(payload["llaves"])
    assert "llave_privada" in json.loads(stored["llaves"])


@pytest.mark.skipif(os.getenv("RUN_PDFA_INTEGRATION") != "1", reason="set RUN_PDFA_INTEGRATION=1 for real Ghostscript/veraPDF integration")
def test_final_diploma_pdfa_visual_qr_rsa_and_dynamodb(tmp_path, monkeypatch):
    """Real stamping/conversion/validation/signing; only persistence is mocked."""
    import fitz
    from PIL import Image, ImageChops, ImageStat

    from controllers.controllerFirma import postFirmaElectronicaV2
    from services.document_store import put_firma_metadata

    assert shutil.which(os.getenv("VERAPDF_BIN", "verapdf")), "veraPDF required"
    source = tmp_path / "source.pdf"
    institutional_fixture = os.getenv("PDFA_TEST_INPUT")
    if institutional_fixture:
        shutil.copyfile(institutional_fixture, source)
    else:
        pdf = canvas.Canvas(str(source), pagesize=(400 * 72 / 25.4, 280 * 72 / 25.4))
        pdf.drawString(150, 400, "Diploma de prueba - Universidad Distrital")
        pdf.setStrokeColorRGB(0, 0, 0)
        pdf.bezier(150, 180, 180, 210, 220, 155, 300, 190)
        pdf.showPage()
        pdf.save()
    original = source.read_bytes()
    (tmp_path / "documents").mkdir()
    monkeypatch.chdir(tmp_path)
    item = {"file": base64.b64encode(original).decode("ascii"), "documento_id": 7,
            "repositorio_documental": "diplomas", "nombre": "Prueba institucional",
            "firmantes": [{"nombre": "Firmante de prueba"}], "representantes": []}
    stamped = tmp_path / "stamped.pdf"
    stamp = ElectronicSign.estamparFirmaElectronica

    def capture_stamp(self, datos, source_path, overlay, output):
        stamp(self, datos, source_path, overlay, output)
        shutil.copyfile(output, stamped)

    with patch.object(ElectronicSign, "estamparFirmaElectronica", capture_stamp), \
         patch("controllers.controllerFirma.put_firma_metadata", wraps=put_firma_metadata), \
         patch("services.document_store._aws_client") as aws:
        response = postFirmaElectronicaV2([item])
        assert response.status_code == 200, response.get_data(as_text=True)
        payload = response.get_json()
        persisted = aws.return_value.put_item.call_args.kwargs
    final = base64.b64decode(payload["file"])
    output = tmp_path / "final.pdf"
    output.write_bytes(final)
    report = validate_pdfa(output)
    digest = hashlib.sha256(final).hexdigest()
    assert digest == payload["hash_sha256"] == persisted["Item"]["hash_sha256"]["S"]
    assert "llave_privada" not in persisted["Item"]["llaves"]["S"]
    assert "attribute_not_exists" in persisted["ConditionExpression"]
    assert json.loads(persisted["Item"]["pdfa"]["S"])["flavour"] == "2b"
    keys = payload["llaves"]
    serialization.load_pem_public_key(base64.urlsafe_b64decode(keys["llave_publica"])).verify(
        base64.urlsafe_b64decode(keys["firma"]), payload["file"].encode("ascii"),
        padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH), hashes.SHA256())
    with pytest.raises(PdfaError):
        validate_pdfa(stamped)  # A QR-stamped ordinary PDF must not be accepted.
    before = PdfReader(stamped)
    after = PdfReader(io.BytesIO(final))
    assert len(before.pages) == len(after.pages) == 1
    assert list(before.pages[0].mediabox) == pytest.approx(list(after.pages[0].mediabox), abs=0.02)
    assert after.xmp_metadata.pdfaid_part == "2"
    assert after.xmp_metadata.pdfaid_conformance == "B"
    assert after.trailer["/Root"]["/OutputIntents"]
    images = []
    for path in (stamped, output):
        with fitz.open(str(path)) as document:
            pix = document[0].get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
            images.append(Image.frombytes("RGB", (pix.width, pix.height), pix.samples))
    assert images[0].size == images[1].size
    error = sum(ImageStat.Stat(ImageChops.difference(*images)).mean) / 3
    assert error < 2.0, f"visual regression mean difference {error}/255"
    # QR occupies the existing top-right 91pt square, unchanged by conversion.
    width = images[0].width
    box = (width - 240, 40, width - 40, 240)
    qr_error = sum(ImageStat.Stat(ImageChops.difference(images[0].crop(box), images[1].crop(box))).mean) / 3
    assert qr_error < 2.0
    evidence = os.getenv("PDFA_EVIDENCE_DIR")
    if evidence:
        directory = Path(evidence)
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "diploma-final.pdf").write_bytes(final)
        (directory / "verapdf.xml").write_bytes(report)
        (directory / "diploma-estampado.pdf").write_bytes(stamped.read_bytes())
        images[1].save(directory / "diploma-final.png")
        (directory / "integridad.json").write_text(json.dumps({
            "sha256": digest, "visual_mean_difference": error,
            "qr_mean_difference": qr_error, "pdfa": "2b", "rsa_verified": True,
            "report_sha256": hashlib.sha256(report).hexdigest(),
            "public_key": keys["llave_publica"], "signature": keys["firma"],
            "rsa_input": "canonical base64 of final PDF bytes, ASCII",
            "institutional_template": bool(institutional_fixture),
            "dynamodb": "mock", "s3": "not called",
        }, indent=2))
