import logging, json, requests, os, base64
from cryptography.hazmat.primitives.serialization import load_pem_public_key
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from flask import Flask,jsonify,request, Response
from models.firma import firmar
from models.firma_electronica import ElectronicSign
import uuid

def postFirmaElectronica(data):
    """
        Carga 1 documento (orientado a pdf) a Nuxeo pasando body json con archivo en base64
        y parametros como firmantes y representantes para estampado de firma electrónica en documento pdf

        Parameters
        ----------
        body : json
            json con parametros como tipoDocumento, nombre, descripcion, metadatos, base64, firmantes y representantes
        nuxeo : Nuxeo
            cliente nuxeo

        Return
        ----------
        json : info documento
    """
    response_array=[]
    archivos_temporales = []

    try:
        for i in range(len(data)):

            nombreGenerado = uuid.uuid4()
            archivoAFirmar = f"./documents/{nombreGenerado}ToSign.pdf"
            archivoFirma = f"./documents/{nombreGenerado}signature.pdf"
            archivoFirmado = f"./documents/{nombreGenerado}Signed.pdf"
            archivos_temporales.extend([
                archivoAFirmar,
                archivoFirma,
                archivoFirmado
            ])

            if len(str(data[i]['file'])) < 1000:
                error_dict = {
                    'Status':'invalid pdf file',
                    'Code':'400'
                }
                return Response(json.dumps(error_dict), status=400, mimetype='application/json')
            IdDocumento = data[i]['IdTipoDocumento']
            res = requests.get(str(os.environ['DOCUMENTOS_CRUD_URL'])+'tipo_documento/'+str(IdDocumento))

            if res.status_code != 200:
                return Response(json.dumps({'Status':'404','Error': str("the id "+str(data[i]['IdTipoDocumento'])+" does not exist in documents_crud")}), status=404, mimetype='application/json')
            #Verificar que el base64 sea un pdf
            if not ElectronicSign.verificaEsPdf(data[i]['file']):
                error_dict = {
                    'Status':'El archivo no es un pdf',
                    'Code':'400'
                }
                return Response(json.dumps(error_dict), status=400, mimetype='application/json')
            #Fin verificar que el base 64 sea un pdf
            res_json = json.loads(res.content.decode('utf8').replace("'", '"'))
            blob = base64.b64decode(data[i]['file'])
            with open(os.path.expanduser(archivoAFirmar), 'wb') as fout:
                fout.write(blob)
            jsonFirmantes = {
                    "firmantes": data[i]["firmantes"],
                    "representantes": data[i]["representantes"],
            }
            all_metadata = str({** data[i]['metadatos']}).replace("{'", '{\\"').replace("': '", '\\":\\"').replace("': ", '\\":').replace(", '", ',\\"').replace("',", '",').replace('",' , '\\",').replace("'}", '\\"}').replace('\\"', '\"')
            DicPostDoc = {
                'Metadatos': all_metadata,
                'Nombre': data[i]['nombre'],
                "Descripcion": data[i]['descripcion'],
                'TipoDocumento':  res_json,
                'Activo': True
            }
            resPost = requests.post(str(os.environ['DOCUMENTOS_CRUD_URL'])+'documento', json=DicPostDoc).content
            responsePostDoc = json.loads(resPost.decode('utf8').replace("'", '"'))
            electronicSign = ElectronicSign()
            objFirmaElectronica = {
                "Activo": True,
                "CodigoAutenticidad": '',
                "FirmaEncriptada": '',
                "Firmantes": json.dumps(jsonFirmantes),
                "Llaves": json.dumps({}),
                "DocumentoId": {"Id": responsePostDoc["Id"]},
            }

            reqPostFirma = requests.post(str(os.environ['DOCUMENTOS_CRUD_URL'])+'firma_electronica', json=objFirmaElectronica).content
            responsePostFirma = json.loads(reqPostFirma.decode('utf8').replace("'", '"'))
            datos = {
                "firma": responsePostFirma["Id"],
                "firmantes": data[i]["firmantes"],
                "representantes": data[i]["representantes"],
                "tipo_documento": res_json["Nombre"],
            }
            electronicSign.estamparFirmaElectronica(datos, archivoAFirmar, archivoFirma, archivoFirmado)
            jsonStringFirmantes = {
                "firmantes": json.dumps(data[i]["firmantes"]),
                "representantes": json.dumps(data[i]["representantes"])
            }
            firma_electronica = firmar(str(electronicSign.docFirmadoBase64(archivoFirmado)))
            #Inicio update firma
            objFirmaElectronica = {
                "Activo": True,
                "CodigoAutenticidad": firma_electronica["codigo_autenticidad"],
                "FirmaEncriptada": firma_electronica["llaves"]["firma"],
                "Firmantes": json.dumps(jsonFirmantes),
                "Llaves": json.dumps(firma_electronica["llaves"]),
                "DocumentoId": {"Id": responsePostDoc["Id"]},
            }
            reqFirma = requests.put(str(os.environ['DOCUMENTOS_CRUD_URL'])+ 'firma_electronica/' + responsePostFirma["Id"], json=objFirmaElectronica)
            if reqFirma.status_code != 200:
                return Response(json.dumps({'Status':'404','Error': str("the id "+str(responsePostFirma["Id"])+" does not exist in documents_crud")}), status=404, mimetype='application/json')
            #fin update firma

            #Inicio modificación metadatos de firma
            firma_electronica.pop("llaves")
            #Fin modificación
            all_metadata = str({** firma_electronica, ** data[i]['metadatos'],  ** jsonStringFirmantes}).replace("{'", '{\\"').replace("': '", '\\":\\"').replace("': ", '\\":').replace(", '", ',\\"').replace("',", '",').replace('",' , '\\",').replace("'}", '\\"}').replace('\\"', '\"').replace("[", "").replace("]", "").replace('"{', '{').replace('}"', '}').replace(": ", ":").replace(", ", ",").replace("[", "").replace("]", "").replace("},{", ",")
            docFirmadoBase64 = str(electronicSign.docFirmadoBase64(archivoFirmado))
            putUpdateJson = [{
                "IdTipoDocumento": data[i]['IdTipoDocumento'],
                "nombre": data[i]['nombre'],
                "metadatos": all_metadata,
                "descripcion": data[i]['descripcion'],
                "file": docFirmadoBase64,
                "idDocumento": responsePostDoc["Id"]
            }]
            reqPutFirma = requests.put(str(os.environ['GESTOR_DOCUMENTAL_URL'])+'document/putUpdate', json=putUpdateJson).content
            responsePutUpdate = json.loads(reqPutFirma.decode('utf8').replace("'", '"'))
            response_array.append(responsePutUpdate)
        responsePutUpdate = response_array if len(response_array) > 1 else responsePutUpdate
        responsePutUpdate['file'] = docFirmadoBase64
        return Response(json.dumps(responsePutUpdate), status=200, mimetype='application/json')
    except Exception as e:
        logging.error("type error: " + str(e))

        if str(e) == "'IdTipoDocumento'":
            error_dict = {'Status':'the field IdTipoDocumento is required','Code':'400'}
            return Response(json.dumps(error_dict), status=400, mimetype='application/json')
        elif str(e) == "'nombre'":
            error_dict = {'Status':'the field nombre is required','Code':'400'}
            return Response(json.dumps(error_dict), status=400, mimetype='application/json')
        elif str(e) == "'file'":
            error_dict = {'Status':'the field file is required','Code':'400'}
            return Response(json.dumps(error_dict), status=400, mimetype='application/json')
        elif str(e) == "'metadatos'":
            error_dict = {'Status':'the field metadatos is required','Code':'400'}
            return Response(json.dumps(error_dict), status=400, mimetype='application/json')
        elif str(e) == "'descripcion'":
            error_dict = {'Status':'the field descripcion is required','Code':'400'}
            return Response(json.dumps(error_dict), status=400, mimetype='application/json')
        elif str(e) == "'representantes'":
            error_dict = {'Status':'the field representantes is required','Code':'400'}
            return Response(json.dumps(error_dict), status=400, mimetype='application/json')
        elif str(e) == "'firmantes'":
            error_dict = {'Status':'the field firmantes is required','Code':'400'}
            return Response(json.dumps(error_dict), status=400, mimetype='application/json')
        elif '400' in str(e):
            DicStatus = {'Status':'invalid request body', 'Code':'400'}
            return Response(json.dumps(DicStatus), status=400, mimetype='application/json')
        return Response(json.dumps({'Status':'500','Error':str(e)}), status=500, mimetype='application/json')
    finally:
        for f in archivos_temporales:
            try:
                if os.path.exists(f):
                    os.remove(f)
            except Exception:
                pass

def postVerify(data):
    """
        Verificar firma electrónica de documentos (pdf) cargados y firmados digitalmente,

        Parameters
        ----------
        body : json
            json con hash de firma electrónica
        nuxeo : Nuxeo
            cliente nuxeo

        Return
        ----------
        json : info documento si existe firma electrónica
    """
    response_array = []
    try:
        for i in range(len(data)):
            if str(data[i]["firma"]) == "":
                error_dict = {'Status': "Field firma is required", 'Code': '400'}
                return Response(json.dumps(error_dict), status=400, mimetype='application/json')
            resFirma = requests.get(str(os.environ['DOCUMENTOS_CRUD_URL'])+'firma_electronica/'+str(data[i]["firma"]))
            if resFirma.status_code != 200:
                return Response(resFirma, resFirma.status_code, mimetype='application/json')
            responseGetFirma = json.loads(resFirma.content.decode('utf8').replace("'", '"'))
            if responseGetFirma["DocumentoId"]["Enlace"]=="":
                error_dict = {'Message': "document not signed", 'code': '404'}
                return Response(json.dumps(error_dict), status=404, mimetype='application/json')
            elif responseGetFirma["DocumentoId"]["Enlace"]!="":
                responseNuxeo = requests.get(str(os.environ['GESTOR_DOCUMENTAL_URL'])+'document/'+str(responseGetFirma["DocumentoId"]["Enlace"])).content
                responseNuxeo = json.loads(responseNuxeo.decode('utf8').replace("'", '"'))
                #INICIO COMPARACIÓN
                llavesFirmaBD = json.loads(responseGetFirma["Llaves"])
                llavePublicaFirmaBD = llavesFirmaBD["llave_publica"]
                firmaBD = llavesFirmaBD["firma"]
                base64User = str (data[i]["fileUp"])
                urlFileUp = str (data[0]["urlFileUp"])
                fileEqual = True #Por defecto true ya que de ser así sólo se muestra un Doc
                public_key = load_pem_public_key(base64.b64decode(llavePublicaFirmaBD))
                if base64User != "":
                    try:
                        public_key.verify(
                            base64.urlsafe_b64decode(firmaBD),
                            base64User.encode('utf-8'),
                            padding.PSS(
                                mgf=padding.MGF1(hashes.SHA256()),
                                salt_length=padding.PSS.MAX_LENGTH
                            ),
                            hashes.SHA256()
                        )
                        fileEqual = True
                    except Exception as e:
                        fileEqual = False
                #FIN COMPARACIÓN
                responseNuxeo['fileEqual'] = fileEqual
                responseNuxeo['urlFileUp'] = urlFileUp
                response_array.append(responseNuxeo)
            else:
                error_dict = {'Message': "electronic signatures do not match", 'code': '404'}
                return Response(json.dumps(error_dict), status=404, mimetype='application/json')
        return Response(json.dumps({'Status':'200', 'res':response_array}), status=200, mimetype='application/json')
    except Exception as e:
            if str(e) == "'firma'":
                error_dict = {'Status':'the field firma is required','Code':'400'}
                return Response(json.dumps(error_dict), status=400, mimetype='application/json')
            elif '400' in str(e):
                DicStatus = {'Status':'invalid request body', 'Code':'400'}
                return Response(json.dumps(DicStatus), status=400, mimetype='application/json')
            return Response(json.dumps({'Status':'500','Error':str(e)}), status=500, mimetype='application/json')

def FirmaMultiple(data):
    """
        Estampa información de firmantes y la fecha en la que se estampa

        Parameters
        ----------
        body : json
            json con parametros como tipoDocumento, nombre, descripcion, metadatos, base64, firmantes y representantes
        nuxeo : Nuxeo
            cliente nuxeo

        Return
        ----------
        json : info documento
    """
    response_array=[]
    archivos_temporales = []

    try:
        for i in range(len(data)):

            nombreGenerado = uuid.uuid4()
            archivoAFirmar = f"./documents/{nombreGenerado}ToSign.pdf"
            archivoFirma = f"./documents/{nombreGenerado}signature.pdf"
            archivoFirmado = f"./documents/{nombreGenerado}Signed.pdf"
            archivos_temporales.extend([
                archivoAFirmar,
                archivoFirma,
                archivoFirmado
            ])

            if len(str(data[i]['file'])) < 1000:
                error_dict = {
                    'Status':'invalid pdf file',
                    'Code':'400'
                }
                return Response(json.dumps(error_dict), status=400, mimetype='application/json')
            IdDocumento = data[i]['IdTipoDocumento']
            res = requests.get(str(os.environ['DOCUMENTOS_CRUD_URL'])+'tipo_documento/'+str(IdDocumento))

            if res.status_code != 200:
                return Response(json.dumps({'Status':'404','Error': str("the id "+str(data[i]['IdTipoDocumento'])+" does not exist in documents_crud")}), status=404, mimetype='application/json')
            #Verificar que el base64 sea un pdf
            if not ElectronicSign.verificaEsPdf(data[i]['file']):
                error_dict = {
                    'Status':'El archivo no es un pdf',
                    'Code':'400'
                }
                return Response(json.dumps(error_dict), status=400, mimetype='application/json')
            #Fin verificar que el base 64 sea un pdf
            res_json = json.loads(res.content.decode('utf8').replace("'", '"'))
            blob = base64.b64decode(data[i]['file'])
            with open(os.path.expanduser(archivoAFirmar), 'wb') as fout:
                fout.write(blob)
            jsonFirmantes = {
                    "firmantes": data[i]["firmantes"],
                    "representantes": data[i]["representantes"],
            }
            all_metadata = str({** data[i]['metadatos']}).replace("{'", '{\\"').replace("': '", '\\":\\"').replace("': ", '\\":').replace(", '", ',\\"').replace("',", '",').replace('",' , '\\",').replace("'}", '\\"}').replace('\\"', '\"')
            DicPostDoc = {
                'Metadatos': all_metadata,
                'Nombre': data[i]['nombre'],
                "Descripcion": data[i]['descripcion'],
                'TipoDocumento':  res_json,
                'Activo': True
            }
            resPost = requests.post(str(os.environ['DOCUMENTOS_CRUD_URL'])+'documento', json=DicPostDoc).content
            responsePostDoc = json.loads(resPost.decode('utf8').replace("'", '"'))
            electronicSign = ElectronicSign()
            objFirmaElectronica = {
                "Activo": True,
                "CodigoAutenticidad": '',
                "FirmaEncriptada": '',
                "Firmantes": json.dumps(jsonFirmantes),
                "Llaves": json.dumps({}),
                "DocumentoId": {"Id": responsePostDoc["Id"]},
            }

            if data[i]["etapa_firma"] == 3:
                reqPostFirma = requests.post(str(os.environ['DOCUMENTOS_CRUD_URL'])+'firma_electronica', json=objFirmaElectronica).content
                responsePostFirma = json.loads(reqPostFirma.decode('utf8').replace("'", '"'))
                datos = {
                    "firma": responsePostFirma["Id"],
                    "firmantes": data[i]["firmantes"],
                    "representantes": data[i]["representantes"],
                    "tipo_documento": res_json["Nombre"],
                    "tipo_firma": data[i]["etapa_firma"]
                }
            else:
                datos = {
                    "firmantes": data[i]["firmantes"],
                    "representantes": data[i]["representantes"],
                    "tipo_documento": res_json["Nombre"],
                    "tipo_firma": data[i]["etapa_firma"]
                }
            electronicSign.estamparFirmaElectronica(datos, archivoAFirmar, archivoFirma, archivoFirmado)

            # ------- LÓGICA CONDICIONADA ----

            if data[i]["etapa_firma"] == 3:
                metaDatos = data[i]["metadatos"]
                jsonFirmantesCompletos = {
                    "firmantes": metaDatos['firmantes'],
                    "representantes": metaDatos["representantes"]
                }
                firma_electronica = firmar(str(electronicSign.docFirmadoBase64(archivoFirmado)))
                #Inicio update firma
                objFirmaElectronica = {
                    "Activo": True,
                    "CodigoAutenticidad": firma_electronica["codigo_autenticidad"],
                    "FirmaEncriptada": firma_electronica["llaves"]["firma"],
                    "Firmantes": json.dumps(jsonFirmantesCompletos),
                    "Llaves": json.dumps(firma_electronica["llaves"]),
                    "DocumentoId": {"Id": responsePostDoc["Id"]},
                }
                reqFirma = requests.put(str(os.environ['DOCUMENTOS_CRUD_URL'])+ 'firma_electronica/' + responsePostFirma["Id"], json=objFirmaElectronica)
                if reqFirma.status_code != 200:
                    return Response(json.dumps({'Status':'404','Error': str("the id "+str(responsePostFirma["Id"])+" does not exist in documents_crud")}), status=404, mimetype='application/json')
                #fin update firma

                #Inicio modificación metadatos de firma
                firma_electronica.pop("llaves")
                #Fin modificación
                #Modificación de metadatos
                metaDatos["firmantes"] = json.dumps(metaDatos["firmantes"])
                metaDatos["representantes"] = json.dumps(metaDatos["representantes"])
                data[i]["metadatos"] = metaDatos
                #Fin Modificación de metadatos
                all_metadata = str({** firma_electronica, ** data[i]['metadatos']}).replace("{'", '{\\"').replace("': '", '\\":\\"').replace("': ", '\\":').replace(", '", ',\\"').replace("',", '",').replace('",' , '\\",').replace("'}", '\\"}').replace('\\"', '\"').replace("[", "").replace("]", "").replace('"{', '{').replace('}"', '}').replace(": ", ":").replace(", ", ",").replace("[", "").replace("]", "").replace("},{", ",")

            putUpdateJson = [{
                "IdTipoDocumento": data[i]['IdTipoDocumento'],
                "nombre": data[i]['nombre'],
                "metadatos": all_metadata,
                "descripcion": data[i]['descripcion'],
                "file": str(electronicSign.docFirmadoBase64(archivoFirmado)),
                "idDocumento": responsePostDoc["Id"]
            }]
            reqPutFirma = requests.put(str(os.environ['GESTOR_DOCUMENTAL_URL'])+'document/putUpdate', json=putUpdateJson).content
            responsePutUpdate = json.loads(reqPutFirma.decode('utf8').replace("'", '"'))
            response_array.append(responsePutUpdate)
        responsePutUpdate = response_array if len(response_array) > 1 else responsePutUpdate

        return Response(json.dumps(responsePutUpdate), status=200, mimetype='application/json')
    except Exception as e:
        logging.error("type error: " + str(e))

        if str(e) == "'IdTipoDocumento'":
            error_dict = {'Status':'the field IdTipoDocumento is required','Code':'400'}
            return Response(json.dumps(error_dict), status=400, mimetype='application/json')
        elif str(e) == "'nombre'":
            error_dict = {'Status':'the field nombre is required','Code':'400'}
            return Response(json.dumps(error_dict), status=400, mimetype='application/json')
        elif str(e) == "'file'":
            error_dict = {'Status':'the field file is required','Code':'400'}
            return Response(json.dumps(error_dict), status=400, mimetype='application/json')
        elif str(e) == "'metadatos'":
            error_dict = {'Status':'the field metadatos is required','Code':'400'}
            return Response(json.dumps(error_dict), status=400, mimetype='application/json')
        elif str(e) == "'descripcion'":
            error_dict = {'Status':'the field descripcion is required','Code':'400'}
            return Response(json.dumps(error_dict), status=400, mimetype='application/json')
        elif str(e) == "'representantes'":
            error_dict = {'Status':'the field representantes is required','Code':'400'}
            return Response(json.dumps(error_dict), status=400, mimetype='application/json')
        elif str(e) == "'firmantes'":
            error_dict = {'Status':'the field firmantes is required','Code':'400'}
            return Response(json.dumps(error_dict), status=400, mimetype='application/json')
        elif '400' in str(e):
            DicStatus = {'Status':'invalid request body', 'Code':'400'}
            return Response(json.dumps(DicStatus), status=400, mimetype='application/json')
        return Response(json.dumps({'Status':'500','Error':str(e)}), status=500, mimetype='application/json')
    finally:
        for f in archivos_temporales:
            try:
                if os.path.exists(f):
                    os.remove(f)
            except Exception:
                pass

