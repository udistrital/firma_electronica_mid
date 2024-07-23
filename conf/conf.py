import os
import sys

# Environmen variables list
# Cambio temporal mientras se ajusta la variable
#variables = ['API_PORT', 'DOCUMENTOS_CRUD_URL', 'GESTOR_DOCUMENTAL_URL', 'ENVIRONMENT']
variables = ['API_PORT', 'DOCUMENTOS_CRUD_URL', 'GESTOR_DOCUMENTAL_URL']

varTemp = "develop"
if varTemp == "develop":
    origins = ["*"]
else:
    origins = ["*.udistrital.edu.co"]

api_cors_config = {
    "origins": origins,
    "methods": ["OPTIONS", "GET", "POST"],
    "allow_headers": ["Authorization", "Content-Type"]
}

def checkEnv():
# Environment variables checking
    for variable in variables:
        if variable not in os.environ:
            print(str(variable) + " environment variable not found")
            sys.exit()