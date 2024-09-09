import os
import logging
from dotenv import load_dotenv
from pymongo import MongoClient
from openai import OpenAI
import pandas as pd
from twitch_auth import get_client_credentials_access_token
from game_api_helper import fetch_from_igdb, fetch_from_rawg
from csv_helper import read_csv_file, format_game_info

# Load environment variables
load_dotenv()

# Retrieve environment variables
openai_api_key = os.getenv("OPENAI_API_KEY")
rawg_api_key = os.getenv("RAWG_API_KEY")
next_public_twitch_client_id = os.getenv("NEXT_PUBLIC_TWITCH_CLIENT_ID")
twitch_client_secret = os.getenv("TWITCH_CLIENT_SECRET")
twitch_token_url = os.getenv("TWITCH_TOKEN_URL")
mongo_uri = os.getenv("MONGODB_URI")

client = OpenAI(api_key=openai_api_key)

# Ensure environment variables are loaded correctly
if not all([openai_api_key, rawg_api_key, next_public_twitch_client_id, twitch_client_secret, twitch_token_url, mongo_uri]):
    raise ValueError("One or more environment variables are missing or not set correctly")

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Connect to MongoDB
mongo_client = MongoClient(mongo_uri)
db = mongo_client["Wingman"]
user_id_collection = db["userID"]
questions_collection = db["question"]

# Load the CSV files
video_games_df = read_csv_file('data/Video Games Data.csv')
data_dictionary_df = read_csv_file('data/vg_data_dictionary.csv')

# Search games by genre
def search_games_by_genre(genre):
    results = video_games_df[video_games_df['Genre'].str.contains(genre, case=False, na=False)]
    return results

# Search games by name
def search_game_by_name(game_name):
    results = video_games_df[video_games_df['title'].str.contains(game_name, case=False)]
    return results

# Fetch data from IGDB, RAWG, and CSV files
def fetch_data_from_all_sources(game_name):
    try:
        access_token = get_client_credentials_access_token()
        
        igdb_data = fetch_from_igdb(game_name, access_token)
        rawg_data = fetch_from_rawg(game_name)
        
        csv_game_info = video_games_df[video_games_df['title'].str.lower() == game_name.lower()]
        csv_info = format_game_info(csv_game_info.iloc[0]) if not csv_game_info.empty else None
        
        combined_response = ""
        
        if igdb_data:
            combined_response += f"IGDB Data:\n{igdb_data}\n"
        
        if rawg_data:
            combined_response += f"RAWG Data:\n{rawg_data}\n"
        
        if csv_info:
            combined_response += f"CSV Data:\n{csv_info}\n"
        
        if not combined_response.strip():
            combined_response = "No relevant game information found in any database."
        
        return combined_response
    
    except Exception as e:
        logging.error(f"Error fetching data from APIs: {e}")
        return "Failed to fetch data due to an error."

# Check if API key is loaded
if openai_api_key is None:
    raise ValueError("API key not found. Please set the OPENAI_API_KEY environment variable.")

# AI Assistant (Video Game Wingman)
def setup_openai_assistant():
    try:
        assistant = client.beta.assistants.create(
            name="Video Game Wingman",
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
            -" What are some of the biggest challenges impacting the Global Video Game Industry?
            Use up-to-date information and provide the best possible answers to enhance the user's gaming experience.
            """,
            tools=[{"type": "code_interpreter"}],
            model="gpt-4o"
        )
        return assistant
    except Exception as e:
        logging.error(f"Failed to create assistant: {e}")
        return None

# Create a thread
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

# Add a message to a thread
def add_message_to_thread(thread_id, message_content):
    try:
        message = client.beta.threads.messages.create(
            thread_id=thread_id,
            role="user",
            content=message_content
        )
        logging.info(f"Message added to thread: {message}")
        return message
    except Exception as e:
        logging.error(f"Error adding message to thread: {e}")
        return None

# Run the assistant
def run_assistant(thread_id, assistant_id):
    try:
        run = client.beta.threads.runs.create(
            thread_id=thread_id,
            assistant_id=assistant_id
        )
        logging.info(f"Run created: {run}")
        return run
    except Exception as e:
        logging.error(f"Error running assistant: {e}")
        return None

# Retrieve and display the assistant's response
import time

def display_assistant_response(thread_id, run_id):
    try:
        logging.info(f"Processing response for thread_id: {thread_id} and run_id: {run_id}")
        time.sleep(15)
        messages = client.beta.threads.messages.list(thread_id=thread_id)
        for message in reversed(messages.data):
            if message.role == "assistant":
                logging.info(f"Full Assistant Message: {message}")
                if message.content and message.content[0].text and message.content[0].text.value:
                    response = message.content[0].text.value
                    logging.info(f"Assistant: {response}")
                    return response
                else:
                    logging.info("Assistant message does not have the expected content format.")
        logging.info("No response from assistant.")
    except Exception as e:
        logging.error(f"Error retrieving messages: {e}")

# Get or create user in MongoDB
def get_or_create_user(user_id):
    user = user_id_collection.find_one({"userId": user_id})
    if not user:
        user = {
            "userId": user_id,
            "conversations": []
        }
        user_id_collection.insert_one(user)
    return user

# Save interaction in MongoDB
import datetime

def save_interaction(user_id, question, response):
    interaction = {
        "userId": user_id,
        "question": question,
        "response": response,
        "timestamp": datetime.datetime.now()
    }
    questions_collection.insert_one(interaction)
    user_id_collection.update_one(
        {"userId": user_id},
        {"$push": {"conversations": interaction}},
        upsert=True
    )

# Retrieve and analyze previous interactions
import re

def get_previous_interactions(user_id):
    user = user_id_collection.find_one({"userId": user_id})
    if user and "conversations" in user:
        return user["conversations"]
    return []

# Generate recommendations based on previous interactions
def generate_recommendations(previous_interactions):
    recommendations = []
    keywords = {
        "role-playing game": "Try playing 'Final Fantasy VII'",
        "rpg": "Try playing 'Paper Mario: The Thousand-Year Door'",
        "action-adventure": "Try playing 'The Elder Scrolls V: Skyrim'",
        "hack and slash": "You might enjoy 'Devil May Cry 3'",
        "action rpg": "Try playing 'Xenoblade Chronicles'",
        "battle royale": "Try playing 'Fortnite'",
        "platformer": "Try playing 'Super Mario 64'",
        "survival horror": "Try playing 'Resident Evil 4'",
        "third-person shooter": "Try playing 'Splatoon 3'",
        "metroidvania": "Try playing 'Castlevania: Symphony of the Night'",
        "first-person shooter": "Try playing 'Bioshock Infinite'",
        "sandbox": "Try playing 'Minecraft'",
        "roguelike": "Try playing 'Hades'",
        "social simulation": "Try playing 'Animal Crossing: New Horizons'",
        "mmo": "Try playing 'Runescape'",
        "massively multiplayer online role-playing game": "Try playing 'World of Warcraft'",
        "moba": "Try playing 'League of Legends'",
        "multiplayer online battle arena": "Try playing 'Dota 2'",
        "puzzle-platformer": "Try playing 'Portal'",
        "fighting game": "Try playing 'Super Smash Bros. Ultimate'",
        "tactical role-playing game": "Try playing 'Fire Emblem: Awakening'",
        "tower defense": "Try playing 'Bloons TD 6'",
        "racing": "Try playing 'Forza Horizon 5'",
        "kart racing": "Try playing 'Mario Kart 8 Deluxe'",
        "rail shooter": "Try playing 'Star Fox 64'",
        "stealth": "Try playing 'Metal Gear Solid'",
        "run and gun": "Try playing 'Cuphead'",
        "turn-based strategy": "Try playing 'Advance Wars'",
        "4x": "Try playing 'Sid Meier's Civilization VI'",
        "sports": "Try playing 'Wii Sports'",
        "party": "Try playing 'Mario Party Superstars'",
        "rhythm": "Try playing 'Rock Band'",
        "point and click": "Try playing 'Five Night's at Freddy's'",
        "visual novel": "Try playing 'Phoenix Wright: Ace Attorney'",
        "real-time strategy": "Try playing 'Command & Conquer'",
        "beat 'em up": "Try playing 'Streets of Rage 4'",
        "puzzle": "Try playing 'Tetris'",
        "turn-based tactics": "Try playing 'XCOM: Enemy Unknown'",
        "interactive story": "Try playing 'The Stanley Parable'",
        "maze": "Try playing 'Pac-Man'",
        "game creation system": "Try playing 'Roblox'",
        "level editor": "Try playing 'Super Mario Maker'",
        "endless runner": "Try playing 'Temple Run'",
        "digital collectible card game": "Try playing 'Yu-Gi-Oh! Master Duel'",
        "exergaming": "Try playing 'Wii Fit'",
        "immersive sim": "Try playing 'Deathloop'",
        "tile-matching": "Try playing 'Bejeweled'",
        "text based": "Try playing 'The Oregon Trail'",
        "augmented reality": "Try playing 'Pokémon Go'",
        "action-adventure": "Try playing 'The Last of Us'"
    }

    for interaction in previous_interactions:
        for keyword, recommendation in keywords.items():
            if re.search(keyword, interaction["question"], re.IGNORECASE):
                if recommendation not in recommendations:
                    recommendations.append(recommendation)
    
    return recommendations

# Generate response
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
                response = fetch_data_from_all_sources(game_name)
                print(response)
                save_interaction(user_id, question, response)
            elif "genre" in question.lower():
                genre = question.split("genre ")[1].strip()
                response = fetch_data_from_all_sources(genre)
                print(response)
                save_interaction(user_id, question, response)
            else:
                message = add_message_to_thread(thread.id, question)
                if message:
                    run = run_assistant(thread.id, assistant.id)
                    if run:
                        response = display_assistant_response(thread.id, run.id)
                        if response:
                            save_interaction(user_id, question, response)
                        else:
                            response = fetch_data_from_all_sources(question)
                            print(response)
                            save_interaction(user_id, question, response)
                    else:
                        logging.error("Failed to run assistant")
                else:
                    logging.error("Failed to add message to thread")
        else:
            logging.error("Failed to create thread")

        previous_interactions = get_previous_interactions(user_id)
        recommendations = generate_recommendations(previous_interactions)
        if recommendations:
            recommendations_str = ", ".join(recommendations)
            print(f"Recommendations based on your previous interactions: {recommendations_str}")

    except Exception as e:
        logging.error(f"An error occurred in the main function: {e}")

# Run the main function
if __name__ == "__main__":
    main()
