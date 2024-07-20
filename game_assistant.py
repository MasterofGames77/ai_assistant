import sys
print(sys.path)
import os
import requests
import logging
from dotenv import load_dotenv
from pymongo import MongoClient
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
mongo_uri = os.getenv("MONGODB_URI")

client = OpenAI(api_key=openai_api_key)

if not all([openai_api_key, rawg_api_key, twitch_client_id, twitch_client_secret, twitch_token_url, mongo_uri]):
    raise ValueError("One or more environment variables are missing or not set correctly")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

mongo_client = MongoClient(mongo_uri)
db = mongo_client["Main"]
user_id_collection = db["user_id"]
questions_collection = db["questions"]

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

print("Token URL:", twitch_token_url)  # This line might be redundant unless you need to confirm the URL


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
    
def fetch_data_from_both_apis(game_name):
    try:
        rawg_data = fetch_games_from_rawg(game_name)
        igdb_data = fetch_igdb_data(game_name)
        
        rawg_response = f"RAWG games related to {game_name}: {[game['name'] for game in rawg_data]}"
        igdb_response = f"IGDB games related to {game_name}: {[game['name'] for game in igdb_data]}"
        
        return f"{rawg_response}\n\n{igdb_response}"
    except Exception as e:
        logging.error(f"Error fetching data from APIs: {e}")
        return "Failed to fetch data due to an error."

if openai_api_key is None:
    raise ValueError("API key not found. Please set the OPENAI_API_KEY environment variable.")

def setup_openai_assistant():
    try:
        assistant = client.beta.assistants.create(
            name="Video Game Analytics Assistant",
            instructions="""
            You are an AI assistant specializing in video games. You can provide detailed analytics and insights into gameplay, helping players track their progress and identify areas for improvement. 
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


import time

def display_assistant_response(thread_id, run_id):
    try:
        # Add a delay to allow the assistant to process
        time.sleep(10)  # Increase the delay to ensure processing time

        messages = client.beta.threads.messages.list(thread_id=thread_id)
        response = None  # Initialize the response variable
        for message in reversed(messages.data):
            if message.role == "assistant":
                for content in message.content:
                    response = content.text.value
                    print(f"Assistant: {response}")
                return response
        logging.info("No response from assistant.")
    except APIError as e:
        logging.error(f"Error retrieving messages: {e}")
    except Exception as e:
        logging.error(f"Unexpected error: {e}")


def get_or_create_user(user_id):
    user = user_id_collection.find_one({"userId": user_id})
    if not user:
        user = {
            "userId": user_id,
            "conversations": []
        }
        user_id_collection.insert_one(user)
    return user

def save_interaction(user_id, question, response):
    interaction = {
        "question": question,
        "response": response,
        "timestamp": datetime.datetime.now()
    }
    user_id_collection.update_one(
        {"userId": user_id},
        {"$push": {"conversations": interaction}},
        upsert=True
    )


def get_previous_interactions(user_id):
    user = user_id_collection.find_one({"userId": user_id})
    if user and "conversations" in user:
        return user["conversations"]
    return []

# Generate recommendations based on previous interactions
def generate_recommendations(previous_interactions):
    recommendations = []
    for interaction in previous_interactions:
        if "Role-Playing Game" in interaction["question"]:
            recommendations.append("Try playing 'Final Fantasy VII'")
        if "Action-Adventure" in interaction["question"]:
            recommendations.append("Try playing 'The Legend of Zelda: Breath of the Wild'")
        if "Hack and Slash" in interaction["question"]:
            recommendations.append("You might enjoy 'Devil May Cry 3'")
        if "Action RPG" in interaction["question"]:
            recommendations.append("Try playing 'Xenoblade Chronicles'")
        if "Battle Royale" in interaction["question"]:
            recommendations.append("Try playing 'Fortnite'")
        if "Platformer" in interaction["question"]:
            recommendations.append("Try playing 'Super Mario 64'")
        if "Survival Horror" in interaction["question"]:
            recommendations.append("Try playing 'Resident Evil 4'")
        if "Third-Person Shooter" in interaction["question"]:
            recommendations.append("Try playing 'Splatoon 3'")
        if "Metroidvania" in interaction["question"]:
            recommendations.append("Try playing 'Castlevania: Symphony of the Night'")
        if "First-Person Shooter" in interaction["question"]:
            recommendations.append("Try playing 'Bioshock Infinite'")
        if "Sandbox" in interaction["question"]:
            recommendations.append("Try playing 'Minecraft'")
        if "Roguelike" in interaction["question"]:
            recommendations.append("Try playing 'Hades'")
        if "Action-Adventure" in interaction["question"]:
            recommendations.append("Try playing 'The Last of Us'")
        if "Social Simulation" in interaction["question"]:
            recommendations.append("Try playing 'Animal Crossing: New Horizons'")
        if "Massively Multiplayer Online Role-Playing Game" in interaction["question"]:
            recommendations.append("Try playing 'World of Warcraft'")
        if "Multiplayer Online Battle Arena" in interaction["question"]:
            recommendations.append("Try playing 'Dota 2'")
        if "Puzzle-Platformer" in interaction["question"]:
            recommendations.append("Try playing 'Portal'")
        if "Fighting Game" in interaction["question"]:
            recommendations.append("Try playing 'Super Smash Bros. Ultimate'")
        if "Tactical Role-Playing Game" in interaction["question"]:
            recommendations.append("Try playing 'Fire Emblem: Awakening'")
        if "Tower Defense" in interaction["question"]:
            recommendations.append("Try playing 'Bloons TD 6'")
        if "Racing" in interaction["question"]:
            recommendations.append("Try playing 'Forza Horizon 5'")
        if "Kart Racing" in interaction["question"]:
            recommendations.append("Try playing 'Mario Kart 8 Deluxe'")
        if "Rail Shooter" in interaction["question"]:
            recommendations.append("Try playing 'Star Fox 64'")
        if "Stealth" in interaction["question"]:
            recommendations.append("Try playing 'Metal Gear Solid'")
        if "Run and Gun" in interaction["question"]:
            recommendations.append("Try playing 'Cuphead'")
        if "Turn-Based Strategy" in interaction["question"]:
            recommendations.append("Try playing 'Advance Wars'")
        if "4X" in interaction["question"]:
            recommendations.append("Try playing 'Sid Meier's Civilization VI'")
        if "Sports" in interaction["question"]:
            recommendations.append("Try playing 'Fifa 18'")
        if "Party" in interaction["question"]:
            recommendations.append("Try playing 'Mario Party Superstars'")
        if "Rhythm" in interaction["question"]:
            recommendations.append("Try playing 'Rock Band'")
        if "Point and Click" in interaction["question"]:
            recommendations.append("Try playing 'Five Night's at Freddy's'")
        if "Visual Novel" in interaction["question"]:
            recommendations.append("Try playing 'Phoenix Wright: Ace Attorney'")
        if "Real Time Strategy" in interaction["question"]:
            recommendations.append("Try playing 'Command & Conquer'")
        if "Beat 'em up" in interaction["question"]:
            recommendations.append("Try playing 'Streets of Rage 4'")
        if "Puzzle" in interaction["question"]:
            recommendations.append("Try playing 'Tetris'")
        if "Turn-Based Tactics" in interaction["question"]:
            recommendations.append("Try playing 'XCOM: Enemy Unknown'")
        if "Interactive Story" in interaction["question"]:
            recommendations.append("Try playing 'The Stanley Parable'")
        if "Maze" in interaction["question"]:
            recommendations.append("Try playing 'Pac-Man'")
        if "Game Creation System" in interaction["question"]:
            recommendations.append("Try playing 'Roblox'")
        if "Level Editor" in interaction["question"]:
            recommendations.append("Try playing 'Super Mario Maker'")
        if "Endless Runner" in interaction["question"]:
            recommendations.append("Try playing 'Temple Run'")
        if "Digitable Collectible Card Game" in interaction["question"]:
            recommendations.append("Try playing 'Yu-Gi-Oh! Master Duel'")
        if "Exergaming" in interaction["question"]:
            recommendations.append("Try playing 'Wii Fit'")
        if "Immersive Sim" in interaction["question"]:
            recommendations.append("Try playing 'Deathloop'")
        if "Tile-Matching" in interaction["question"]:
            recommendations.append("Try playing 'Bejeweled'")
        if "Text Based" in interaction["question"]:
            recommendations.append("Try playing 'The Oregon Trail'")
    return recommendations


def main():
    try:
        assistant = setup_openai_assistant()
        if assistant is None:
            raise Exception("Assistant could not be created.")

        user_id = input("Enter your user ID: ")
        question = input("Enter your gameplay data or question for analysis: ")

        # Get or create user in MongoDB
        user = get_or_create_user(user_id)
        
        thread = create_thread()
        if thread:
            if "similar to" in question.lower():
                game_name = question.split("similar to ")[1].strip()
                response = fetch_data_from_both_apis(game_name)
                print(response)
            else:
                message = add_message_to_thread(thread.id, question)
                if message:
                    run = run_assistant(thread.id, assistant.id)
                    if run:
                        response = display_assistant_response(thread.id, run.id)  # Fetch response
                        if response:
                            # Save interaction in MongoDB
                            save_interaction(user_id, question, response)
                    else:
                        logging.error("Failed to run assistant")
                else:
                    logging.error("Failed to add message to thread")
        else:
            logging.error("Failed to create thread")

        # Retrieve and analyze previous interactions
        previous_interactions = get_previous_interactions(user_id)
        recommendations = generate_recommendations(previous_interactions)
        print("Recommendations based on your previous interactions: ", recommendations)

    except Exception as e:
        logging.error(f"An error occurred in the main function: {e}")

if __name__ == "__main__":
    main()