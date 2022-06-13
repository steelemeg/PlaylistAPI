from google.cloud import datastore
from flask import Blueprint, request, Response
import json


client = datastore.Client()

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
    
def get_things(thing_type, pagination, owner_id):
    # Helper function that handles querying for generic objects
    # Accepts two parameters: the Datastore kind, and a boolean governing if pagination will be implemented.
    query = client.query(kind=thing_type)
    if owner_id is not None:
        query.add_filter("owner", "=", owner_id)
    if pagination:
        q_limit = int(request.args.get('limit', '5'))
        q_offset = int(request.args.get('offset', '0'))
        l_iterator = query.fetch(limit= q_limit, offset=q_offset)
        pages = l_iterator.pages
        results = list(next(pages))

        if l_iterator.next_page_token:
            next_offset = q_offset + q_limit
            next_url = request.base_url + "?limit=" + str(q_limit) + "&offset=" + str(next_offset)
        else:
            next_url = None

        ordered_results = []      
           
        for e in results:
            e["id"] = e.key.id
            e["self"] = request.root_url + thing_type + "/" + str(e.key.id)
        output = {thing_type: results}
        if next_url:
            output["next"] = next_url
                 
        res_body = json.dumps(output)
        res = Response(response=res_body, status=200, mimetype="application/json")         
        res.headers.set('Content-Type', 'application/json; charset=utf-8')          
        return res
    else:    
        # Convert the Datastore entity to a list so we can use len against it
        results = list(query.fetch())

    for e in results:
        e["id"] = e.key.id
        e["self"] = request.root_url + thing_type + "/" + str(e.key.id)

    res_body = json.dumps(results)
    res = Response(response=res_body, status=200, mimetype="application/json")         
    res.headers.set('Content-Type', 'application/json; charset=utf-8')              
    return res