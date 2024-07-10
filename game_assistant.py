# %%
import sys
print(sys.path)

# %%
from dotenv import load_dotenv
import os
import requests
import logging
from openai import OpenAI

# Load environment variables
load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=api_key)

twitch_client_id = os.getenv("TWITCH_CLIENT_ID")
twitch_client_secret = os.getenv("TWITCH_CLIENT_SECRET")
twitch_token_url = "https://id.twitch.tv/oauth2/token"

# %% [markdown]
# Ensure Variables are Loaded Correctly

# %%
if not all([api_key, twitch_client_id, twitch_client_secret, twitch_token_url]):
    raise ValueError("One or more environment variables are missing or not set correctly")

# %% [markdown]
# Configure Logging

# %%
# Configure Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# %% [markdown]
# Get Access Token

# %%
def get_access_token(client_id, client_secret, token_url):
    params = {
        'client_id': client_id,
        'client_secret': client_secret,
        'grant_type': 'client_credentials'
    }
    try:
        response = requests.post(token_url, params=params)
        response.raise_for_status()  # Raise an exception for bad status codes
        return response.json().get('access_token')
    except requests.exceptions.HTTPError as http_err:
        logging.error(f"HTTP error occurred: {http_err}")
        raise
    except Exception as err:
        logging.error(f"Other error occurred: {err}")
        raise

# Example usage to get the access token
try:
    access_token = get_access_token(twitch_client_id, twitch_client_secret, twitch_token_url)
    logging.info(f"Access token obtained: {access_token}")
except Exception as e:
    logging.error(f"Error obtaining access token: {e}")
    raise

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
# Check if API Key is loaded

# %%
if api_key is None:
    raise ValueError("API key not found. Please set the OPENAI_API_KEY environment variable.")

# %% [markdown]
# AI Game Analytics 

# %%
assistant = client.beta.assistants.create(
    name="Video Game Expert",
    instructions="""
    You are an AI assistant specializing in video games. You can provide detailed analytics and insights into gameplay, helping players track their progress and identify areas for improvement. 
    You can answer questions about game completion times, strategies to progress past difficult sections, fastest speedrun times, and general tips and tricks.
    For example:
    - "How long would it take to fully complete Super Mario Bros. on NES?"
    - "How do I progress past the Water Temple in The Legend of Zelda: Ocarina of Time?"
    - "What is the fastest speedrun time for Sonic the Hedgehog?"
    - "Give me tips and tricks to improve my gameplay in Fortnite."
    Use up-to-date information and provide the best possible answers to enhance the user's gaming experience.
    """,
    tools=[{"type": "code_interpreter"}],  # Add more tools if needed
    model="gpt-4o"
)

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
# Example:

# %%
def main():
    thread = create_thread()
    if thread:
        user_input = input("Enter your gameplay data or question for analysis: ")
        message = add_message_to_thread(thread.id, user_input)
        if message:
            run = run_assistant(thread.id, assistant.id)
            if run:
                display_assistant_response(thread.id, run.id)

# Run the main function
if __name__ == "__main__":
    main()