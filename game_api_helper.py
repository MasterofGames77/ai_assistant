import logging
import os
import requests
from dotenv import load_dotenv
from twitch_auth import get_client_credentials_access_token

load_dotenv()

TWITCH_CLIENT_ID = os.getenv("NEXT_PUBLIC_TWITCH_CLIENT_ID")
RAWG_API_KEY = os.getenv("RAWG_API_KEY")

# Utility function to clean and match titles
def clean_and_match_title(query_title: str, record_title: str) -> bool:
    clean_query = query_title.lower().strip()
    clean_record = record_title.lower().strip()
    return clean_query == clean_record

# Fetch game data from IGDB
def fetch_from_igdb(game_title: str) -> str:
    try:
        access_token = get_client_credentials_access_token()  # Ensure token is valid and get it
        headers = {
            'Client-ID': TWITCH_CLIENT_ID,
            'Authorization': f'Bearer {access_token}'
        }
        body = f'fields name,release_dates.date,platforms.name,developers.name,publishers.name; where name ~ "{game_title}";'
        response = requests.post('https://api.igdb.com/v4/games', data=body, headers=headers)

        if response.status_code == 200:
            games = response.json()
            for game in games:
                if clean_and_match_title(game_title, game['name']):
                    release_date = game['release_dates'][0]['date'] if 'release_dates' in game else 'Unknown'
                    platforms = ', '.join([platform['name'] for platform in game.get('platforms', [])])
                    developers = ', '.join([dev['name'] for dev in game.get('developers', [])])
                    publishers = ', '.join([pub['name'] for pub in game.get('publishers', [])])
                    return (f"The game {game['name']} was released on {release_date}. "
                            f"It was developed by {developers or 'unknown developers'} and published by {publishers or 'unknown publishers'} "
                            f"and was released on {platforms or 'unknown platforms'}.")
        else:
            logging.error(f"Failed to fetch data from IGDB: {response.status_code} - {response.text}")
        return None

    except Exception as e:
        logging.error(f"Error in fetch_from_igdb: {e}")
        return None

# Fetch game data from RAWG
def fetch_from_rawg(game_title: str) -> str:
    try:
        url = f"https://api.rawg.io/api/games?key={RAWG_API_KEY}&search={game_title}"
        response = requests.get(url)
        
        if response.status_code == 200:
            games = response.json()['results']
            for game in games:
                if clean_and_match_title(game_title, game['name']):
                    release_date = game.get('released', 'Unknown')
                    platforms = ', '.join([platform['platform']['name'] for platform in game.get('platforms', [])])
                    return (f"The game {game['name']} was released on {release_date}. "
                            f"It was released on {platforms}.")
        else:
            logging.error(f"Failed to fetch data from RAWG: {response.status_code} - {response.text}")
        return None

    except Exception as e:
        logging.error(f"Error in fetch_from_rawg: {e}")
        return None