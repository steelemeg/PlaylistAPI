from google.cloud import datastore
from flask import Blueprint, request, Response, jsonify
import json
import constants
from helpers import *
from requests_oauthlib import OAuth2Session
from google.auth import crypt
from google.auth import jwt
from google.oauth2 import id_token
from google.auth.transport import requests
from google.auth import crypt
from google.auth import jwt


client = datastore.Client()

bp = Blueprint('users', __name__, url_prefix='/users')

@bp.route('/<owner_id>/boats', methods=['GET'])
def get_public_boats_by_owner(owner_id):
    # Return 200 status code and an array with all public boats for the specified owner_id 
    # Do not care about request JWT. If no results, return 200 and an empty list.
    query = client.query(kind=constants.boats)
    query.add_filter("owner", "=", owner_id)
    query.add_filter("public", "=", True)
   
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
    

@bp.route('/get-jwt-user')
def get_jwt_user():
    # This function is just for testing--it allows Postman to get the userid from 
    # the sub field of a decoded JWT
    encrypted_jwt = request.headers.get("Authorization")
    try:
        idinfo = id_token.verify_oauth2_token(encrypted_jwt.split()[1], requests.Request(), constants.client_id)
        userid = idinfo['sub']
        res_body = json.dumps({"user": userid})
        res = Response(response=res_body, status=200)
        return res
        
    except ValueError:
        res_body = json.dumps({"Error": "Invalid token"})
        res = Response(response=res_body, status=401)
        return res
        
@bp.route('', methods=['POST','GET','DELETE','PUT','PATCH'])
def users_get():
    if request.method == 'GET':
        # This endpoint is required to be unprotected, so no JWT requirement is enforced.
        # Make sure the request accepts JSON
        res = accept_type_validation(['application/json'])
        if res != None:
            return res
        # Opting to skip pagination, since my best way of testing this is by looking for my own users.
        # I don't know how many will be created for testing, so this ensures I can "see" them all on one page.
        all_users = get_things("users", False, None)
        return all_users

    else:
        # Use status code 405 for PUT, PATCH, or DELETE requests on the root users URL
        # And presumably any other verb, which would be invalid and caught differently by Flask.
        print("check")
        res_body = json.dumps({"Error": "Invalid method for this endpoint"})
        res = Response(response=res_body, status=405, mimetype="application/json")         
        res.headers.set('Content-Type', 'application/json; charset=utf-8')            
        return res