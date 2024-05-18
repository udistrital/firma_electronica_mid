import logging, json, requests, os, base64
from flask import Flask,jsonify,request, Response
from DatosPrueba import documents
from models.firma import firmar
from models.firma_electronica import ElectronicSign
def getAll():
    return jsonify(documents)

def getOne(titulo):
    documentFound=[document for document in documents if document['titulo']==titulo]
    if (len(documentFound)>0):
        return jsonify({"document": documentFound[0]})
    return jsonify({'message':'Documento no entontrado'})

def post():
    newDocument={
        "formato":request.json['formato'],
        "titulo":request.json['titulo'],
        "hash":request.json['hash']
    }
    documents.append(newDocument)
    return jsonify({"message":"Documento agregado","documentos": documents})

def put(titulo_doc):
    documentFound=[document for document in documents if document['titulo']==titulo_doc]
    if (len(documentFound)>0):
        documentFound[0]['formato']=request.json['formato']
        documentFound[0]['titulo']=request.json['titulo']
        documentFound[0]['hash']=request.json['hash']
        return jsonify({
            "message": "Documento actualizado",
            "document": documentFound[0]
        })
    return jsonify({"message": "documento no encontrado"})

def delete(titulo_doc):
    documentFound=[document for document in documents if document['titulo']==titulo_doc]
    if(len(documentFound)>0):
        documents.remove(documentFound[0])
        return jsonify({
            "message": "Documento eliminado",
            "documents": documents
        })
    return jsonify({"message":"Documento no entontrado"})
def postFirmaElectronica(body):
    try:
        data=body
        for i in range(len(data)):
            IdDocumento = data[i]['IdTipoDocumento']
            res = requests.get(str(os.environ['DOCUMENTOS_CRUD_URL'])+'/tipo_documento/'+str(IdDocumento))
            
            if res.status_code != 200:
                return Response(json.dumps({'Status':'404','Error': str("the id "+str(data[i]['IdTipoDocumento'])+" does not exist in documents_crud")}), status=404, mimetype='application/json')

            res_json = json.loads(res.content.decode('utf8').replace("'", '"'))

            blob = base64.b64decode(data[i]['file'])
            with open(os.path.expanduser('./documents/documentToSign.pdf'), 'wb') as fout:
                fout.write(blob)

            jsonFirmantes = {
                    "firmantes": data[i]["firmantes"],
                    "representantes": data[i]["representantes"],
            }

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
            firma_completa = electronicSign.firmaCompleta(firma_electronica["llaves"]["firma"], responsePostDoc["Id"])
            objFirmaElectronica = {
                "Activo": True,
                "CodigoAutenticidad": firma_electronica["codigo_autenticidad"],
                "FirmaEncriptada": firma_completa,
                "Firmantes": json.dumps(jsonFirmantes),
                "Llaves": json.dumps(firma_electronica["llaves"]),
            }
            reqPostFirma = requests.post(str(os.environ['DOCUMENTOS_CRUD_URL'])+'/firma_electronica', json=objFirmaElectronica).content
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
    except Exception as e:
        logging.error("type error: "+str(e))
    