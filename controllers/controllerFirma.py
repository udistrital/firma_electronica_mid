import logging, json, requests, os, base64
from cryptography.hazmat.primitives.serialization import load_pem_public_key
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from flask import request, Response, redirect
from models.firma import firmar
from models.firma_electronica import ElectronicSign
from services.qr_security import build_qr_url, validate_qr_token
from conf.conf import get_documentos_crud_url, get_gestor_documental_url, get_qr_base_url
import uuid


def _trace(stage, extra=None):
    message = f"[trace] {stage}"
    if extra:
        message = f"{message} | {extra}"
    logging.info(message)

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
            res = requests.get(get_documentos_crud_url()+'tipo_documento/'+str(IdDocumento))

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
            resPost = requests.post(get_documentos_crud_url()+'documento', json=DicPostDoc).content
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

            reqPostFirma = requests.post(get_documentos_crud_url()+'firma_electronica', json=objFirmaElectronica).content
            responsePostFirma = json.loads(reqPostFirma.decode('utf8').replace("'", '"'))
            qr_url = build_qr_url(responsePostFirma["Id"], responsePostDoc["Id"])
            datos = {
                "firma": responsePostFirma["Id"],
                "firmantes": data[i]["firmantes"],
                "representantes": data[i]["representantes"],
                "tipo_documento": res_json["Nombre"],
                "tipo_firma": 3,
                "qr_url": qr_url,
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
            reqFirma = requests.put(get_documentos_crud_url()+ 'firma_electronica/' + responsePostFirma["Id"], json=objFirmaElectronica)
            if reqFirma.status_code != 200:
                return Response(json.dumps({'Status':'404','Error': str("the id "+str(responsePostFirma["Id"])+" does not exist in documents_crud")}), status=404, mimetype='application/json')
            #fin update firma

            #Inicio modificación metadatos de firma
            firma_electronica.pop("llaves")
            if qr_url:
                firma_electronica["qr_url_segura"] = qr_url
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
            reqPutFirma = requests.put(get_gestor_documental_url()+'document/putUpdate', json=putUpdateJson).content
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
        _trace("verify.start")
        for i in range(len(data)):
            _trace("verify.item.start", f"index={i}")
            if str(data[i]["firma"]) == "":
                _trace("verify.item.missing_firma", f"index={i}")
                error_dict = {'Status': "Field firma is required", 'Code': '400'}
                return Response(json.dumps(error_dict), status=400, mimetype='application/json')
            _trace("verify.documentos_crud.request", f"index={i}")
            resFirma = requests.get(get_documentos_crud_url()+'firma_electronica/'+str(data[i]["firma"]))
            _trace("verify.documentos_crud.response", f"index={i} status={resFirma.status_code}")
            if resFirma.status_code != 200:
                _trace("verify.documentos_crud.non_200", f"index={i}")
                return Response(resFirma, resFirma.status_code, mimetype='application/json')
            responseGetFirma = json.loads(resFirma.content.decode('utf8').replace("'", '"'))
            if responseGetFirma["DocumentoId"]["Enlace"]=="":
                _trace("verify.document_link.empty", f"index={i}")
                error_dict = {'Message': "document not signed", 'code': '404'}
                return Response(json.dumps(error_dict), status=404, mimetype='application/json')
            elif responseGetFirma["DocumentoId"]["Enlace"]!="":
                _trace("verify.gestor_documental.request", f"index={i}")
                responseNuxeo = requests.get(get_gestor_documental_url()+'document/'+str(responseGetFirma["DocumentoId"]["Enlace"])).content
                _trace("verify.gestor_documental.response", f"index={i}")
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
                    _trace("verify.signature.compare.start", f"index={i}")
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
                        _trace("verify.signature.compare.ok", f"index={i}")
                    except Exception as e:
                        fileEqual = False
                        _trace("verify.signature.compare.fail", f"index={i} type={type(e).__name__}")
                #FIN COMPARACIÓN
                responseNuxeo['fileEqual'] = fileEqual
                responseNuxeo['urlFileUp'] = urlFileUp
                response_array.append(responseNuxeo)
            else:
                _trace("verify.signature.mismatch", f"index={i}")
                error_dict = {'Message': "electronic signatures do not match", 'code': '404'}
                return Response(json.dumps(error_dict), status=404, mimetype='application/json')
        _trace("verify.end", f"items={len(response_array)}")
        return Response(json.dumps({'Status':'200', 'res':response_array}), status=200, mimetype='application/json')
    except Exception as e:
            _trace("verify.exception", f"type={type(e).__name__}")
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
            res = requests.get(get_documentos_crud_url()+'tipo_documento/'+str(IdDocumento))

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
            resPost = requests.post(get_documentos_crud_url()+'documento', json=DicPostDoc).content
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
                reqPostFirma = requests.post(get_documentos_crud_url()+'firma_electronica', json=objFirmaElectronica).content
                responsePostFirma = json.loads(reqPostFirma.decode('utf8').replace("'", '"'))
                qr_url = build_qr_url(responsePostFirma["Id"], responsePostDoc["Id"])
                datos = {
                    "firma": responsePostFirma["Id"],
                    "firmantes": data[i]["firmantes"],
                    "representantes": data[i]["representantes"],
                    "tipo_documento": res_json["Nombre"],
                    "tipo_firma": data[i]["etapa_firma"],
                    "qr_url": qr_url
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
                reqFirma = requests.put(get_documentos_crud_url()+ 'firma_electronica/' + responsePostFirma["Id"], json=objFirmaElectronica)
                if reqFirma.status_code != 200:
                    return Response(json.dumps({'Status':'404','Error': str("the id "+str(responsePostFirma["Id"])+" does not exist in documents_crud")}), status=404, mimetype='application/json')
                #fin update firma

                #Inicio modificación metadatos de firma
                firma_electronica.pop("llaves")
                if qr_url:
                    firma_electronica["qr_url_segura"] = qr_url
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
            reqPutFirma = requests.put(get_gestor_documental_url()+'document/putUpdate', json=putUpdateJson).content
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


def resolveSecureQr(token):
    try:
        _trace("qr.redirect.start")
        validate_qr_token(token)
        _trace("qr.redirect.token_ok")
        front_base_url = get_qr_base_url()
        if not front_base_url:
            _trace("qr.redirect.missing_front_base")
            return Response(
                json.dumps({'Status':'404','Error':'QR client URL not configured'}),
                status=404,
                mimetype='application/json'
            )
        separator = "&" if "?" in front_base_url else "?"
        _trace("qr.redirect.redirecting")
        return redirect(f"{front_base_url}{separator}token={token}", code=302)
    except ValueError as e:
        _trace("qr.redirect.value_error")
        return Response(
            json.dumps({'Status':'400','Error':str(e)}),
            status=400,
            mimetype='application/json'
        )
    except Exception as e:
        _trace("qr.redirect.exception", f"type={type(e).__name__}")
        return Response(
            json.dumps({'Status':'500','Error':str(e)}),
            status=500,
            mimetype='application/json'
        )


def resolveSecureQrData(token):
    try:
        _trace("qr.resolve.start")
        payload = validate_qr_token(token)
        _trace("qr.resolve.token_ok")
        resFirma = requests.get(get_documentos_crud_url()+'firma_electronica/'+str(payload["firma_id"]))
        _trace("qr.resolve.documentos_crud.response", f"status={resFirma.status_code}")
        if resFirma.status_code != 200:
            _trace("qr.resolve.documentos_crud.non_200")
            return Response(
                json.dumps({'Status':'404','Error':'firma_electronica not found'}),
                status=404,
                mimetype='application/json'
            )

        responseGetFirma = json.loads(resFirma.content.decode('utf8').replace("'", '"'))
        documento = responseGetFirma.get("DocumentoId", {})
        if str(documento.get("Id", "")) != payload["documento_id"]:
            _trace("qr.resolve.document_mismatch")
            return Response(
                json.dumps({'Status':'403','Error':'QR token/document mismatch'}),
                status=403,
                mimetype='application/json'
            )

        enlace = documento.get("Enlace", "")
        if not enlace:
            _trace("qr.resolve.document_link.empty")
            return Response(
                json.dumps({'Status':'404','Error':'signed document link not available'}),
                status=404,
                mimetype='application/json'
            )

        gestor_documento_url = get_gestor_documental_url().rstrip("/") + '/document/' + str(enlace)
        resDocumento = requests.get(gestor_documento_url)
        _trace("qr.resolve.gestor_documental.response", f"status={resDocumento.status_code}")
        if resDocumento.status_code != 200:
            _trace("qr.resolve.gestor_documental.non_200")
            return Response(
                json.dumps({'Status':'404','Error':'document not found in gestor_documental_mid'}),
                status=404,
                mimetype='application/json'
            )

        responseDocumento = json.loads(resDocumento.content.decode('utf8').replace("'", '"'))
        file_content = responseDocumento.get("file:content", {})
        filename = file_content.get("name") or responseDocumento.get("dc:title") or f"{enlace}.pdf"

        response_payload = {
            "Status": "200",
            "res": {
                "firma_id": payload["firma_id"],
                "filename": filename,
                "token": token,
                "file_path": f"/qr/file/{token}",
            }
        }
        _trace("qr.resolve.end")
        return Response(json.dumps(response_payload), status=200, mimetype='application/json')
    except ValueError as e:
        _trace("qr.resolve.value_error")
        return Response(
            json.dumps({'Status':'400','Error':str(e)}),
            status=400,
            mimetype='application/json'
        )
    except Exception as e:
        _trace("qr.resolve.exception", f"type={type(e).__name__}")
        return Response(
            json.dumps({'Status':'500','Error':str(e)}),
            status=500,
            mimetype='application/json'
        )


def resolveSecureQrFile(token):
    try:
        _trace("qr.file.start")
        payload = validate_qr_token(token)
        _trace("qr.file.token_ok")
        resFirma = requests.get(get_documentos_crud_url()+'firma_electronica/'+str(payload["firma_id"]))
        _trace("qr.file.documentos_crud.response", f"status={resFirma.status_code}")
        if resFirma.status_code != 200:
            _trace("qr.file.documentos_crud.non_200")
            return Response(
                json.dumps({'Status':'404','Error':'firma_electronica not found'}),
                status=404,
                mimetype='application/json'
            )

        responseGetFirma = json.loads(resFirma.content.decode('utf8').replace("'", '"'))
        documento = responseGetFirma.get("DocumentoId", {})
        if str(documento.get("Id", "")) != payload["documento_id"]:
            _trace("qr.file.document_mismatch")
            return Response(
                json.dumps({'Status':'403','Error':'QR token/document mismatch'}),
                status=403,
                mimetype='application/json'
            )

        enlace = documento.get("Enlace", "")
        if not enlace:
            _trace("qr.file.document_link.empty")
            return Response(
                json.dumps({'Status':'404','Error':'signed document link not available'}),
                status=404,
                mimetype='application/json'
            )

        gestor_documento_url = get_gestor_documental_url().rstrip("/") + '/document/' + str(enlace)
        resDocumento = requests.get(gestor_documento_url)
        _trace("qr.file.gestor_documental.response", f"status={resDocumento.status_code}")
        if resDocumento.status_code != 200:
            _trace("qr.file.gestor_documental.non_200")
            return Response(
                json.dumps({'Status':'404','Error':'document not found in gestor_documental_mid'}),
                status=404,
                mimetype='application/json'
            )

        responseDocumento = json.loads(resDocumento.content.decode('utf8').replace("'", '"'))
        base64_file = responseDocumento.get("file", "")
        if not base64_file:
            _trace("qr.file.document_content.empty")
            return Response(
                json.dumps({'Status':'404','Error':'document content not available'}),
                status=404,
                mimetype='application/json'
            )

        try:
            file_bytes = base64.b64decode(base64_file)
        except Exception:
            _trace("qr.file.document_content.invalid_base64")
            return Response(
                json.dumps({'Status':'500','Error':'invalid document base64 content'}),
                status=500,
                mimetype='application/json'
            )

        file_content = responseDocumento.get("file:content", {})
        mime_type = file_content.get("mime-type", "application/pdf")
        filename = file_content.get("name") or responseDocumento.get("dc:title") or f"{enlace}.pdf"

        response = Response(file_bytes, status=200, mimetype=mime_type)
        response.headers["Content-Disposition"] = f'inline; filename="{filename}"'
        response.headers["Cache-Control"] = "no-store"
        _trace("qr.file.end")
        return response
    except ValueError as e:
        _trace("qr.file.value_error")
        return Response(
            json.dumps({'Status':'400','Error':str(e)}),
            status=400,
            mimetype='application/json'
        )
    except Exception as e:
        _trace("qr.file.exception", f"type={type(e).__name__}")
        return Response(
            json.dumps({'Status':'500','Error':str(e)}),
            status=500,
            mimetype='application/json'
        )
