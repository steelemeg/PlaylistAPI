import os
# Using Google OAuth as my JWT provider and to obtain user information.
# Based largely on https://requests-oauthlib.readthedocs.io/en/latest/examples/google.html
from requests_oauthlib import OAuth2Session
from google.auth import crypt
from google.auth import jwt
from google.oauth2 import id_token
from google.auth.transport import requests
from google.auth import crypt
from google.auth import jwt

app = Flask(__name__)
app.register_blueprint(songs.bp)
app.register_blueprint(playlists.bp)
app.register_blueprint(owners.bp)
app.state = ''

# We don't require as much user information for this project
app.scope = ['openid']
app.google = OAuth2Session(constants.client_id, scope=app.scope, redirect_uri=constants.redirect_url)
    
@app.route('/', methods=['GET'])
def welcome():
    # Prepare the link to Google authentication and store the state
    auth_url, app.state = app.google.authorization_url(constants.auth_url,access_type="offline", prompt="select_account")

    return render_template('index.html', state = app.state, authorization_url = auth_url) 


@app.route('/oauth', methods=['POST','GET'])
def oauth():
    access_token = ''
    try:
        access_token = app.google.fetch_token(constants.token_url, client_secret=constants.client_secret, authorization_response=request.url)
    except:
        # In testing, got the occasional state mismatch error when I did not reload properly.
        res_body = json.dumps({"Error": "State mismatch. This may be due to a cache error. Please clear your browser cache and try again."})
        res = Response(response=res_body, status=404)         
        return res       
    
    # https://developers.google.com/identity/sign-in/web/backend-auth
    try:
        idinfo = id_token.verify_oauth2_token(access_token['id_token'], requests.Request(), constants.client_id)
        userid = idinfo['sub']
    except ValueError:
        res_body = json.dumps({"Error": "Invalid token"})
        res = Response(response=res_body, status=401)         
        return res
    # Per https://dev.to/kimmaida/signing-and-validating-json-web-tokens-jwt-for-everyone-25fb 
    # the JWT itself is supposed to be pretty big (800+ characters)
    return render_template('userinfo.html', jwt = access_token['id_token'])

  
if __name__ == '__main__':
    # For local testing only. 
    # https://oauthlib.readthedocs.io/en/latest/oauth2/security.html
    os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
    app.run(host='127.0.0.1', port=8080, debug=True)