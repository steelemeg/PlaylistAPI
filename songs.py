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

def song_length(seconds):
    # Checks if the song length is a number and imposes an 
    # arbitrary length restriction of 2^20 seconds
    if not isinstance(seconds, int):
        res_body = json.dumps({"Error": "Valid song lengths are between 1 and 1048576"})
        res = Response(response=res_body, status=400, mimetype="application/json")         
        res.headers.set('Content-Type', 'application/json; charset=utf-8')            
        return res
    if seconds < 1 or seconds > 1048576:
        res_body = json.dumps({"Error": "Valid song lengths are between 1 and 1048576"})
        res = Response(response=res_body, status=400, mimetype="application/json")         
        res.headers.set('Content-Type', 'application/json; charset=utf-8')            
        return res

@bp.route('', methods=['POST','GET','DELETE','PUT','PATCH'])
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

        # Check that all required attributes are present in the POST request
        # Validation is not required!
        if content.get("name") == None or content.get("artist") == None or content.get("length") == None :
            # If the request was missing any of the required attributes, return error 400
            res_body = json.dumps({"Error": "The request object is missing at least one of the required attributes"})
            res = Response(response=res_body, status=400, mimetype="application/json")         
            res.headers.set('Content-Type', 'application/json; charset=utf-8')            
            return res
       
        # Check that a valid length was provided
        res = song_length(content.get("length"))
        if res != None:
            return res
            
        # If the required attributes were present, make a new song!
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
        all_songs = get_things("songs", True, None)
        return all_songs

    else:
        # Use status code 405 for PUT, PATCH, or DELETE requests on the root songs URL
        res_body = json.dumps({"Error": "Invalid method for this endpoint"})
        res = Response(response=res_body, status=405, mimetype="application/json")         
        res.headers.set('Content-Type', 'application/json; charset=utf-8')            
        return res

    
@bp.route('/<id>', methods=['GET','DELETE','PUT','PATCH','POST'])
def songs_by_id(id):
    song_key = client.key(constants.songs, int(id))
    song = client.get(key=song_key)
    song_exists = False if song == None else True     
    # Does this song exist?
    if not song_exists:
        res_body = json.dumps({"Error": "No song with this song_id exists"})
        res = Response(response=res_body, status=404, mimetype="application/json")         
        res.headers.set('Content-Type', 'application/json; charset=utf-8')  
        return res
        
    if request.method == 'GET':
        # This endpoint only returns JSON
        res = accept_type_validation(['application/json'])
        if res != None:
            return res

        if song_exists:
            res_body = json.dumps({
                "id": song.key.id, 
                "name": song["name"], 
                "artist": song["artist"],
                "album": song["album"],
                "length": song["length"],
                "playlists": song["playlists"],
                "self": request.root_url + "songs/" + str(song.key.id)})
            res = Response(response=res_body, status=200, mimetype="application/json")         
            res.headers.set('Content-Type', 'application/json; charset=utf-8')    
            return res 
        
    elif request.method == 'DELETE':
        if song_exists:
            # Update playlists that contained this song
            query = client.query(kind=constants.playlists)
            results = list(query.fetch())
            for e in results:
                if song.key.id in e["songs"]:
                    e["songs"].remove(song.key.id)
                    e.update({"songs": e["songs"]})
                    client.put(e)
            client.delete(song_key)
            return ('',204)
        
    
    elif request.method == 'PATCH':
        # Check that the request is JSON 
        content, res = request_validation()
        if res != None:
            return res
        # This endpoint only returns JSON
        res = accept_type_validation(['application/json'])
        if res != None:
            return res
        
        # Check that at least one required attributes are present in the PATCH request
        elif content.get("name") == None and content.get("artist") == None and content.get("album") == None and content.get("length") == None:
            # If the request was missing all of the required attributes, return error 400
            res_body = json.dumps({"Error": "The request object is missing any recognized attributes"})
            res = Response(response=res_body, status=400, mimetype="application/json")         
            res.headers.set('Content-Type', 'application/json; charset=utf-8')            
            return res

        # If a length was provided, validate it.
        elif content.get("length") != None:
            res = song_length(content.get("length"))
            if res != None:
                return res
                
        # Update the song!
        if content.get("name") != None:
            song.update({"name": content["name"]})
        if content.get("artist") != None:
            song.update({"artist": content["artist"]})
        if content.get("album") != None:
            song.update({"album": content["album"]})
        if content.get("length") != None:
            song.update({"length": content["length"]})
        # Persist the entity to Datastore
        client.put(song)
        res_body = json.dumps({
            "id": song.key.id, 
            "name": song["name"], 
            "artist": song["artist"],
            "album": song["album"],
            "length": song["length"],
            "playlists": song["playlists"],
            "self": request.root_url + "songs/" + str(song.key.id)})

        res = Response(response=res_body, status=200, mimetype="application/json")         
        res.headers.set('Content-Type', 'application/json; charset=utf-8')
        return res
    
    elif request.method == 'PUT':
        # Check that the request is JSON 
        content, res = request_validation()
        if res != None:
            return res
        
        # Check that at required attributes are present in the PUT request
        elif content.get("name") == None or content.get("artist") == None or content.get("length") == None:
            # If the request was missing any of the required attributes, return error 400
            res_body = json.dumps({"Error": "The request object is missing at least one of the required attributes"})
            res = Response(response=res_body, status=400, mimetype="application/json")         
            res.headers.set('Content-Type', 'application/json; charset=utf-8')            
            return res

        res = song_length(content.get("length"))
        if res != None:
            return res
                
        # Update the song!
        song.update({"name": content["name"]})
        song.update({"artist": content["artist"]})
        if content.get("album") != None:
            song.update({"album": content["album"]})
        song.update({"length": content["length"]})
        # Persist the entity to Datastore
        client.put(song)
        res = Response(response="", status=303, mimetype="application/json")         
        res.headers.set('Content-Type', 'application/json; charset=utf-8')         
        song_self = request.root_url + "songs/" + str(song.key.id)
        res.headers.set('Location', song_self)
        return res
    
    else:
        # Use status code 405 for POST requests on the song ID
        # And presumably any other verb, which would be invalid and caught differently by Flask.
        print("check")
        res_body = json.dumps({"Error": "Invalid method for this endpoint"})
        res = Response(response=res_body, status=405, mimetype="application/json")         
        res.headers.set('Content-Type', 'application/json; charset=utf-8')            
        return res
 