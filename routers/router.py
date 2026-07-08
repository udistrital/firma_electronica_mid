from flask import Blueprint, request
from flask_restx import Api, Resource
from flask_cors import CORS, cross_origin
from controllers import healthCheck, controllerFirma
from models.model_params import define_parameters
from conf.conf import ENV, api_cors_config

api_bp = Blueprint("api_bp", __name__, url_prefix="/api")
CORS(api_bp, resources={r"/*": api_cors_config})

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

    @ns_v1.expect(model_params["upload_model"], validate=False)
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

    @ns_v1.expect(model_params["firma_model"], validate=False)
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
        return controllerFirma.postVerify(body)

@ns_v1.route("/qr")
class SecureQrResource(Resource):

    @ns_v1.expect(model_params["qr_token_model"], validate=True)
    @cross_origin(**api_cors_config)
    def post(self):
        """
            Redirige al cliente de verificación a partir de un token QR firmado
        """
        body = request.get_json()
        return controllerFirma.resolveSecureQr(body)

@ns_v1.route("/qr/resolve")
class SecureQrResolveResource(Resource):

    @ns_v1.expect(model_params["qr_token_model"], validate=True)
    @cross_origin(**api_cors_config)
    def post(self):
        """
            Resuelve un token QR validado y retorna datos del documento para el cliente
        """
        body = request.get_json()
        return controllerFirma.resolveSecureQrData(body)

@ns_v1.route("/qr/file")
class SecureQrFileResource(Resource):

    @ns_v1.expect(model_params["qr_token_model"], validate=True)
    @cross_origin(**api_cors_config)
    def post(self):
        """
            Retorna el archivo del documento validado a partir del token QR
        """
        body = request.get_json()
        return controllerFirma.resolveSecureQrFile(body)

@ns_v1.route("/firma_multiple")
class FirmaMultipleResource(Resource):

    @ns_v1.expect(model_params["firma_multiple_model"], validate=False)
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
