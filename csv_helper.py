import pandas as pd

def read_csv_file(file_path: str) -> pd.DataFrame:
    try:
        data = pd.read_csv(file_path)
        return data
    except Exception as e:
        print(f"Error reading CSV file: {e}")
        return pd.DataFrame()  # Return an empty DataFrame in case of error

def format_game_info(game_info: pd.Series) -> str:
    return f"{game_info['title']} was released on {game_info['release_year']} for {game_info['console']}. It is a {game_info['genre']} game published by {game_info['publisher']}."
