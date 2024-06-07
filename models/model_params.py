from flask_restx import reqparse, fields

def define_parameters(api):

    request_parser = reqparse.RequestParser(bundle_errors=True)
    request_parser.add_argument('list', location='json', type=list, required=True)

    metadata_doc_crud_model = api.model('documentos_crud_metadata', {
        'dato_a': fields.String,
        'dato_b': fields.String,
        'dato_n': fields.String
    })

    firmantes_model =api.model('firmantes_info', {
        'nombre': fields.String,
        'cargo': fields.String,
        'tipoId': fields.String,
        'identificacion': fields.String,
    })

    representantes_model =api.model('representantes_info', {
        'nombre': fields.String,
        'cargo': fields.String,
        'tipoId': fields.String,
        'identificacion': fields.String,
    })

    upload_model = [api.model('upload_resquest', {
        'IdTipoDocumento': fields.Integer,
        'nombre': fields.String,
        'metadatos': fields.Nested(metadata_doc_crud_model),
        'firmantes': fields.Nested(firmantes_model),
        'representantes': fields.Nested(representantes_model),
        'descripcion': fields.String,
        'file': fields.String
    })]

    firma_model = [api.model('firma_request',{
        'firma': fields.String,
    })]
    
    return {k: v for k, v in vars().items() if not k.startswith('__')}