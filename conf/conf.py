import os
import sys
import re

variables = ['API_PORT', 'DOCUMENTOS_CRUD_URL', 'GESTOR_DOCUMENTAL_URL', 'ENV']

if os.environ['ENV'] == "dev":
    origins = ["*"]
else:
    origins = [re.compile(r".*\.udistrital\.edu\.co$")]

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