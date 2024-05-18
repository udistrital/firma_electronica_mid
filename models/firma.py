
import base64
import logging
from cryptography.exceptions import UnsupportedAlgorithm
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization

def firmar(plain_text):
    try:
        #objeto_firmado = []
        # genera un par de claves 
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
            backend=default_backend()
        )
        public_key = private_key.public_key()

        #serializacion de llaves 
        pem_privada = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )

        pem_publica = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
        # firma el documento
        signature = private_key.sign(
            data=plain_text.encode('utf-8'),
            padding=padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH
            ),
            algorithm=hashes.SHA256()
        )

        mascara = abs(hash(str(pem_publica)))
        objeto_firmado = {
            "codigo_autenticidad": str(mascara),
            "llaves": {
                "llave_publica": base64.urlsafe_b64encode(pem_publica).decode("utf-8"),
                "llave_privada": base64.urlsafe_b64encode(pem_privada).decode("utf-8"),
                "firma": base64.urlsafe_b64encode(signature).decode("utf-8")
            }
        }
        #string_json = str(objeto_firmado).replace("{'", '{ \ "').replace("': '", ' \ ": \ "').replace("': ", ' \ ": ').replace(", '", ', \ "').replace("',", '",').replace('",' , ' \ ",').replace("'}", ' \ " } ').replace(" ", "").replace('\\"', '\"')
        return objeto_firmado
        #return string_json
    except UnsupportedAlgorithm:        
        logging.error("signature failed, type error: " + str(UnsupportedAlgorithm))