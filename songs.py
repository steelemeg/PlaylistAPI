from google.cloud import datastore
from flask import Blueprint, request, Response
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

bp = Blueprint('songs', __name__, url_prefix='/songs')

def get_songs():
    # Helper function that handles querying for songs
    query = client.query(kind=constants.songs)
    q_limit = int(request.args.get('limit', '5'))
    q_offset = int(request.args.get('offset', '0'))
    l_iterator = query.fetch(limit= q_limit, offset=q_offset)
    pages = l_iterator.pages
    results = list(next(pages))

    # how to combine nice ordering with the stupid results paginator TODO
    if l_iterator.next_page_token:
        next_offset = q_offset + q_limit
        next_url = request.base_url + "?limit=" + str(q_limit) + "&offset=" + str(next_offset)
    else:
        next_url = None

    ordered_results = []      
       
    for e in results:
        e["id"] = e.key.id
        e["self"] = request.root_url + "songs/" + str(e.key.id)
    output = {"songs": results}
    if next_url:
        output["next"] = next_url
             
    res_body = json.dumps(output)
    res = Response(response=res_body, status=201, mimetype="application/json")         
    res.headers.set('Content-Type', 'application/json; charset=utf-8')          
    return res
    
@bp.route('', methods=['POST','GET'])
def songs_post_get():
    if request.method == 'POST':
        # Check that the request is JSON 
        content, res = request_validation()
        if res != None:
            return res
        # This endpoint only returns JSON
        res = accept_type_validation(['application/json'])
        if res != None:
            return res
            
        content = request.get_json()
        # Define here so we only have to call id_token verification once.
        userid = ''
        encrypted_jwt = request.headers.get("Authorization")
        # Check that all required attributes are present in the POST request
        # Validation is not required, but keeping the code since it's pretty straightforward
        if content.get("name") == None or content.get("artist") == None or content.get("length") == None :
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
       
        # If the required attributes were present, and the JWT was valid, make a new song!
        # If no album was provided, plug in a blank space
        album = " " if content.get("album") == None else content.get("album")
            
        new_song = datastore.entity.Entity(key=client.key(constants.songs))
        new_song.update({"name": content["name"], 
                            "artist": content["artist"],
                            "album": album,
                            "length": content["length"], 
                            "playlists": [],
                            "self": request.root_url + "songs/" + str(new_song.key.id)})
        
        client.put(new_song)


        res_body = json.dumps({
            "id": new_song.key.id, 
            "name": new_song["name"], 
            "artist": new_song["artist"],
            "album": new_song["album"],
            "length": new_song["length"],
            "playlists": new_song["playlists"],
            "self": request.root_url + "songs/" + str(new_song.key.id)}) 
        res = Response(response=res_body, status=201, mimetype="application/json")         
        res.headers.set('Content-Type', 'application/json; charset=utf-8')            
        return res
    
    elif request.method == 'GET':
        # Songs are not associated with users, so no JWT requirement is enforced.
        # Make sure the request accepts JSON
        res = accept_type_validation(['application/json'])
        if res != None:
            return res
        all_songs = get_songs()
        return all_songs

    else:
        return 'Method not recognized'

    
@bp.route('/<id>', methods=['GET','DELETE'])
def songs_get_delete(id):
    song_key = client.key(constants.songs, int(id))
    song = client.get(key=song_key)
    song_exists = False if song == None else True  
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
    
    # Does this user own the song?
    if song_exists and userid == song["owner"]:
        correct_owner = True      
    
    if request.method == 'GET':
        # Does this song exist, and does this JWT have access to it?
        if song_exists and (correct_owner or song["public"]):
            return (json.dumps({
                "id": song.key.id, 
                "name": song["name"], 
                "type": song["type"],
                "length": song["length"],
                "public": song["public"],
                "owner": song["owner"],
                "self": request.root_url + "songs/" + str(song.key.id)}), 200) 
        
    elif request.method == 'DELETE':
        #Only the owner of a song with a valid JWT should be able to delete that song
        # If a song exists with this song_id and the JWT in the request is valid 
        # and the JWT belongs to the song's owner, delete the song and return 204 
        if song_exists and valid_jwt and correct_owner:
            client.delete(song_key)
            return ('',204)
        #Return 401 status code for missing or invalid JWTs.
        if not valid_jwt:
            return ('',401)
        #Return 403 status code:
        #If the JWT is valid but song_id is owned by someone else
        if valid_jwt and not correct_owner:
            return ('',403)
        #If the JWT is valid but no song with this song_id exists
        if valid_jwt and not song_exists:
            return ('',403)
         
    else:
        return 'Method not recognized'
 