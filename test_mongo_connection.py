import os
from pymongo import MongoClient
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Retrieve MongoDB URI from environment variables
mongo_uri = os.getenv("MONGODB_URI")

if not mongo_uri:
    raise ValueError("MONGODB_URI environment variable is missing")

# Connect to MongoDB
try:
    client = MongoClient(mongo_uri)
    db = client["Main"]  # Use the "Main" database
    users_collection = db["user_id"]  # Use the collection named "user_id"
    questions_collection = db["questions"]  # Use the collection named "questions"]

    # Test connection by listing collections
    collections = db.list_collection_names()
    print("Connected to MongoDB, collections:", collections)
except Exception as e:
    print(f"MongoDB connection error: {e}")