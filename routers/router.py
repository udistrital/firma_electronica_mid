from flask import Flask, jsonify, Blueprint, request, send_from_directory
from controllers import controllerFirma
from DatosPrueba import documents
from flask_swagger_ui import get_swaggerui_blueprint
from flask_restx import Resource
from nuxeo.client import Nuxeo
#Creo función para capturar la app de server y poder hacer routing
def addRutas(app_main):
    app_main.register_blueprint(docControl)
#Uso Blueprint para poder utilizar la función route
docControl=Blueprint('docControl', __name__)

#----------INICIO SWAGGER --------------
@docControl.route('/static/<path:path>')
def send_swagger(path):
    return send_from_directory('static',path)
SWAGGER_URL='/swagger'
API_URL='/static/swagger.json'
swaggerui_blueprint = get_swaggerui_blueprint(
    SWAGGER_URL,
    API_URL,
    config={
        'app_name': "API de Firma electrónica"
    }
)
docControl.register_blueprint(swaggerui_blueprint,url_prefix=SWAGGER_URL)
#----------FIN SWAGGER ----------------

#Ruta de Home
@docControl.route('/')
def home():
    return jsonify({'message':'Todo ok'})

#GETALL para traer documentos
@docControl.route('/documents', methods=['GET'])
def getDocuments():
    return controllerFirma.getAll()


#GETONE
@docControl.route('/documents/<string:titulo>')
def getDocument(titulo):
    return controllerFirma.getOne(titulo)

#POST
@docControl.route('/documents', methods=['POST'])
def addDocument():
    return controllerFirma.post()

#PUT
@docControl.route('/documents/<string:titulo_doc>', methods=['PUT'])
def editDocument(titulo_doc):
    return controllerFirma.put(titulo_doc)

#DELETE
@docControl.route('/documents/<string:titulo_doc>', methods=['DELETE'])
def deleteDoc(titulo_doc):
    return controllerFirma.delete(titulo_doc)

#Firma electrónica
@docControl.route('/firma_electronica')
def firmaElectronica():
    body=request.get_json()
    controllerFirma.postFirmaElectronica(body)
#Verificación Firma electrónica