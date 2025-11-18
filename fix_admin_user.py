#!/usr/bin/env python3
"""
Quick script to fix the admin user role to primary_admin
Run this if you're getting "admin privileges required" errors
"""

import os
from dotenv import load_dotenv
from pymongo import MongoClient
from werkzeug.security import generate_password_hash

# Load environment variables
load_dotenv()

# MongoDB connection
MONGO_URI = os.environ.get('MONGO_URI', 'mongodb://localhost:27017/')
DB_NAME = os.environ.get('DB_NAME', 'app_distribution')

# Connect to MongoDB
client = MongoClient(MONGO_URI)
db = client[DB_NAME]
users_collection = db['users']

# Find admin user
admin_user = users_collection.find_one({'username': 'admin'})

if not admin_user:
    print("Admin user not found. Creating new admin user...")
    default_admin = {
        'username': 'admin',
        'password': generate_password_hash('admin123'),
        'role': 'primary_admin',
        'org_id': None,
        'org_role': None
    }
    users_collection.insert_one(default_admin)
    print("✓ Created admin user with primary_admin role")
else:
    print(f"Found admin user. Current role: {admin_user.get('role', 'not set')}")
    
    # Update to primary_admin
    update_data = {
        'role': 'primary_admin',
        'org_id': None,
        'org_role': None
    }
    
    result = users_collection.update_one(
        {'username': 'admin'},
        {'$set': update_data}
    )
    
    if result.modified_count > 0:
        print("✓ Updated admin user to primary_admin role")
        print("  - role: primary_admin")
        print("  - org_id: None")
        print("  - org_role: None")
    else:
        print("✓ Admin user already has primary_admin role (no changes needed)")

print("\nPlease restart your Flask app and log out/login again for changes to take effect.")

