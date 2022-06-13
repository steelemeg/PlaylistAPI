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

bp = Blueprint('playlists', __name__, url_prefix='/playlists')
   
@bp.route('', methods=['POST','GET'])
def playlists_post_get():
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
        if content.get("name") == None or content.get("shuffle") == None or content.get("description") == None:
            # If the request was missing any of the required attributes, return error 400
            return (json.dumps({"Error": "The request object is missing at least one of the required attributes"}), 400)

        # Check if the shuffle value is a boolean
        if content.get("shuffle").lower() not in ("true", "false"):
            res_body = json.dumps({"Error": "Valid shuffle values are true and false"})
            res = Response(response=res_body, status=400, mimetype="application/json")         
            res.headers.set('Content-Type', 'application/json; charset=utf-8')   
            return res
            
        # Verify the JWT
        if not encrypted_jwt:
            res_body = json.dumps({"Error": "Invalid token"})
            res = Response(response=res_body, status=401)    
            res.headers.set('Content-Type', 'application/json; charset=utf-8')             
            return res
        # Postman will prepend "Bearer" so we have to discard that piece of the string
        #https://docs.python.org/3/library/stdtypes.html#str.split            

        try:
            idinfo = id_token.verify_oauth2_token(encrypted_jwt.split()[1], requests.Request(), constants.client_id)
            userid = idinfo['sub']
        except ValueError:
            res_body = json.dumps({"Error": "Invalid token"})
            res = Response(response=res_body, status=401)    
            res.headers.set('Content-Type', 'application/json; charset=utf-8')             
            return res
       
        # If the required attributes were present, and the JWT was valid, make a new playlist!
        new_playlist = datastore.entity.Entity(key=client.key(constants.playlists))
        new_playlist.update({"name": content["name"], 
                            "shuffle": content["shuffle"], 
                            "description": content["description"], 
                            "owner": userid, 
                            "songs": [],
                            "self": request.root_url + "playlists/" + str(new_playlist.key.id)})
        
        client.put(new_playlist)

        res_body = json.dumps({
            "id": new_playlist.key.id, 
            "name": new_playlist["name"], 
            "shuffle": new_playlist["shuffle"],
            "description": new_playlist["description"],
            "owner": new_playlist["owner"],
            "songs": new_playlist["songs"],
            "self": request.root_url + "playlists/" + str(new_playlist.key.id)})
        res = Response(response=res_body, status=201, mimetype="application/json")         
        res.headers.set('Content-Type', 'application/json; charset=utf-8')  
        return res
    
    elif request.method == 'GET':
        # This endpoint only returns JSON
        res = accept_type_validation(['application/json'])
        if res != None:
            return res
        # If the supplied JWT is valid, return status code 200 
        # and an array with all playlists whose owner matches 
        # Define here so we only have to call id_token verification once.
        userid = ''
        encrypted_jwt = request.headers.get("Authorization")
         # Verify the JWT
        if not encrypted_jwt:
            #If no JWT is provided , return status code 200 
            # and an array with all public boats regardless of owner.
            res_body = json.dumps({"Error": "Invalid token"})
            res = Response(response=res_body, status=401)    
            res.headers.set('Content-Type', 'application/json; charset=utf-8')             
            return res

        try:
            idinfo = id_token.verify_oauth2_token(encrypted_jwt.split()[1], requests.Request(), constants.client_id)
            userid = idinfo['sub']
            all_playlists = get_things(constants.playlists, True, userid)
            return all_playlists
        except ValueError:
            # If an invalid JWT is provided, return status code 401 Unauthorized 
            res_body = json.dumps({"Error": "Invalid token"})
            res = Response(response=res_body, status=401)    
            res.headers.set('Content-Type', 'application/json; charset=utf-8')             
            return res

    else:
        res_body = json.dumps({"Error": "Invalid method for this endpoint"})
        res = Response(response=res_body, status=405, mimetype="application/json")         
        res.headers.set('Content-Type', 'application/json; charset=utf-8')            
        return res

    
@bp.route('/<id>', methods=['GET','DELETE','PUT','PATCH','POST'])
def playlists_get_update_delete(id):
    playlist_key = client.key(constants.playlists, int(id))
    playlist = client.get(key=playlist_key)
    playlist_exists = False if playlist == None else True  
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
    # Does this user own the playlist?
    if playlist_exists and userid == playlist["owner"]:
        correct_owner = True      
    
    if request.method == 'GET':
        # Does this playlist exist, and does this JWT have access to it?
        if playlist_exists and correct_owner:
            res_body = json.dumps({
                "id": playlist.key.id, 
                "name": playlist["name"], 
                "description": playlist["description"],
                "shuffle": playlist["shuffle"],
                "songs": playlist["songs"],
                "self": request.root_url + "playlists/" + str(playlist.key.id)})
            res = Response(response=res_body, status=200, mimetype="application/json")    
            res.headers.set('Content-Type', 'application/json; charset=utf-8')    
            return res 
        
        # Handle the case where the user is valid but the playlist does not exist
        elif not playlist_exists:
            res_body = json.dumps({"Error": "No playlist with this playlist_id exists"})
            res = Response(response=res_body, status=404, mimetype="application/json")         
            res.headers.set('Content-Type', 'application/json; charset=utf-8')  
            return res
        else:
            # This JWT doesn't correspond to the playlist owner
            res = Response(response='', status=403, mimetype="application/json")       
            res.headers.set('Content-Type', 'application/json; charset=utf-8')            
            return res
            
    elif request.method == 'PATCH':
        # Check that the request is JSON 
        content, res = request_validation()
        if res != None:
            return res
        # This endpoint only returns JSON
        res = accept_type_validation(['application/json'])
        if res != None:
            return res
            
        #Only the owner of a playlist with a valid JWT should be able to update that playlist
        # If a playlist exists with this playlist_id and the JWT in the request is valid 
        # and the JWT belongs to the playlist's owner, update the playlist and return 204 
        if playlist_exists and valid_jwt and correct_owner:           
            # Check that at least one required attributes are present in the PATCH request
            if content.get("name") == None and content.get("description") == None and content.get("shuffle") == None:
                # If the request was missing all of the required attributes, return error 400
                res_body = json.dumps({"Error": "The request object is missing any recognized attributes"})
                res = Response(response=res_body, status=400, mimetype="application/json")         
                res.headers.set('Content-Type', 'application/json; charset=utf-8')            
                return res
                    
            # Check if the shuffle value is a boolean
            if content.get("shuffle") is not None and content.get("shuffle").lower() not in ("true", "false"):
                res_body = json.dumps({"Error": "Valid shuffle values are true and false"})
                res = Response(response=res_body, status=400, mimetype="application/json")         
                res.headers.set('Content-Type', 'application/json; charset=utf-8')   
                return res
            
                    
            # Update the playlist!
            if content.get("name") != None:
                playlist.update({"name": content["name"]})
            if content.get("description") != None:
                playlist.update({"description": content["description"]})
            if content.get("shuffle") != None:
                playlist.update({"shuffle": content["shuffle"]})

            # Persist the entity to Datastore
            client.put(playlist)
            res_body = json.dumps({
                "id": playlist.key.id, 
                "name": playlist["name"], 
                "description": playlist["description"],
                "shuffle": playlist["shuffle"],
                "songs": playlist["songs"],
                "self": request.root_url + "playlists/" + str(playlist.key.id)})

            res = Response(response=res_body, status=200, mimetype="application/json")         
            res.headers.set('Content-Type', 'application/json; charset=utf-8')
            return res
        #Return 401 status code for missing or invalid JWTs.
        if not valid_jwt:
            return ('',401)
        #Return 403 status code:
        #If the JWT is valid but playlist_id is owned by someone else
        if valid_jwt and playlist_exists and not correct_owner:
            res = Response(response='', status=403, mimetype="application/json")       
            res.headers.set('Content-Type', 'application/json; charset=utf-8')            
            return res
        #If the JWT is valid but no playlist with this playlist_id exists
        if valid_jwt and not playlist_exists:
            res_body = json.dumps({"Error": "No playlist with this playlist_id exists"})
            res = Response(response=res_body, status=404, mimetype="application/json")         
            res.headers.set('Content-Type', 'application/json; charset=utf-8')  
            return res
            
    elif request.method == 'PUT':
        # Check that the request is JSON 
        content, res = request_validation()
        if res != None:
            return res
            
        #Only the owner of a playlist with a valid JWT should be able to update that playlist
        # If a playlist exists with this playlist_id and the JWT in the request is valid 
        # and the JWT belongs to the playlist's owner, update the playlist and return 204 
        if playlist_exists and valid_jwt and correct_owner:           
            # Check that all required attributes are present in the PATCH request
            if content.get("name") == None or content.get("description") == None or content.get("shuffle") == None:
                # If the request was missing all of the required attributes, return error 400
                res_body = json.dumps({"Error": "The request object is missing at least one of the required attributes"})
                res = Response(response=res_body, status=400, mimetype="application/json")         
                res.headers.set('Content-Type', 'application/json; charset=utf-8')            
                return res
                    
            # Check if the shuffle value is a boolean
            if content.get("shuffle").lower() not in ("true", "false"):
                res_body = json.dumps({"Error": "Valid shuffle values are true and false"})
                res = Response(response=res_body, status=400, mimetype="application/json")         
                res.headers.set('Content-Type', 'application/json; charset=utf-8')   
                return res
            
                    
            # Update the playlist!
            playlist.update({"name": content["name"]})
            playlist.update({"description": content["description"]})
            playlist.update({"shuffle": content["shuffle"]})

            # Persist the entity to Datastore
            client.put(playlist)
            res = Response(response="", status=303, mimetype="application/json")         
            res.headers.set('Content-Type', 'application/json; charset=utf-8')         
            song_self = request.root_url + "playlists/" + str(playlist.key.id)
            res.headers.set('Location', song_self)
            return res

        #Return 401 status code for missing or invalid JWTs.
        if not valid_jwt:
            return ('',401)
        #Return 403 status code:
        #If the JWT is valid but playlist_id is owned by someone else
        if valid_jwt and playlist_exists and not correct_owner:
            res = Response(response='', status=403, mimetype="application/json")       
            res.headers.set('Content-Type', 'application/json; charset=utf-8')            
            return res
        #If the JWT is valid but no playlist with this playlist_id exists
        if valid_jwt and not playlist_exists:
            res_body = json.dumps({"Error": "No playlist with this playlist_id exists"})
            res = Response(response=res_body, status=404, mimetype="application/json")         
            res.headers.set('Content-Type', 'application/json; charset=utf-8')  
            return res

    elif request.method == 'DELETE':
        #Only the owner of a playlist with a valid JWT should be able to delete that playlist
        # If a playlist exists with this playlist_id and the JWT in the request is valid 
        # and the JWT belongs to the playlist's owner, delete the playlist and return 204 
        if playlist_exists and valid_jwt and correct_owner:
            # Update songs that were part of this playlist
            query = client.query(kind=constants.songs)
            results = list(query.fetch())
            for e in results:
                if playlist.key.id in e["playlists"]:
                    e["playlists"].remove(playlist.key.id)
                    e.update({"playlists": e["playlists"]})
                    client.put(e)
            client.delete(playlist_key)
            # TODO update all songs that are part of this playlist
            return ('',204)
        #Return 401 status code for missing or invalid JWTs.
        if not valid_jwt:
            return ('',401)
        #Return 403 status code:
        #If the JWT is valid but playlist_id is owned by someone else
        if valid_jwt and playlist_exists and not correct_owner:
            res = Response(response='', status=403, mimetype="application/json")       
            res.headers.set('Content-Type', 'application/json; charset=utf-8')            
            return res
        #If the JWT is valid but no playlist with this playlist_id exists
        if valid_jwt and not playlist_exists:
            res_body = json.dumps({"Error": "No playlist with this playlist_id exists"})
            res = Response(response=res_body, status=404, mimetype="application/json")         
            res.headers.set('Content-Type', 'application/json; charset=utf-8')  
            return res     
     
    else:
        res_body = json.dumps({"Error": "Invalid method for this endpoint"})
        res = Response(response=res_body, status=405, mimetype="application/json")         
        res.headers.set('Content-Type', 'application/json; charset=utf-8')            
        return res
 
 


@bp.route('/<playlist_id>/songs/<song_id>', methods=['PUT','DELETE'])
def playlists_and_songs(playlist_id, song_id):

    # Does this playlist exist?
    playlist_key = client.key(constants.playlists, int(playlist_id))
    playlist = client.get(key=playlist_key)
    playlist_exists = False if playlist == None else True  
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
    # Does this user own the playlist?
    if playlist_exists and userid == playlist["owner"]:
        correct_owner = True  
      
    # Does this song exist?
    song_key = client.key(constants.songs, int(song_id))
    song = client.get(key=song_key)
    song_exists = False if song == None else True     
    
    if request.method == 'PUT':
        # This endpoint only returns JSON
        res = accept_type_validation(['application/json'])
        if res != None:
            return res
            
        # Does this playlist/song exist, and does this JWT have access to it?
        if playlist_exists and correct_owner and song_exists:
            songs_array = playlist["songs"]
            playlists_array = song["playlists"]
            songs_array.append(song.key.id)
            playlists_array.append(playlist.key.id)

            # Persist to Datastore
            playlist.update({"songs": songs_array})
            song.update({"playlists": playlists_array})
            client.put(playlist)
            client.put(song)
            
            res = Response(response='', status=204, mimetype="application/json")         
            res.headers.set('Content-Type', 'application/json; charset=utf-8')  
            return res
        
        # Handle the case where the user is valid but the playlist or song does not exist
        elif not playlist_exists or not song_exists:
            res_body = json.dumps({"Error": "The specified playlist and/or song does not exist"})
            res = Response(response=res_body, status=404, mimetype="application/json")         
            res.headers.set('Content-Type', 'application/json; charset=utf-8')  
            return res
        else:
            # This JWT doesn't correspond to the playlist owner
            res = Response(response='', status=403, mimetype="application/json")       
            res.headers.set('Content-Type', 'application/json; charset=utf-8')            
            return res
    elif request.method == 'DELETE':
        # This endpoint only returns JSON
        res = accept_type_validation(['application/json'])
        if res != None:
            return res
            
        # Does this playlist/song exist, and does this JWT have access to it?
        if playlist_exists and correct_owner and song_exists:
            songs_array = playlist["songs"]
            playlists_array = song["playlists"]
            # Is this song in this playlist?
            if song.key.id not in songs_array:
                res_body = json.dumps({"Error": "The specified playlist does not contain the specified song"})
                res = Response(response=res_body, status=404, mimetype="application/json")         
                res.headers.set('Content-Type', 'application/json; charset=utf-8')  
                return res
            # If it does, remove it from both the song and playlist attributes
            songs_array.remove(song.key.id)
            playlists_array.remove(playlist.key.id)

            # Persist to Datastore
            playlist.update({"songs": songs_array})
            song.update({"playlists": playlists_array})
            client.put(playlist)
            client.put(song)
            
            res = Response(response='', status=204, mimetype="application/json")         
            res.headers.set('Content-Type', 'application/json; charset=utf-8')  
            return res
        
        # Handle the case where the user is valid but the playlist or song does not exist
        elif not playlist_exists or not song_exists:
            res_body = json.dumps({"Error": "The specified playlist and/or song does not exist"})
            res = Response(response=res_body, status=404, mimetype="application/json")         
            res.headers.set('Content-Type', 'application/json; charset=utf-8')  
            return res
        else:
            # This JWT doesn't correspond to the playlist owner
            res = Response(response='', status=403, mimetype="application/json")       
            res.headers.set('Content-Type', 'application/json; charset=utf-8')            
            return res