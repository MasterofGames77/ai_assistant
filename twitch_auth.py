import datetime
import logging
import os
import requests
from dotenv import load_dotenv

# Load environment variables from the .env file
load_dotenv()

# Retrieve environment variables for Twitch API credentials and URLs
TWITCH_CLIENT_ID = os.getenv("NEXT_PUBLIC_TWITCH_CLIENT_ID")
TWITCH_CLIENT_SECRET = os.getenv("TWITCH_CLIENT_SECRET")
TWITCH_REDIRECT_URI = os.getenv("TWITCH_REDIRECT_URI")
TWITCH_TOKEN_URL = os.getenv("TWITCH_TOKEN_URL")

# Variables to store the access token and its expiration time
cached_access_token = None
token_expiry_time = None

# Function to get a client credentials access token from Twitch
def get_client_credentials_access_token():
    global cached_access_token, token_expiry_time
    
    # Check if we have a cached token that hasn't expired
    if cached_access_token and token_expiry_time and token_expiry_time > datetime.datetime.now():
        return cached_access_token
    
    logging.info("Fetching new access token")

    # Parameters for the token request
    params = {
        'client_id': TWITCH_CLIENT_ID,
        'client_secret': TWITCH_CLIENT_SECRET,
        'grant_type': 'client_credentials'
    }

    # Make the POST request to Twitch to get a new access token
    response = requests.post(TWITCH_TOKEN_URL, data=params)
    response.raise_for_status()  # Raise an error for any unsuccessful request
    token_data = response.json()

    # Cache the new token and calculate its expiration time
    cached_access_token = token_data['access_token']
    token_expiry_time = datetime.datetime.now() + datetime.timedelta(seconds=token_data['expires_in'])

    logging.info(f"New access token fetched: {cached_access_token}")
    logging.info(f"Token expires at: {token_expiry_time}")

    return cached_access_token

# Function to get user data from Twitch using the access token
def get_twitch_user_data(access_token):
    # Headers for the Twitch API request
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Client-Id': TWITCH_CLIENT_ID
    }
    
    # Make the GET request to fetch the user data from Twitch
    response = requests.get('https://api.twitch.tv/helix/users', headers=headers)
    if response.status_code == 200:
        return response.json()
    else:
        raise Exception("Failed to retrieve user data")