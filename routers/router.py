import logging
from flask import Blueprint, request
from flask_restx import Api, Resource
from flask_cors import CORS, cross_origin
from controllers import healthCheck, controllerFirma
from models.model_params import define_parameters
from conf.conf import ENV, api_cors_config

api_bp = Blueprint("api_bp", __name__, url_prefix="/api")
CORS(api_bp)

@api_bp.route("", methods=["GET"])
@api_bp.route("/", methods=["GET"])
def api_health():
    return healthCheck.health_check()

docDocumentacion = Api(
    api_bp,
    version="1.0",
    title="firma_electronica_mid",
    description="API para la firma electrónica de documentos",
    doc="/swagger" if ENV == "dev" else None
)

ns_v1 = docDocumentacion.namespace(
    "v1",
    path="/v1",
    description="Servicios de firma electrónica"
)

model_params = define_parameters(docDocumentacion)

@ns_v1.route("/firma_electronica")
class FirmaElectronicaResource(Resource):

    @ns_v1.expect(model_params["upload_model"], validate=True)
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
        body = request.get_json()
        return controllerFirma.postFirmaElectronica(body)

@ns_v1.route("/verify")
class VerifyFirmaResource(Resource):

    @ns_v1.expect(model_params["firma_model"], validate=True)
    @cross_origin(**api_cors_config)
    def post(self):
        """
            Permite verificar la firma electronica de un documento.

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
        logging.info("[trace] http.verify.enter")
        return controllerFirma.postVerify(body)

@ns_v1.route("/qr/<string:token>")
class SecureQrResource(Resource):

    @cross_origin(**api_cors_config)
    def get(self, token):
        """
            Redirige al cliente de verificación a partir de un token QR firmado
        """
        logging.info("[trace] http.qr.redirect.enter")
        return controllerFirma.resolveSecureQr(token)

@ns_v1.route("/qr/resolve/<string:token>")
class SecureQrResolveResource(Resource):

    @cross_origin(**api_cors_config)
    def get(self, token):
        """
            Resuelve un token QR validado y retorna datos del documento para el cliente
        """
        logging.info("[trace] http.qr.resolve.enter")
        return controllerFirma.resolveSecureQrData(token)

@ns_v1.route("/qr/file/<string:token>")
class SecureQrFileResource(Resource):

    @cross_origin(**api_cors_config)
    def get(self, token):
        """
            Retorna el archivo del documento validado a partir del token QR
        """
        logging.info("[trace] http.qr.file.enter")
        return controllerFirma.resolveSecureQrFile(token)

@ns_v1.route("/firma_multiple")
class FirmaMultipleResource(Resource):

    @ns_v1.expect(model_params["firma_multiple_model"], validate=True)
    @cross_origin(**api_cors_config)
    def post(self):
        """
            Permite realizar firma múltiple asincrónica utilizando como pámetro para decidir la etapa en la que se está firmando la clave valor etapa_firma

            Parameters
            ----------
            request : json
                Json Body {Document}, Documento que será firmado

            Returns
            -------
            Response
                Respuesta con cuerpo, status y en formato json
        """
        body = request.get_json()
        return controllerFirma.FirmaMultiple(body)

def addRutas(app):
    app.register_blueprint(api_bp)
