import logging, json, requests, os, base64
from flask import Flask,jsonify,request, Response
from models.firma import firmar
from models.firma_electronica import ElectronicSign

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
    try:
        for i in range(len(data)):
            if len(str(data[i]['file'])) < 1000:
                error_dict = {
                    'Status':'invalid pdf file',
                    'Code':'400'
                }
                return Response(json.dumps(error_dict), status=400, mimetype='application/json')
            IdDocumento = data[i]['IdTipoDocumento']
            res = requests.get(str(os.environ['DOCUMENTOS_CRUD_URL'])+'/tipo_documento/'+str(IdDocumento))

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
            with open(os.path.expanduser('./documents/documentToSign.pdf'), 'wb') as fout:
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
            resPost = requests.post(str(os.environ['DOCUMENTOS_CRUD_URL'])+'/documento', json=DicPostDoc).content
            responsePostDoc = json.loads(resPost.decode('utf8').replace("'", '"'))
            firma_electronica = firmar(str(data[i]['file']))
            electronicSign = ElectronicSign()
            #firma_completa = electronicSign.firmaCompleta(firma_electronica["llaves"]["firma"], responsePostDoc["Id"])
            objFirmaElectronica = {
                "Activo": True,
                "CodigoAutenticidad": firma_electronica["codigo_autenticidad"],
                "FirmaEncriptada": firma_electronica["llaves"]["firma"],
                "Firmantes": json.dumps(jsonFirmantes),
                "Llaves": json.dumps(firma_electronica["llaves"]),
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
            electronicSign.estamparFirmaElectronica(datos)
            jsonStringFirmantes = {
                "firmantes": json.dumps(data[i]["firmantes"]),
                "representantes": json.dumps(data[i]["representantes"])
            }
            #Inicio modificación metadatos de firma
            firma_electronica.pop("llaves")
            #Fin modificación
            all_metadata = str({** firma_electronica, ** data[i]['metadatos'],  ** jsonStringFirmantes}).replace("{'", '{\\"').replace("': '", '\\":\\"').replace("': ", '\\":').replace(", '", ',\\"').replace("',", '",').replace('",' , '\\",').replace("'}", '\\"}').replace('\\"', '\"').replace("[", "").replace("]", "").replace('"{', '{').replace('}"', '}').replace(": ", ":").replace(", ", ",").replace("[", "").replace("]", "").replace("},{", ",")
            DicPostDoc = {
                'Metadatos': all_metadata,
                "firmantes": data[i]["firmantes"],
                "representantes": data[i]["representantes"],
                'Nombre': data[i]['nombre'],
                "Descripcion": data[i]['descripcion'],
                'TipoDocumento' :  res_json,
                'Activo': True
            }

            putUpdateJson = [{
                "IdTipoDocumento": data[i]['IdTipoDocumento'],
                "nombre": data[i]['nombre'],
                "metadatos": all_metadata,
                "descripcion": data[i]['descripcion'],
                "file": str(electronicSign.docFirmadoBase64()),
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
            resFirma = requests.get(str(os.environ['DOCUMENTOS_CRUD_URL'])+'/firma_electronica/'+str(data[i]["firma"]))
            if resFirma.status_code != 200:
                return Response(resFirma, resFirma.status_code, mimetype='application/json')
            responseGetFirma = json.loads(resFirma.content.decode('utf8').replace("'", '"'))
            firma = responseGetFirma["FirmaEncriptada"].encode()
            if "firma" not in responseGetFirma["DocumentoId"]["Metadatos"]:
                error_dict = {'Message': "document not signed", 'code': '404'}
                return Response(json.dumps(error_dict), status=404, mimetype='application/json')
            elif firma in responseGetFirma["DocumentoId"]["Metadatos"].encode():
                responseNuxeo = requests.get(str(os.environ['GESTOR_DOCUMENTAL_URL'])+'document/'+str(responseGetFirma["DocumentoId"]["Enlace"])).content
                # succes_dict = {'Status': responseNuxeo, 'code': '200'}
                # return Response(json.dumps(succes_dict), status=200, mimetype='application/json')
                resString = str(responseNuxeo)
                resString = resString.replace("'","")
                resString = resString.lstrip("b")
                responseNuxeo = json.loads(resString)
                #INICIO COMPARACIÓN
                base64Nuxeo = str(responseNuxeo['file'])
                base64User = str (data[i]["fileUp"])
                urlFileUp = str (data[0]["urlFileUp"])
                fileEqual = True #Por defecto true ya que de ser así sólo se muestra un Doc
                if base64User != "":
                    if base64Nuxeo == base64User:
                        fileEqual = True
                    else:
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
            logging.error("type error: " + str(e))
            if str(e) == "'firma'":
                error_dict = {'Status':'the field firma is required','Code':'400'}
                return Response(json.dumps(error_dict), status=400, mimetype='application/json')
            elif '400' in str(e):
                DicStatus = {'Status':'invalid request body', 'Code':'400'}
                return Response(json.dumps(DicStatus), status=400, mimetype='application/json')
            return Response(json.dumps({'Status':'500','Error':str(e)}), status=500, mimetype='application/json')