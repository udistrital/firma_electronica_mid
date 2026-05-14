

import os
import base64
import logging
from io import BytesIO

from cryptography.fernet import Fernet

# Imports ElectronicSign
from pdfminer.layout import LAParams, LTTextBox, LTTextLine, LTFigure, LTImage, LTCurve, LTChar
from pdfminer.pdfpage import PDFPage
from pdfminer.pdfinterp import PDFResourceManager
from pdfminer.pdfinterp import PDFPageInterpreter
from pdfminer.converter import PDFPageAggregator
from reportlab.pdfgen import canvas
from pypdf import PdfWriter, PdfReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from pdfminer.high_level import extract_pages
from reportlab.lib.utils import ImageReader
from textwrap import wrap
import time
from fillpdf import fillpdfs
from conf.conf import get_verificacion_externa_url, get_verificacion_url

os.environ['TZ'] = 'America/Bogota'
time.tzset()


class ElectronicSign:
    """
        Permite el manejo de pdf para estampa la firma electronica en un documento,
        ademas de calcular el espacio necesario para estampar dicha firma con su información.
        También permite la encriptación desincriptación de una firma
    """
    def __init__(self):
        self.YFOOTER = 80
        self.YHEEADER = 100

    def build_qr_image(self, qr_url):
        if not qr_url:
            return None

        try:
            import qrcode
        except ImportError:
            logging.warning("qrcode dependency not installed; QR image skipped")
            return None

        qr = qrcode.QRCode(
            version=None,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=6,
            border=2,
        )
        qr.add_data(qr_url)
        qr.make(fit=True)
        image = qr.make_image(fill_color="black", back_color="white").get_image().convert("RGB")
        image_buffer = BytesIO()
        image.save(image_buffer, format="PNG")
        image_buffer.seek(0)
        return ImageReader(image_buffer)

    def lastPageItems(self, pdfIn):
        """
            Analiza el pdf para determinar las posiciones de sus elementos
            Parameters
            ----------
            pdfIn : _io.BufferedReader
                pdf abierto en buffer como lectura

            Return
            ----------
            list : lista de posiciones en y de cada uno de los elementos de un pdf
        """
        rsrcmgr = PDFResourceManager()
        laparams = LAParams()
        device = PDFPageAggregator(rsrcmgr, laparams=laparams)
        interpreter = PDFPageInterpreter(rsrcmgr, device)
        #pages = PDFPage.get_pages(pdfIn)
        pages = extract_pages(pdfIn)
        pages = list(pages)
        page = pages[len(pages)-1]

        yText = []

        for lobj in page:
            if isinstance(lobj, LTTextBox):
                for text_line in lobj:
                    for character in text_line:
                        if isinstance(character,LTChar):    
                            y= lobj.bbox[1]
                            yText.append(y)

        return yText

    def signPosition(self, pdfIn):
        yText = self.lastPageItems(pdfIn)
        yText.reverse()

        for i in range(0,len(yText)):
            if yText[i] > 80:
                y = yText[i]
                break

        return int(y)

    def descrypt(self, codigo):
        """
            Desencripta un texto
            Parameters
            ----------
            codigo : bytes
                codigo en formato bytes encriptado
            Return
            ----------
            bytes : codigo en formato bytes desencriptado
        """
        return self.fernet.decrypt(codigo)

    def hashCode(self, firma):
        """
            Desencripta un texto
            Parameters
            ----------
            codigo : String
                codigo desencriptado
            Return
            ----------
            bytes : codigo en formato bytes encriptado
        """
        return self.fernet.encrypt(firma.encode())

    #--------- INICIO NUEVA ESTAMPA -------
    def signature_alter(self, pdfIn, yPosition, datos, etapa, archivoFirma):
        """
            Crea el estampado dependiendo de la etapa en la que se esté firmando.
            Parameters
            ----------
            pdfIn : _io.BufferedReader
                pdf abierto en buffer como lectura
            yPosition : int
                posición del ultimo elemeento del pdf
            datos : dict
                diccionario con datos a estampar {tipo_documento, firmantes, representantes, firma}

            Return
            ----------
            String : id y firma encriptados
            Boolean : True si se puede estampar en la ultima pagina, False si se debe crear una nueva pagina
        """
        link_verificacion = "Verificación interna: " + get_verificacion_url()
        link_verificacion_externa = "Verificación para externos: " + get_verificacion_externa_url()

        x = 80
        page = PdfReader(pdfIn).pages[0]
        page_width = int(page.mediabox[2])
        page_height = int(page.mediabox[3])
        y = yPosition
        line_height = 8
        section_gap = 4
        row_gap = 2
        label_width = 120
        left_value_width = 46
        verification_wrap_width = 96
        qr_url = datos.get("qr_url")
        qr_image = self.build_qr_image(qr_url)
        qr_size = 78
        qr_col_x = page_width - qr_size - 55

        wraped_firmantes = []
        for firmante in datos["firmantes"]:
            cargo = ""
            if firmante["cargo"] != "":
                cargo = firmante["cargo"] + ": "
            text = cargo + firmante["nombre"] + ". " + firmante["tipoId"] + " " + firmante["identificacion"]
            wraped_firmantes.append("\n".join(wrap(text, left_value_width)))

        wraped_representantes = []
        for representante in datos["representantes"]:
            cargo = ""
            if representante["cargo"] != "":
                cargo = representante["cargo"] + ": "
            text = cargo + representante["nombre"] + ". " + representante["tipoId"] + " " + representante["identificacion"]
            wraped_representantes.append("\n".join(wrap(text, left_value_width)))

        firma = datos.get("firma", "")
        wrapped_tipo_documento = "\n".join(wrap(datos.get("tipo_documento", ""), left_value_width))
        wrapped_codigo = "\n".join(wrap(firma, left_value_width))
        wrapped_link_ver = "\n".join(wrap(link_verificacion, verification_wrap_width))
        wrapped_link_ver_externo = "\n".join(wrap(link_verificacion_externa, verification_wrap_width))

        rows = []
        if len(datos["firmantes"]) > 1:
            rows.append(("Firmantes:", "\n".join(wraped_firmantes)))
        elif len(datos["firmantes"]) == 1:
            rows.append(("Firmante:", wraped_firmantes[0]))

        if len(datos["representantes"]) > 1:
            rows.append(("Representantes:", "\n".join(wraped_representantes)))
        elif len(datos["representantes"]) == 1:
            rows.append(("Representante:", wraped_representantes[0]))

        fechaHoraActual = time.strftime("%d/%m/%y %H:%M:%S")
        rows.append(("Fecha y hora:", fechaHoraActual))

        if etapa == 3:
            rows.append(("Tipo de documento:", wrapped_tipo_documento))
            rows.append(("Código de verificación:", wrapped_codigo))

        rows_height = 0
        for label, value in rows:
            label_lines = label.count("\n") + 1
            value_lines = value.count("\n") + 1 if value else 1
            rows_height += max(label_lines, value_lines) * line_height + row_gap

        verification_lines = [
            "Para verificar la autenticidad de la presente firma electrónica",
            "consulte el código suministrado en el sitio web indicado:",
            *wrapped_link_ver.split("\n"),
            *wrapped_link_ver_externo.split("\n"),
        ]
        if qr_url:
            verification_lines.append("Acceso seguro al documento original: escanee el QR.")

        verification_height = len(verification_lines) * line_height
        lower_block_height = verification_height

        title_height = 10 if etapa == 1 else 0
        signPageSize = title_height + section_gap + rows_height + section_gap + lower_block_height + 8
        if qr_image:
            signPageSize = max(signPageSize, qr_size + 24)

        if(yPosition - self.YFOOTER < signPageSize):
            y = page_height - self.YHEEADER

        c = canvas.Canvas(archivoFirma)
        pdfmetrics.registerFont(TTFont('Vera', 'Vera.ttf'))
        pdfmetrics.registerFont(TTFont('VeraBd', 'VeraBd.ttf'))

        cursor_y = y
        if etapa == 1:
            c.setFont('VeraBd', 10)
            cursor_y = cursor_y - 10
            c.drawString(x + 20, cursor_y, "Firmado Digitalmente")

        cursor_y = cursor_y - 12

        for label, value in rows:
            label_lines = label.split("\n")
            value_lines = value.split("\n") if value else [""]
            row_lines = max(len(label_lines), len(value_lines))
            row_top_y = cursor_y

            label_text = c.beginText()
            label_text.setFont('VeraBd', 8)
            label_text.setLeading(line_height)
            label_text.setTextOrigin(x, row_top_y)
            for line in label_lines:
                label_text.textLine(line)
            c.drawText(label_text)

            value_text = c.beginText()
            value_text.setFont('Vera', 8)
            value_text.setLeading(line_height)
            value_text.setTextOrigin(x + label_width, row_top_y)
            for line in value_lines:
                value_text.textLine(line)
            c.drawText(value_text)

            cursor_y = row_top_y - (row_lines * line_height) - row_gap

        cursor_y = cursor_y - section_gap
        verification_top_y = cursor_y

        verification_title = c.beginText()
        verification_title.setFont('VeraBd', 8)
        verification_title.setLeading(line_height)
        verification_title.setTextOrigin(x, verification_top_y)
        verification_title.textLine("Para verificar la autenticidad de la presente firma electrónica")
        verification_title.textLine("consulte el código suministrado en el sitio web indicado:")
        c.drawText(verification_title)

        verification_body_y = verification_top_y - (2 * line_height)
        verification_body = c.beginText()
        verification_body.setFont('Vera', 8)
        verification_body.setLeading(line_height)
        verification_body.setTextOrigin(x, verification_body_y)
        for line in wrapped_link_ver.split("\n"):
            verification_body.textLine(line)
        for line in wrapped_link_ver_externo.split("\n"):
            verification_body.textLine(line)
        if qr_url:
            verification_body.textLine("Acceso seguro al documento original: escanee el QR.")
        c.drawText(verification_body)

        if qr_image:
            qr_draw_y = max(self.YFOOTER + 6, verification_top_y - qr_size + (3 * line_height))
            c.drawImage(
                qr_image,
                qr_col_x,
                qr_draw_y,
                width=qr_size,
                height=qr_size,
                preserveAspectRatio=True,
                mask="auto"
            )

        c.showPage()
        c.save()

        espacio = yPosition - self.YFOOTER > signPageSize
        return espacio

    #--------- FIN NUEVA ESTAMPA --------

    def signature(self, pdfIn, yPosition, datos, archivoFirma):
        """
            Crea el estampado de la firma electronica
            Parameters
            ----------
            pdfIn : _io.BufferedReader
                pdf abierto en buffer como lectura
            yPosition : int
                posición del ultimo elemeento del pdf
            datos : dict
                diccionario con datos a estampar {tipo_documento, firmantes, representantes, firma}

            Return
            ----------
            String : id y firma encriptados
            Boolean : True si se puede estampar en la ultima pagina, False si se debe crear una nueva pagina
        """
        link_verificacion = "Verificación interna: " + get_verificacion_url()
        link_verificacion_externa = "Verificación para externos: " + get_verificacion_externa_url()

        x = 80
        y = yPosition
        signPageSize = 3 + len(datos["firmantes"]) + len(datos["representantes"]) + 2.5 + 6 #Espacios

        wraped_firmantes = []
        for firmante in datos["firmantes"]:
            cargo = ""
            if firmante["cargo"] != "":
                cargo = firmante["cargo"] + ": "
            text = cargo + firmante["nombre"] + ". " + firmante["tipoId"] + " " + firmante["identificacion"]
            text = "\n".join(wrap(text, 60))
            signPageSize += text.count("\n")
            wraped_firmantes.append(text)

        wraped_representantes = []
        for representante in datos["representantes"]:
            cargo = ""
            if representante["cargo"] != "":
                cargo = representante["cargo"] + ": "
            text = cargo + representante["nombre"] + ". " + representante["tipoId"] + " " + representante["identificacion"]
            text = "\n".join(wrap(text, 60))
            text.count("\n")
            signPageSize += text.count("\n")
            wraped_representantes.append(text)

        firma = datos["firma"]

        wraped_firma = "\n".join(wrap(firma, 60))

        signPageSize += wraped_firma.count("\n")

        signPageSize *= 10



        if(yPosition - self.YFOOTER < signPageSize):
            y = int(PdfReader(pdfIn).pages[0].mediabox[3] - self.YHEEADER)


        c = canvas.Canvas(archivoFirma)
        # Create the signPdf from an image
        # c = canvas.Canvas('signPdf.pdf')

        # Draw the image at x, y. I positioned the x,y to be where i like here
        # c.drawImage('test.png', 15, 720)
        pdfmetrics.registerFont(TTFont('Vera', 'Vera.ttf'))
        pdfmetrics.registerFont(TTFont('VeraBd', 'VeraBd.ttf'))

        c.setFont('VeraBd', 10)
        y = y - 10
        c.drawString(x + 20, y,"Firmado Digitalmente")

        c.setFont('Vera', 8)
        t = c.beginText()

        if len(datos["firmantes"]) > 1:
            t.setFont('VeraBd', 8)
            y = y - 15
            t.setTextOrigin(x, y)
            t.textLine("Firmantes:")
        elif len(datos["firmantes"]) == 1:
            t.setFont('VeraBd', 8)
            y = y - 15
            t.setTextOrigin(x, y)
            t.textLine("Firmante:")

        count = 1
        t.setFont('Vera', 8)
        for firmante in wraped_firmantes:
            if(count > 1):
                y = y - 10
            t.setTextOrigin(x+140,y)
            t.textLines(firmante)
            y = y-firmante.count("\n")*10
            count += 1

        if len(wraped_firmantes):
            y = y - 5

        if len(datos["representantes"]) > 1:
            t.setFont('VeraBd', 8)
            y = y - 10
            t.setTextOrigin(x, y)
            t.textLine("Representantes:")
        elif len(datos["representantes"]) == 1:
            t.setFont('VeraBd', 8)
            y = y - 10
            t.setTextOrigin(x, y)
            t.textLine("Representante:")

        count = 1
        t.setFont('Vera', 8)
        for representante in wraped_representantes:
            if(count > 1):
                y = y - 10
            t.setTextOrigin(x+140,y)
            t.textLines(representante)
            y = y-representante.count("\n")*10
            count += 1

        if len(wraped_representantes):
            y = y - 5

        t.setFont('VeraBd', 8)
        y = y - 10
        t.setTextOrigin(x, y)
        t.textLine("Tipo de documento:")
        t.setFont('Vera', 8)
        t.setTextOrigin(x+140, y)
        t.textLine(datos["tipo_documento"])

        y = y - 5

        t.setFont('VeraBd', 8)
        y = y - 10
        t.setTextOrigin(x, y)
        t.textLine("Código de verificación:")
        t.setTextOrigin(x + 140, y)
        t.setFont('Vera', 8)
        t.textLine(firma)

        y = y - 5

        t.setFont('VeraBd', 8)
        y = y - 10 - wraped_firma.count("\n")*10
        t.setTextOrigin(x, y)
        t.textLine("Fecha y hora:")
        t.setFont('Vera', 8)
        #fechaHoraActual = time.strftime("%x") + " " + time.strftime("%X")
        fechaHoraActual = time.strftime("%d/%m/%y %H:%M:%S")
        t.setTextOrigin(x+140, y)
        t.textLine(fechaHoraActual)

        #Enlace verificacion
        y = y - 10
        t.setFont('VeraBd', 8)
        y = y - 10
        t.setTextOrigin(x, y)
        t.textLine("Para verificar la autenticidad de la presente firma electrónica")
        t.textLine("consulte el código suministrado en el sitio web indicado:")
        t.textLine(" ")
        y= y - 20
        link_ver = link_verificacion
        link_ver_externo = link_verificacion_externa
        t.setFont("Vera", 8)
        t.setTextOrigin(x, y)
        t.textLine(link_ver)
        t.textLine(link_ver_externo)
        #Fin enlace

        c.drawText(t)
        c.showPage()
        c.save()

        espacio = yPosition - self.YFOOTER > signPageSize
        return espacio

    def estamparUltimaPagina(self, pdfIn, archivoFirma, archivoFirmado):

        """
            Estampa la firma en la ultima pagina del cocumento ya existente
            Parameters
            ----------
            pdfIn : _io.BufferedReader
                pdf abierto en buffer como lectura
        """

        signPdf = PdfReader(open(archivoFirma, "rb"))
        documentPdf = PdfReader(pdfIn)

        # Get our files ready
        output_file = PdfWriter()

        # Number of pages in input document
        page_count = len(documentPdf.pages)

        for page_number in range(page_count-1):
            input_page = documentPdf.pages[page_number]
            output_file.add_page(input_page)

        input_page = documentPdf.pages[page_count-1]
        input_page.merge_page(signPdf.pages[0])
        output_file.add_page(input_page)
        with open(archivoFirmado, "wb") as outputStream:
            output_file.write(outputStream)

    def estamparNuevaPagina(self, pdfIn, archivoFirma, archivoFirmado):
        """
            Crea una nueva pagina y la estampa para ser unida con el pdf

            Parameters
            ----------
            pdfIn : _io.BufferedReader
                pdf abierto en buffer como lectura
        """
        signPdf = PdfReader(open(archivoFirma, "rb"))
        documentPdf = PdfReader(pdfIn)

        # Get our files ready
        output_file = PdfWriter()

        # Number of pages in input document
        page_count = len(documentPdf.pages)

        for page_number in range(page_count):
            input_page = documentPdf.pages[page_number]
            output_file.add_page(input_page)

        output_file.add_blank_page()
        output_file.pages[len(output_file.pages)-1].merge_page(signPdf.pages[0])

        with open(archivoFirmado, "wb") as outputStream:
            output_file.write(outputStream)


    def estamparFirmaElectronica(self, datos, archivoAFirmar, archivoFirma, archivoFirmado):
        """
            Metodo principal para el proceso de estampado

            Parameters
            ----------
            datos : dict
                diccionario con datos a estampar {tipo_documento, firmantes, representantes, firma}

            Returns
            -------
            firmaEncriptada : String
                firma con id encriptadas en un solo texto
        """
        # Primero calcular posición
        with open(archivoAFirmar, "rb") as pdfIn:
            yPosition = self.signPosition(pdfIn) - 10
        # Generar firma visual
        with open(archivoAFirmar, "rb") as pdfIn:
            if datos.get('tipo_firma'):
                if datos['tipo_firma'] != 1:
                    yPosition = yPosition + 15
                etapa = datos['tipo_firma']
                suficienteEspacio = self.signature_alter(pdfIn, yPosition, datos, etapa, archivoFirma)
            else:
                suficienteEspacio = self.signature(pdfIn, yPosition, datos, archivoFirma)
        # Estampar en documento
        with open(archivoAFirmar, "rb") as pdfIn:
            if suficienteEspacio:
                self.estamparUltimaPagina(pdfIn, archivoFirma, archivoFirmado)
            else:
                self.estamparNuevaPagina(pdfIn, archivoFirma, archivoFirmado)
        return

    def firmaCompleta(self, firma, id):
        """
        Método que retorna la firma encriptada incluyendo el ID del documento

        Parameters
        ----------
        firma : string
            Firma encriptada
        ----------
        id : int
            ID del documento en la tabla documento del api documentos_crud

        Returns
        -------
        firmaCompleta : String
            firma con id encriptadas en un solo texto
        """
        firmaID = str(id) + "/////" + firma
        return self.hashCode(firmaID).decode()
    
    def docFirmadoBase64(self, archivoFirmado):
        '''
            Convierte el documento firmado a base 64 para que pueda ser recibido en gestor documental por putUpdate
        '''
        with open(archivoFirmado,"rb") as pdf_file:
            # Leer el contenido del archivo
            pdf_bytes = pdf_file.read()
            # Convertir los bytes a base64
            base64_bytes = base64.b64encode(pdf_bytes)
            # Convertir los bytes base64 a una cadena
            base64_string = base64_bytes.decode('utf-8')
        return base64_string

    def verificaEsPdf(base64_string):
        '''
            Verifica que el base 64 ingresado corresponda a un pdf
        '''
        try:
            # Decodificar el string Base64
            decoded_bytes = base64.b64decode(base64_string)

            # Verificar el encabezado y pie de un archivo PDF
            if decoded_bytes[:5] == b'%PDF-' and b'%%EOF' in decoded_bytes:
                return True
            else:
                return False
        except Exception as e:
            # Si hay un error en la decodificación, no es un Base64 válido para un PDF
            return False
