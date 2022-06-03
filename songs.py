from google.cloud import datastore
from flask import Blueprint, request, Response
import json
import constants
from requests_oauthlib import OAuth2Session
from google.auth import crypt
from google.auth import jwt
from google.oauth2 import id_token
from google.auth.transport import requests
from google.auth import crypt
from google.auth import jwt

client = datastore.Client()

bp = Blueprint('songs', __name__, url_prefix='/songs')

def get_boats(owner_id):
    # Helper function that handles querying for boats
    query = client.query(kind=constants.boats)
    if owner_id is None:
        query.add_filter("public", "=", True)
    if owner_id is not None:
        query.add_filter("owner", "=", owner_id)

    # Convert the Datastore entity to a list so we can use len against it
    results = list(query.fetch())
    ordered_results = []

    for e in results:
        boat_key = client.key(constants.boats, e.key.id)
        boat = client.get(key=boat_key)
        # Datastore is returning results with different property orders and it looked messy.
        ordered_results.append({"id":e.key.id, 
                    "name":boat["name"], 
                    "type":boat["type"], 
                    "length":boat["length"], 
                    "public":boat["public"], 
                    "owner":boat["owner"]}) 
    res_body = json.dumps(ordered_results)
    res = Response(response=res_body, status=200)         
    return res
    
@bp.route('', methods=['POST','GET'])
def boats_post_get():
    if request.method == 'POST':
        content = request.get_json()
        # Define here so we only have to call id_token verification once.
        userid = ''
        encrypted_jwt = request.headers.get("Authorization")
        # Check that all required attributes are present in the POST request
        # Validation is not required, but keeping the code since it's pretty straightforward
        if content.get("name") == None or content.get("type") == None or content.get("length") == None or content.get("public") == None:
            # If the request was missing any of the required attributes, return error 400
            return (json.dumps({"Error": "The request object is missing at least one of the required attributes"}), 400)
        # Verify the JWT
        if not encrypted_jwt:
            res_body = json.dumps({"Error": "Invalid token"})
            res = Response(response=res_body, status=401)         
            return res
        # Postman will prepend "Bearer" so we have to discard that piece of the string
        #https://docs.python.org/3/library/stdtypes.html#str.split            

        try:
            idinfo = id_token.verify_oauth2_token(encrypted_jwt.split()[1], requests.Request(), constants.client_id)
            userid = idinfo['sub']
        except ValueError:
            res_body = json.dumps({"Error": "Invalid token"})
            res = Response(response=res_body, status=401)         
            return res
       
        # If the required attributes were present, and the JWT was valid, make a new boat!
        new_boat = datastore.entity.Entity(key=client.key(constants.boats))
        new_boat.update({"name": content["name"], 
                            "type": content["type"], 
                            "length": content["length"], 
                            "public": content["public"],
                            "owner": userid, 
                            "self": request.root_url + "boats/" + str(new_boat.key.id)})
        
        client.put(new_boat)

        return (json.dumps({
            "id": new_boat.key.id, 
            "name": new_boat["name"], 
            "type": new_boat["type"],
            "length": new_boat["length"],
            "public": new_boat["public"],
            "owner": new_boat["owner"],
            "self": request.root_url + "boats/" + str(new_boat.key.id)}), 201) 
    
    elif request.method == 'GET':
        # If the supplied JWT is valid, return status code 200 
        # and an array with all boats whose owner matches 
        # Define here so we only have to call id_token verification once.
        userid = ''
        encrypted_jwt = request.headers.get("Authorization")
         # Verify the JWT
        if not encrypted_jwt:
            #If no JWT is provided , return status code 200 
            # and an array with all public boats regardless of owner.
            all_boats = get_boats(None)
            return all_boats
        try:
            idinfo = id_token.verify_oauth2_token(encrypted_jwt.split()[1], requests.Request(), constants.client_id)
            userid = idinfo['sub']
            all_boats = get_boats(userid)
            return all_boats
        except ValueError:
            # If  an invalid JWT is provided, return status code 200 
            # and an array with all public boats regardless of owner.
            all_boats = get_boats(None)
            return all_boats

    else:
        return 'Method not recognized'

    
@bp.route('/<id>', methods=['GET','DELETE'])
def boats_get_delete(id):
    boat_key = client.key(constants.boats, int(id))
    boat = client.get(key=boat_key)
    boat_exists = False if boat == None else True  
    correct_owner = False
    valid_jwt = False
  
    userid = ''
    encrypted_jwt = request.headers.get("Authorization")

    if encrypted_jwt != None:    
        try:
            idinfo = id_token.verify_oauth2_token(encrypted_jwt.split()[1], requests.Request(), constants.client_id)
            userid = idinfo['sub']
            valid_jwt = True
        except ValueError:
            correct_owner = False
    
    # Does this user own the boat?
    if boat_exists and userid == boat["owner"]:
        correct_owner = True      
    
    if request.method == 'GET':
        # Does this boat exist, and does this JWT have access to it?
        if boat_exists and (correct_owner or boat["public"]):
            return (json.dumps({
                "id": boat.key.id, 
                "name": boat["name"], 
                "type": boat["type"],
                "length": boat["length"],
                "public": boat["public"],
                "owner": boat["owner"],
                "self": request.root_url + "boats/" + str(boat.key.id)}), 200) 
        
    elif request.method == 'DELETE':
        #Only the owner of a boat with a valid JWT should be able to delete that boat
        # If a boat exists with this boat_id and the JWT in the request is valid 
        # and the JWT belongs to the boat's owner, delete the boat and return 204 
        if boat_exists and valid_jwt and correct_owner:
            client.delete(boat_key)
            return ('',204)
        #Return 401 status code for missing or invalid JWTs.
        if not valid_jwt:
            return ('',401)
        #Return 403 status code:
        #If the JWT is valid but boat_id is owned by someone else
        if valid_jwt and not correct_owner:
            return ('',403)
        #If the JWT is valid but no boat with this boat_id exists
        if valid_jwt and not boat_exists:
            return ('',403)
         
    else:
        return 'Method not recognized'
 