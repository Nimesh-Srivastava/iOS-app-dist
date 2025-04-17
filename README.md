# iOS App Distribution Platform

## Note
View CHANGELOG.md for comparing v2.2 and v2.1

This platform allows you to build and distribute iOS apps directly from GitHub repositories or by uploading IPA files.

## GitHub Actions Integration

This project now includes GitHub Actions support for automated iOS app building. When you push code to your repository, GitHub Actions can automatically build your iOS app and store the build artifacts.

### Setup Instructions

1. **Fork or clone this repository** to your GitHub account.

2. **Set up required secrets** in your GitHub repository:

   - Go to your repository on GitHub
   - Navigate to Settings > Secrets and variables > Actions
   - Add the following secrets:
     - `APPLE_TEAM_ID`: Your Apple Developer Team ID
     - `MONGO_URI`: Your MongoDB connection string
     - `DB_NAME`: Your database name
     - `SECRET_KEY`: Secret key for app security

3. **Customize the workflow** in `.github/workflows/build-ios-app.yml` if needed.

4. **Push your changes** to trigger the workflow, or manually run it from the Actions tab.

### How It Works

The GitHub Actions workflow:

1. Runs on a macOS environment to have access to Xcode
2. Sets up Python and installs dependencies
3. Configures Xcode with the latest stable version
4. Uses your app's `build_ios_app_from_github` function to build the app
5. Saves build artifacts for download

### Workflow Triggers

The workflow runs automatically when:

- You push to the `main` or `master` branch
- A pull request is opened against the `main` or `master` branch
- You manually trigger it from the GitHub Actions tab

### Viewing Build Results

1. Go to the Actions tab in your GitHub repository
2. Click on the workflow run
3. Download the build artifacts from the Summary page
4. The build is also recorded in your app's database for viewing in the web interface

## Manual Build Process

You can also trigger builds manually through the web interface:

1. Log in to the app
2. Navigate to the GitHub Build page
3. Enter your repository URL, branch, and other details
4. Click "Start Build"

## Troubleshooting

- **Build fails on GitHub Actions**: Check the workflow logs for detailed error messages.
- **Missing Xcode components**: Ensure the GitHub macOS runner has the necessary Xcode components.
- **Database connection issues**: Verify your MongoDB connection string in the secrets.

## MongoDB Storage

This application uses MongoDB for all data storage, including:

- User accounts and authentication
- App metadata and version information
- Build records and logs
- IPA files and other binary assets

### MongoDB Configuration

The application requires the following environment variables for MongoDB configuration:

- `MONGO_URI`: Your MongoDB connection string (e.g., "mongodb://localhost:27017/" or a MongoDB Atlas URI)
- `DB_NAME`: The name of the database to use (default: "app_distribution")

### MongoDB Collections

The application uses several collections in the database:

- `users`: Stores user account information
- `apps`: Stores app metadata and version information
- `builds`: Stores build records and logs
- `app_shares`: Tracks app sharing permissions between users
- `files`: Stores binary data for IPA files and other assets

### File Storage

Unlike previous versions that used the local filesystem, this version stores all binary files directly in MongoDB:

- IPA files are stored as binary data in the `files` collection
- File metadata (filename, size, MIME type) is stored alongside the binary data
- This allows for easier deployment and migration between environments
- No local file storage is required, except for temporary build files

## Requirements

- Python 3.7+
- Flask
- pymongo
- Pillow
- For local building: macOS with Xcode installed
- MongoDB 4.0+ (local instance or MongoDB Atlas)

## Environment Variables

- `SECRET_KEY`: Secret key for session security (required)
- `MONGO_URI`: MongoDB connection string (required)
- `DB_NAME`: MongoDB database name (default: "app_distribution")
- `APPLE_TEAM_ID`: Your Apple Developer Team ID (optional, used for builds)
- `GITHUB_REPO_URL`: Default GitHub repository URL (optional)
- `TZ`: Timezone for file upload timestamps (optional, default: "UTC")
