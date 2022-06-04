from flask import Blueprint, request, Response
import json

def accept_type_validation(accept_mimetypes):
    """
    Accepts a request and a list of mimetypes that the endpoint can provide.
    If a match is found, returns True, else returns False.
    """
    res = None
    # Check that a valid Accept type was specified.
    matches = [value for value in accept_mimetypes if value in request.accept_mimetypes]
    if len(matches) < 1: 
        res_body = json.dumps({"Error": "No match was found between the request's Accept header and the available options for this endpoint"})
        res = Response(response=res_body, status=406, mimetype="application/json")         
        res.headers.set('Content-Type', 'application/json; charset=utf-8') 
    return res
    
def request_validation():
    """ 
    Single function to validate requirements that are shared between different types of requests.
    Avoids code duplication.
    """
    # Check that the request is JSON
    res = None
    content = None
    try:
        content = request.get_json()
    except:
        res_body = json.dumps({"Error": "Only application/json MIMEtype is accepted"})
        res = Response(response=res_body, status=415, mimetype="application/json")         
        res.headers.set('Content-Type', 'application/json; charset=utf-8')  
    
    return content, res