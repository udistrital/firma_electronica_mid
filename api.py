import os
from flask import Flask, jsonify, request, send_from_directory
from conf import conf
from controllers import error
from routers import router
conf.checkEnv()

app = Flask(__name__) #Creo la app de servidor

router.addRutas(app)
error.add_error_handler(app)
if __name__=='__main__':
    app.run(host='0.0.0.0', port=int(os.environ['API_PORT']))