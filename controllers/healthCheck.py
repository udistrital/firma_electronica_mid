from flask import jsonify

def health_check():
    return jsonify({
                'Status':'Ok',
                'Code':'200'
        }), 200

