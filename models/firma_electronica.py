

import os
import base64

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
from textwrap import wrap
import time
from fillpdf import fillpdfs

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
        #key = os.environ['ENCRYPTION_KEY']
        #self.fernet = Fernet(key)

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

    def signature(self, pdfIn, yPosition, datos):
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
        link_verificacion = ""
        if os.environ['ENV'] == "dev":
            link_verificacion = "https://pruebasverificacion.portaloas.udistrital.edu.co"
        else:
            link_verificacion = "https://verificacion.portaloas.udistrital.edu.co"

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


        c = canvas.Canvas('documents/signature.pdf')
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
        fechaHoraActual = time.strftime("%x") + " " + time.strftime("%X")
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
        t.setFont("Vera", 8)
        t.setTextOrigin(x, y)
        t.textLine(link_ver)
        #Fin enlace

        c.drawText(t)
        c.showPage()
        c.save()

        espacio = yPosition - self.YFOOTER > signPageSize
        return espacio

    def estamparUltimaPagina(self, pdfIn):

        """
            Estampa la firma en la ultima pagina del cocumento ya existente
            Parameters
            ----------
            pdfIn : _io.BufferedReader
                pdf abierto en buffer como lectura
        """

        signPdf = PdfReader(open("documents/signature.pdf", "rb"))
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
        with open("documents/documentSigned.pdf", "wb") as outputStream:
            output_file.write(outputStream)

    def estamparNuevaPagina(self, pdfIn):
        """
            Crea una nueva pagina y la estampa para ser unida con el pdf

            Parameters
            ----------
            pdfIn : _io.BufferedReader
                pdf abierto en buffer como lectura
        """
        signPdf = PdfReader(open("documents/signature.pdf", "rb"))
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

        with open("documents/documentSigned.pdf", "wb") as outputStream:
            output_file.write(outputStream)


    def estamparFirmaElectronica(self, datos):
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
        pdfIn = open("documents/documentToSign.pdf","rb")
        yPosition = self.signPosition(pdfIn) - 10
        suficienteEspacio = self.signature(pdfIn, yPosition, datos)

        if suficienteEspacio:
            self.estamparUltimaPagina(pdfIn)
        else:
            self.estamparNuevaPagina(pdfIn)
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
    
    def docFirmadoBase64(self):
        '''
            Convierte el documento firmado a base 64 para que pueda ser recibido en gestor documental por putUpdate
        '''
        with open("documents/documentSigned.pdf","rb") as pdf_file:
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