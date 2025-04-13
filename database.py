import os
from pymongo import MongoClient
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash

# Load environment variables
load_dotenv()

# MongoDB connection
MONGO_URI = os.environ.get('MONGO_URI', 'mongodb://localhost:27017/')
DB_NAME = os.environ.get('DB_NAME', 'app_distribution')

# Connect to MongoDB
client = MongoClient(MONGO_URI)
db = client[DB_NAME]

# Collections
users_collection = db['users']
apps_collection = db['apps']
builds_collection = db['builds']

def initialize_db():
    """Initialize database with default data if empty"""
    # Create indexes for better performance
    users_collection.create_index('username', unique=True)
    apps_collection.create_index('id', unique=True)
    builds_collection.create_index('id', unique=True)
    
    # Create default admin user if no users exist
    if users_collection.count_documents({}) == 0:
        default_admin = {
            'username': 'admin',
            'password': generate_password_hash('admin123'),
            'role': 'admin'
        }
        users_collection.insert_one(default_admin)
        print("Created default admin user (username: admin, password: admin123)")

# User operations
def get_users():
    """Get all users"""
    return list(users_collection.find({}, {'_id': 0}))

def get_user(username):
    """Get a user by username"""
    return users_collection.find_one({'username': username}, {'_id': 0})

def save_user(user_data):
    """Create or update a user"""
    username = user_data['username']
    users_collection.update_one(
        {'username': username},
        {'$set': user_data},
        upsert=True
    )

def delete_user(username):
    """Delete a user"""
    users_collection.delete_one({'username': username})

# App operations
def get_apps():
    """Get all apps"""
    return list(apps_collection.find({}, {'_id': 0}))

def get_app(app_id):
    """Get an app by ID"""
    return apps_collection.find_one({'id': app_id}, {'_id': 0})

def save_app(app_data):
    """Create or update an app"""
    app_id = app_data['id']
    apps_collection.update_one(
        {'id': app_id},
        {'$set': app_data},
        upsert=True
    )

def delete_app(app_id):
    """Delete an app"""
    apps_collection.delete_one({'id': app_id})

def save_apps(apps):
    """Save multiple apps (used for batch operations)"""
    for app in apps:
        save_app(app)

# Build operations
def get_builds():
    """Get all builds"""
    return list(builds_collection.find({}, {'_id': 0}))

def get_build(build_id):
    """Get a build by ID"""
    return builds_collection.find_one({'id': build_id}, {'_id': 0})

def save_build(build_data):
    """Create or update a build"""
    build_id = build_data['id']
    builds_collection.update_one(
        {'id': build_id},
        {'$set': build_data},
        upsert=True
    )

def update_build_status(build_id, status, log=None, end_time=None):
    """Update build status and optional fields"""
    update_data = {'status': status}
    if log is not None:
        update_data['log'] = log
    if end_time is not None:
        update_data['end_time'] = end_time
    
    builds_collection.update_one(
        {'id': build_id},
        {'$set': update_data}
    )
    return True 