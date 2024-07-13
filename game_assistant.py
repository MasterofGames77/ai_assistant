# %%
import sys
print(sys.path)

# %%
import os
import requests
import logging
from dotenv import load_dotenv
from openai import OpenAI
import datetime

# Load environment variables
load_dotenv()

# Retrieve environment variables
openai_api_key = os.getenv("OPENAI_API_KEY")
rawg_api_key = os.getenv("RAWG_API_KEY")
twitch_client_id = os.getenv("TWITCH_CLIENT_ID")
twitch_client_secret = os.getenv("TWITCH_CLIENT_SECRET")
twitch_token_url = os.getenv("TWITCH_TOKEN_URL")

client = OpenAI(api_key=openai_api_key)

# %% [markdown]
# Ensure Variables are Loaded Correctly

# %%
if not all([openai_api_key, rawg_api_key, twitch_client_id, twitch_client_secret, twitch_token_url]):
    raise ValueError("One or more environment variables are missing or not set correctly")

# %%
# Configure Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# %% [markdown]
# Get Access Token

# %%
import time
import datetime

token_info = {"access_token": None, "expires_at": None}

def get_access_token():
    """ Fetch access token using Twitch credentials. """
    data = {
        'client_id': twitch_client_id,
        'client_secret': twitch_client_secret,
        'grant_type': 'client_credentials'
    }
    response = requests.post(twitch_token_url, data=data)
    response.raise_for_status()
    token_data = response.json()
    expires_in = token_data['expires_in']
    token_info['access_token'] = token_data['access_token']
    token_info['expires_at'] = datetime.datetime.now() + datetime.timedelta(seconds=expires_in)
    logging.info("New access token fetched and stored.")

def check_token():
    """ Check if the token is expired and refresh it if needed. """
    if token_info['expires_at'] is None or token_info['expires_at'] <= datetime.datetime.now():
        logging.info("Token has expired, fetching a new one...")
        get_access_token()
    else:
        logging.info("Token is still valid.")

# Example usage
try:
    # Always check the token before making a request
    check_token()
    access_token = token_info['access_token']
    if access_token:
        print(f"Using access token: {access_token}")
        # Proceed with using the access token for API requests
    else:
        print("Failed to obtain access token.")
except Exception as e:
    print(f"Error obtaining or using access token: {e}")

print("Token URL:", twitch_token_url)

# %% [markdown]
# Make a Request to IGDB API

# %%
def fetch_igdb_data(access_token, client_id):
    headers = {
        'Client-ID': client_id,
        'Authorization': f'Bearer {access_token}',
    }
    response = requests.post(
        'https://api.igdb.com/v4/games',
        headers=headers,
        data='fields name,genres.name,platforms.name,release_dates.human; limit 10;'
    )
    if response.status_code == 200:
        return response.json()
    else:
        raise Exception(f"Failed to fetch data: {response.status_code}, {response.text}")

# Fetch IGDB data
try:
    games_data = fetch_igdb_data(access_token, twitch_client_id)
    for game in games_data:
        print(game)
except Exception as e:
    logging.error(f"Error fetching IGDB data: {e}")

# %% [markdown]
# Fetch Game Data from RAWG API
def fetch_games_from_rawg(search_query):
    """Fetch games based on a search query from RAWG."""
    # Fetch the RAWG API key directly from environment variables within the function
    rawg_api_key = os.getenv("RAWG_API_KEY")
    # Construct the URL with the API key and the search query properly included
    url = f"https://api.rawg.io/api/games?key={rawg_api_key}&search={search_query}"
    # Use a GET request to fetch data
    response = requests.get(url)
    # Check the response status and handle accordingly
    if response.status_code == 200:
        return response.json()['results']  # Make sure to return the results part of the JSON
    else:
        raise Exception(f"Failed to fetch data: {response.status_code}, {response.text}")

# %% [markdown]
# Check if API Key is loaded

# %%
if openai_api_key is None:
    raise ValueError("API key not found. Please set the OPENAI_API_KEY environment variable.")

# %% [markdown]
# AI Game Analytics 

# %%
def setup_openai_assistant():
    try:
        assistant = client.beta.assistants.create(
            name="Video Game Analytics Assistant",
            instructions="""
            You are an AI assistant specializing in video game. You can provide detailed analytics and insights into gameplay, helping players track their progress and identify areas for improvement. 
            You can answer questions about game completion times, strategies to progress past difficult sections, fastest speedrun times, and general tips and tricks.
            For example:
            - "How long would it take to fully complete Super Mario Bros. on NES?"
            - "How do I progress past the Water Temple in The Legend of Zelda: Ocarina of Time?"
            - "What is the fastest speedrun time for Sonic the Hedgehog?"
            - "Give me tips and tricks to improve my gameplay in Fortnite."
            - "Give me a guide on how to clear Chapter 3 in Paper Mario: The Thousand Year Door."
            - "What is the best strategy for completing Shrines in The Legend of Zelda: Breath of the Wild?"
            - "What games in terms of genre are similar to Super Metroid?"
            - "What games could you recommend to someone who is playing a Role-Playing Game for the first time?"
            - "What types of games are you familiar with?"
            Use up-to-date information and provide the best possible answers to enhance the user's gaming experience.
            """,
            tools=[{"type": "code_interpreter"}],  # Add more tools if needed
            model="gpt-4o"
)
        return assistant
    except Exception as e:
        logging.error(f"Failed to create assistant: {e}")
        return None

# %% [markdown]
# Create a Thred

# %%
from openai import APIError

def create_thread():
    try:
        thread = client.beta.threads.create()
        logging.info(f"Thread created: {thread}")
        return thread
    except APIError as e:
        logging.error(f"Error creating thread: {e}")
        return None
    except Exception as e:
        logging.error(f"Unexpected error: {e}")
        return None

# %% [markdown]
# Add a Message to a Thread

# %%
def add_message_to_thread(thread_id, message_content):
    try:
        message = client.beta.threads.messages.create(
            thread_id=thread_id,
            role="user",
            content=message_content
        )
        logging.info(f"Message added to thread: {message}")
        return message
    except APIError as e:
        logging.error(f"Error adding message to thread: {e}")
        return None
    except Exception as e:
        logging.error(f"Unexpected error: {e}")
        return None

# %% [markdown]
# Run the Assistant

# %%
def run_assistant(thread_id, assistant_id):
    try:
        run = client.beta.threads.runs.create(
            thread_id=thread_id,
            assistant_id=assistant_id
        )
        logging.info(f"Run created: {run}")
        return run
    except APIError as e:
        logging.error(f"Error running assistant: {e}")
        return None
    except Exception as e:
        logging.error(f"Unexpected error: {e}")
        return None

# %% [markdown]
# Retreive and Display the Assistant's Response

# %%
import time

def display_assistant_response(thread_id, run):
    try:
        # Add a delay to allow the assistant to process
        time.sleep(10)  # Increase the delay to ensure processing time

        messages = client.beta.threads.messages.list(thread_id=thread_id)
        for message in reversed(messages.data):
            if message.role == "assistant":
                for content in message.content:
                    print(f"Assistant: {content.text.value}")
                return
        logging.info("No response from assistant.")
    except APIError as e:
        logging.error(f"Error retrieving messages: {e}")
    except Exception as e:
        logging.error(f"Unexpected error: {e}")

# %% [markdown]
# Generate Response:

# %%
def main():
    try:
        assistant = setup_openai_assistant()
        if assistant is None:
            raise Exception("Assistant could not be created.")

        thread = create_thread()
        if thread:
            user_input = input("Enter your gameplay data or question for analysis: ")
            if "similar to" in user_input.lower():
                game_name = user_input.split("similar to ")[1]
                similar_games = fetch_games_from_rawg(game_name)
                if similar_games:
                    print(f"Games similar to {game_name}: {[game['name'] for game in similar_games]}")
                else:
                    print("No similar games found.")
            else:
                message = add_message_to_thread(thread.id, user_input)
                if message:
                    run = run_assistant(thread.id, assistant.id)
                    if run:
                        display_assistant_response(thread.id, run.id)
                else:
                    logging.error("Failed to add message to thread")
        else:
            logging.error("Failed to create thread")
    except Exception as e:
        logging.error(f"An error occurred in the main function: {e}")

if __name__ == "__main__":
    main()