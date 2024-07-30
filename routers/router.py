from flask import  jsonify, Blueprint, request
from flask_restx import Resource, Api
from controllers import healthCheck, controllerFirma
from models.model_params import define_parameters
from conf.conf import api_cors_config
from flask_cors import cross_origin, CORS

#Creo función para capturar la app de server y poder hacer routing

def addRutas(app_main):
    app_main.register_blueprint(healthCheckController)
    app_main.register_blueprint(docControl, url_prefix='/v1')

healthCheckController = Blueprint('healthCheckController', __name__, url_prefix='/')
CORS(healthCheckController)

@healthCheckController.route('/')
def _():
    return healthCheck.healthCheck(docDocumentacion)

#Uso Blueprint para poder utilizar la función route
docControl=Blueprint('docControl', __name__)
CORS(docControl)
#----------INICIO SWAGGER --------------
docDocumentacion = Api(docControl, version='1.0',title="firma_electronica", description='API para la firma electrónica de documentos',doc='/swagger')
docFirmacontroller = docDocumentacion.namespace("firma_electronica",path="/", description="methods for electronic signature process")

model_params=define_parameters(docDocumentacion)
#----------FIN SWAGGER ----------------

#Firma electrónica
@docFirmacontroller.route('/firma_electronica')
class docFirmaElectronica(Resource):
    @docDocumentacion.doc(responses={
        200: 'Success',
        500: 'Nuxeo Error',
        400: 'Bad request'
    }, body=model_params['upload_model'])
    @docFirmacontroller.expect(model_params['request_parser'])
    @cross_origin(**api_cors_config)
    def post(self):
        """
            Permite firmar un documento y subirlo a nuxeo consumiendo a gestor documental

            Parameters
            ----------
            request : json
                Json Body {Document}, Documento que será firmado

            Returns
            -------
            Response
                Respuesta con cuerpo, status y en formato json
        """
        body=request.get_json()
        return controllerFirma.postFirmaElectronica(body)

#Verificación Firma electrónica
@docFirmacontroller.route('/verify')
class docPostVerify(Resource):
    @docDocumentacion.doc(responses={
        200: 'Success',
        500: 'Nuxeo error',
        400: 'Bad request'
    }, body=model_params['firma_model'])
    @docFirmacontroller.expect(model_params['request_parser'])
    @cross_origin(**api_cors_config)
    def post(self):
        """
            permite verificar la firma electronica de un documento

            Parameters
            ----------
            request : json
                Json Body {firma}, firma electronica encriptada con el id

            Returns
            -------
            Response
                Respuesta con cuerpo, status y en formato json
        """
        body = request.get_json()
        return controllerFirma.postVerify(body)