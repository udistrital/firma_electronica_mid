import pytest
from pypdf import PdfReader
from reportlab.pdfgen import canvas

from models.firma_electronica import ElectronicSign


def _crear_pdf(ruta, tamano):
    c = canvas.Canvas(str(ruta), pagesize=tamano)
    c.drawString(80, tamano[1] - 100, "Contenido del documento")
    c.save()


@pytest.mark.parametrize(
    "tamano",
    [
        (612, 792),  # carta vertical
        (792, 612),  # carta horizontal
        (842, 595),  # A4 horizontal
    ]
)
def test_estampado_usa_tamano_de_la_pagina(tmp_path, tamano):
    """
        El lienzo del sello debe medir lo mismo que la pagina: si queda en A4 vertical,
        pypdf recorta el QR al estampar documentos horizontales
    """
    archivoAFirmar = tmp_path / "ToSign.pdf"
    archivoFirma = tmp_path / "signature.pdf"
    archivoFirmado = tmp_path / "Signed.pdf"
    _crear_pdf(archivoAFirmar, tamano)

    datos = {
        "firma": "cd175043-4586-4932-b48b-14ac3a01544e",
        "firmantes": [{"nombre": "Firmante de prueba", "cargo": "Jefe de Oficina"}],
        "representantes": [],
        "tipo_documento": "Documento de prueba",
        "tipo_firma": 3,
        "qr_url": "https://verificacion.udistrital.edu.co/?token=prueba",
    }
    ElectronicSign().estamparFirmaElectronica(datos, str(archivoAFirmar), str(archivoFirma), str(archivoFirmado))

    sello = PdfReader(str(archivoFirma)).pages[0]
    assert (int(sello.mediabox.width), int(sello.mediabox.height)) == tamano

    qr_x = tamano[0] - 78 - 55
    assert qr_x + 78 <= sello.mediabox.width

    firmado = PdfReader(str(archivoFirmado)).pages[-1]
    assert (int(firmado.mediabox.width), int(firmado.mediabox.height)) == tamano
