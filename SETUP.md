# How to Run the iOS App Distribution Platform

## Prerequisites

1. **Python 3.7+** - Check with `python3 --version`
2. **MongoDB** - Either:
   - Local MongoDB installation, or
   - MongoDB Atlas account (cloud)
3. **SSL Certificates** (optional for development) - For HTTPS

## Step-by-Step Setup

### 1. Install Python Dependencies

```bash
pip3 install -r requirements.txt
```

Or if you prefer using a virtual environment (recommended):

```bash
# Create virtual environment
python3 -m venv venv

# Activate virtual environment
# On macOS/Linux:
source venv/bin/activate
# On Windows:
# venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Set Up MongoDB

#### Option A: Local MongoDB
- Install MongoDB locally
- Start MongoDB service: `mongod` (or use your system's service manager)
- Default connection: `mongodb://localhost:27017/`

#### Option B: MongoDB Atlas (Cloud)
- Sign up at https://www.mongodb.com/cloud/atlas
- Create a free cluster
- Get your connection string (looks like: `mongodb+srv://username:password@cluster.mongodb.net/`)

### 3. Create Environment Variables

Create a `.env` file in the project root:

```bash
# Required
SECRET_KEY=your-secret-key-here-change-this-in-production
MONGO_URI=mongodb://localhost:27017/
DB_NAME=app_distribution

# Optional
PORT=5000
TZ=UTC
APPLE_TEAM_ID=your-team-id-if-needed
GITHUB_TOKEN=your-github-token-if-using-github-builds
```

**Important**: Replace `your-secret-key-here-change-this-in-production` with a secure random string. You can generate one with:
```python
import secrets
print(secrets.token_hex(32))
```

### 4. SSL Certificates (Optional for Development)

The app tries to use SSL certificates (`cert.pem` and `key.pem`). For development, you can:

#### Option A: Run without SSL (Modify app.py)
Change the last line in `app.py` from:
```python
app.run(host='0.0.0.0', port=port, debug='true', ssl_context=('cert.pem', 'key.pem'))
```

To:
```python
app.run(host='0.0.0.0', port=port, debug=True)
```

#### Option B: Generate Self-Signed Certificates
```bash
openssl req -x509 -newkey rsa:4096 -nodes -out cert.pem -keyout key.pem -days 365
```

### 5. Run the Application

```bash
python3 app.py
```

Or if using a virtual environment:
```bash
source venv/bin/activate
python app.py
```

The app will start on `http://localhost:5000` (or the port specified in your `.env` file).

### 6. Initial Login

On first run, the app creates a default admin user:
- **Username**: `admin`
- **Password**: `admin123`

**⚠️ IMPORTANT**: Change this password immediately after first login!

## Accessing the Application

1. Open your browser and go to: `http://localhost:5000` (or `https://localhost:5000` if using SSL)
2. Login with the default credentials above
3. As the primary admin, you can now:
   - Create organizations at `/organizations`
   - Add users to organizations
   - Manage all organizations and users

## Troubleshooting

### MongoDB Connection Issues
- Verify MongoDB is running: `mongosh` or `mongo` should connect
- Check your `MONGO_URI` in `.env` file
- For Atlas, ensure your IP is whitelisted in MongoDB Atlas dashboard

### Port Already in Use
- Change the `PORT` in your `.env` file
- Or kill the process using the port:
  ```bash
  # Find process
  lsof -i :5000
  # Kill it
  kill -9 <PID>
  ```

### SSL Certificate Errors
- Use Option A above to run without SSL for development
- Or generate proper certificates

### Import Errors
- Ensure all dependencies are installed: `pip install -r requirements.txt`
- Activate your virtual environment if using one

## Production Deployment

For production:
1. Set `debug=False` in `app.py`
2. Use a proper WSGI server like Gunicorn:
   ```bash
   pip install gunicorn
   gunicorn -w 4 -b 0.0.0.0:5000 app:app
   ```
3. Use proper SSL certificates from a certificate authority
4. Set strong `SECRET_KEY` in environment variables
5. Use environment variables instead of `.env` file for security

## Quick Start (TL;DR)

```bash
# 1. Install dependencies
pip3 install -r requirements.txt

# 2. Create .env file with:
# SECRET_KEY=your-secret-key
# MONGO_URI=mongodb://localhost:27017/
# DB_NAME=app_distribution

# 3. Start MongoDB (if local)

# 4. Run app (modify app.py to remove SSL for dev)
python3 app.py

# 5. Login at http://localhost:5000
# Username: admin
# Password: admin123
```

