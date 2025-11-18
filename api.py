import os
from flask import Flask, jsonify, request, send_from_directory
from conf import conf
from controllers import error
import logging
from routers import router
conf.checkEnv()

app = Flask(__name__) #Creo la app de servidor

router.addRutas(app)
error.add_error_handler(app)

# Configurar logger global
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# (Opcional) formato más detallado
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
if not logger.handlers:
    ch = logging.StreamHandler()
    ch.setFormatter(formatter)
    logger.addHandler(ch)


if __name__=='__main__':
    app.run(host='0.0.0.0', port=int(os.environ['API_PORT']))