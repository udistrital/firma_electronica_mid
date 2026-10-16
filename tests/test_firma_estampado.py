from io import BytesIO

import pytest
from PIL import Image
from pdfminer.high_level import extract_pages
from pypdf import PdfReader
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from models.firma_electronica import ElectronicSign

CARTA = (612, 792)


def _crear_pdf(ruta, tamano):
    c = canvas.Canvas(str(ruta), pagesize=tamano)
    c.drawString(80, tamano[1] - 100, "Contenido del documento")
    c.save()


def _datos_firma():
    return {
        "firma": "cd175043-4586-4932-b48b-14ac3a01544e",
        "firmantes": [{"nombre": "Firmante de prueba", "cargo": "Jefe de Oficina"}],
        "representantes": [],
        "tipo_documento": "Documento de prueba",
        "tipo_firma": 3,
        "qr_url": "https://verificacion.udistrital.edu.co/?token=prueba",
    }


def _imagen():
    buffer = BytesIO()
    Image.new("RGB", (300, 150), (40, 90, 170)).save(buffer, "PNG")
    buffer.seek(0)
    return ImageReader(buffer)


def _parrafos(c, y_inicial, cantidad):
    for i in range(cantidad):
        c.drawString(80, y_inicial - i * 16, f"Parrafo {i + 1}")


def _solo_texto(c):
    _parrafos(c, 700, 5)


def _texto_e_imagen(c):
    _parrafos(c, 700, 5)
    c.drawImage(_imagen(), 80, 420, width=300, height=150)


def _texto_y_cuadro(c):
    _parrafos(c, 700, 5)
    for fila in range(4):
        for columna in range(3):
            c.rect(80 + columna * 150, 560 - fila * 30, 150, 30)


def _texto_con_marco_de_pagina(c):
    c.rect(30, 30, CARTA[0] - 60, CARTA[1] - 60)
    _parrafos(c, 700, 5)


def _texto_con_logo_en_pie(c):
    _parrafos(c, 700, 5)
    c.drawImage(_imagen(), 80, 20, width=100, height=50)


@pytest.mark.parametrize(
    "dibujar, y_ultimo_elemento",
    [
        (_solo_texto, 636),
        (_texto_e_imagen, 420),
        (_texto_y_cuadro, 470),
        (_texto_con_marco_de_pagina, 636),
        (_texto_con_logo_en_pie, 636),
    ],
    ids=["texto", "imagen", "cuadro", "marco_de_pagina", "logo_en_pie"]
)
def test_firma_se_ubica_bajo_el_ultimo_elemento(tmp_path, dibujar, y_ultimo_elemento):
    """
        La firma va debajo del ultimo elemento de la pagina, sea texto, imagen o cuadro.
        Los marcos de pagina y lo que esta en el pie de pagina no cuentan como contenido
    """
    archivoAFirmar = tmp_path / "ToSign.pdf"
    archivoFirma = tmp_path / "signature.pdf"
    archivoFirmado = tmp_path / "Signed.pdf"
    c = canvas.Canvas(str(archivoAFirmar), pagesize=CARTA)
    dibujar(c)
    c.save()

    electronicSign = ElectronicSign()
    with open(archivoAFirmar, "rb") as pdfIn:
        y_detectado = electronicSign.signPosition(pdfIn)
    # El texto se mide por la base de su linea, que queda unos puntos por debajo de donde se escribe
    assert y_ultimo_elemento - 5 <= y_detectado <= y_ultimo_elemento

    electronicSign.estamparFirmaElectronica(_datos_firma(), str(archivoAFirmar), str(archivoFirma), str(archivoFirmado))
    assert len(PdfReader(str(archivoFirmado)).pages) == 1

    # Todo el sello (texto y QR) queda debajo del ultimo elemento, con la separacion definida
    tope_sello = max(elemento.bbox[3] for elemento in next(extract_pages(str(archivoFirma))))
    assert tope_sello <= y_detectado - electronicSign.ESPACIO_FIRMA


def test_firma_en_pagina_nueva_cuando_no_cabe(tmp_path):
    archivoAFirmar = tmp_path / "ToSign.pdf"
    archivoFirma = tmp_path / "signature.pdf"
    archivoFirmado = tmp_path / "Signed.pdf"
    c = canvas.Canvas(str(archivoAFirmar), pagesize=CARTA)
    _parrafos(c, 700, 5)
    c.drawImage(_imagen(), 80, 110, width=300, height=150)
    c.save()

    ElectronicSign().estamparFirmaElectronica(_datos_firma(), str(archivoAFirmar), str(archivoFirma), str(archivoFirmado))

    firmado = PdfReader(str(archivoFirmado))
    assert len(firmado.pages) == 2
    assert "Firmante" not in firmado.pages[0].extract_text()
    assert "Firmante" in firmado.pages[1].extract_text()


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
