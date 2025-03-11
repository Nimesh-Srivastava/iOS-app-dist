from flask import Flask, render_template, request, redirect, url_for, jsonify
from datetime import datetime
import os
import uuid
import zipfile
import plistlib
import json
import re
import logging
from io import BytesIO
from biplist import readPlist, InvalidPlistException
from PIL import Image
from packaging import version
from hurry.filesize import size
from azure.storage.blob import BlobServiceClient, ContentSettings
import tempfile

app = Flask(__name__)
app.config.update({
    'ALLOWED_EXTENSIONS': {
        'ipa': {'ipa'},
        'icon': {'png', 'jpg', 'jpeg'}
    },
    'MAX_CONTENT_LENGTH': 2 * 1024 * 1024 * 1024,  # 2GB
    
    # Azure Storage configuration
    'AZURE_STORAGE_CONNECTION_STRING': os.environ.get('AZURE_STORAGE_CONNECTION_STRING'),
    'AZURE_STORAGE_CONTAINER_NAME': os.environ.get('AZURE_STORAGE_CONTAINER_NAME', 'ipa-store'),
    
    # Blob prefixes for organization
    'IPA_PREFIX': 'ipas/',
    'ICON_PREFIX': 'icons/',
    'MANIFEST_PREFIX': 'manifests/',
    'METADATA_PREFIX': 'metadata/'
})

# Configure logging
app.logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
app.logger.addHandler(handler)

# Initialize Azure Blob Storage Client
blob_service_client = BlobServiceClient.from_connection_string(
    app.config['AZURE_STORAGE_CONNECTION_STRING']
)

# Create container if it doesn't exist
try:
    container_client = blob_service_client.get_container_client(app.config['AZURE_STORAGE_CONTAINER_NAME'])
    if not container_client.exists():
        container_client.create_container(public_access="blob")
        app.logger.info(f"Container {app.config['AZURE_STORAGE_CONTAINER_NAME']} created")
except Exception as e:
    app.logger.error(f"Error initializing Azure Storage: {str(e)}")

# Custom Jinja filters
def format_datetime(value, fmt="%b %d, %Y %H:%M"):
    if not value:
        return "Unknown date"
    try:
        if isinstance(value, str):
            value = datetime.fromisoformat(value)
        return value.strftime(fmt)
    except Exception as e:
        app.logger.error(f"Error formatting datetime {value}: {str(e)}")
        return "Invalid date"

app.jinja_env.filters['datetimeformat'] = format_datetime
app.jinja_env.filters['filesizeformat'] = lambda x: size(x)

def allowed_file(filename, file_type='ipa'):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS'].get(file_type, set())

def extract_app_info(ipa_data):
    try:
        with zipfile.ZipFile(BytesIO(ipa_data)) as ipa:
            plist_path = next(
                (name for name in ipa.namelist() 
                 if 'Payload/' in name and name.endswith('Info.plist')),
                None
            )

            if not plist_path:
                return None

            plist_data = ipa.read(plist_path)
            
            try:
                plist = readPlist(BytesIO(plist_data))
            except (InvalidPlistException, Exception):
                plist = plistlib.loads(plist_data)

            return {
                'bundle_id': plist.get('CFBundleIdentifier', 'unknown.bundle.id'),
                'version': plist.get('CFBundleShortVersionString', '1.0'),
                'title': plist.get('CFBundleDisplayName', 
                          plist.get('CFBundleName', 'Untitled App')),
                'min_os': plist.get('MinimumOSVersion', '12.0')
            }
    except Exception as e:
        app.logger.error(f"Error extracting app info: {str(e)}")
        return None

def process_icon(icon_file, app_id):
    try:
        image = Image.open(icon_file.stream)
        image = image.convert('RGBA')
        
        sizes = [(512, 512), (1024, 1024)]
        icon_paths = []
        
        for size_dim in sizes:
            resized = image.resize(size_dim, Image.LANCZOS)
            
            # Save to BytesIO instead of file
            img_byte_arr = BytesIO()
            resized.save(img_byte_arr, format='PNG')
            img_byte_arr.seek(0)
            
            icon_blob_name = f"{app.config['ICON_PREFIX']}{app_id}-{size_dim[0]}x{size_dim[1]}.png"
            blob_client = blob_service_client.get_blob_client(
                container=app.config['AZURE_STORAGE_CONTAINER_NAME'],
                blob=icon_blob_name
            )
            
            blob_client.upload_blob(
                img_byte_arr, 
                overwrite=True, 
                content_settings=ContentSettings(content_type='image/png')
            )
            
            icon_paths.append(icon_blob_name)
            
        return icon_paths[0]  # Return the 512x512 icon path
    except Exception as e:
        app.logger.error(f"Error processing icon: {str(e)}")
        return False

def generate_manifest(app_info, ipa_url, icon_url):
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>items</key>
    <array>
        <dict>
            <key>assets</key>
            <array>
                <dict>
                    <key>kind</key>
                    <string>software-package</string>
                    <key>url</key>
                    <string>{ipa_url}</string>
                </dict>
                <dict>
                    <key>kind</key>
                    <string>display-image</string>
                    <key>needs-shine</key>
                    <true/>
                    <key>url</key>
                    <string>{icon_url}</string>
                </dict>
                <dict>
                    <key>kind</key>
                    <string>full-size-image</string>
                    <key>needs-shine</key>
                    <true/>
                    <key>url</key>
                    <string>{icon_url}</string>
                </dict>
            </array>
            <key>metadata</key>
            <dict>
                <key>bundle-identifier</key>
                <string>{app_info['bundle_id']}</string>
                <key>bundle-version</key>
                <string>{app_info['version']}</string>
                <key>kind</key>
                <string>software</string>
                <key>title</key>
                <string>{app_info['title']}</string>
                <key>subtitle</key>
                <string>{app_info['title']}</string>
            </dict>
        </dict>
    </array>
</dict>
</plist>'''

def get_blob_url(blob_name):
    """Generate a URL for a blob"""
    account_name = blob_service_client.account_name
    container_name = app.config['AZURE_STORAGE_CONTAINER_NAME']
    return f"https://{account_name}.blob.core.windows.net/{container_name}/{blob_name}"

def migrate_old_metadata():
    """Convert old metadata stored in Azure to new format"""
    try:
        container_client = blob_service_client.get_container_client(app.config['AZURE_STORAGE_CONTAINER_NAME'])
        blobs = container_client.list_blobs(name_starts_with=app.config['METADATA_PREFIX'])
        
        for blob in blobs:
            if not blob.name.endswith('.json'):
                continue
                
            try:
                blob_client = container_client.get_blob_client(blob.name)
                data_stream = blob_client.download_blob()
                data = json.loads(data_stream.readall())
                
                if 'bundle_id' in data:
                    continue
                    
                if 'id' in data and 'name' in data:
                    app.logger.info(f"Migrating legacy metadata: {blob.name}")
                    
                    new_metadata = {
                        'bundle_id': data.get('bundle_id', 'unknown.bundle.id'),
                        'display_name': data['name'],
                        'created_at': data.get('created_at', datetime.now().isoformat()),
                        'versions': {
                            data.get('version', '1.0.0'): {
                                'id': data['id'],
                                'ipa': f"{app.config['IPA_PREFIX']}{data['id']}.ipa",
                                'icon': data.get('icon', f"{app.config['ICON_PREFIX']}default.png"),
                                'uploaded_at': data.get('created_at', datetime.now().isoformat()),
                                'version': data.get('version', '1.0.0'),
                                'min_ios': data.get('min_ios', '12.0'),
                                'size': data.get('size', 0)
                            }
                        }
                    }
                    
                    new_blob_name = f"{app.config['METADATA_PREFIX']}{new_metadata['bundle_id']}.json"
                    new_blob_client = container_client.get_blob_client(new_blob_name)
                    
                    new_blob_client.upload_blob(
                        json.dumps(new_metadata),
                        overwrite=True,
                        content_settings=ContentSettings(content_type='application/json')
                    )
                    
                    # Delete old blob
                    blob_client.delete_blob()
                    
            except Exception as e:
                app.logger.error(f"Migration failed for {blob.name}: {str(e)}")
                
    except Exception as e:
        app.logger.error(f"Error during metadata migration: {str(e)}")

@app.route('/')
def index():
    apps = []
    
    try:
        container_client = blob_service_client.get_container_client(app.config['AZURE_STORAGE_CONTAINER_NAME'])
        blobs = container_client.list_blobs(name_starts_with=app.config['METADATA_PREFIX'])
        
        for blob in blobs:
            if blob.name.endswith('.json'):
                try:
                    blob_client = container_client.get_blob_client(blob.name)
                    data_stream = blob_client.download_blob()
                    metadata = json.loads(data_stream.readall())
                    
                    if 'bundle_id' not in metadata or 'versions' not in metadata:
                        continue

                    if not metadata['versions']:
                        continue

                    versions = sorted(metadata['versions'].values(),
                                    key=lambda v: version.parse(v['version']),
                                    reverse=True)
                    latest = versions[0]

                    # Get icon URL from Azure
                    icon_blob_name = latest['icon']
                    icon_url = get_blob_url(icon_blob_name)

                    apps.append({
                        'bundle_id': metadata['bundle_id'],
                        'name': metadata.get('display_name', 'Unnamed App'),
                        'latest_version': latest,
                        'icon': icon_url,
                        'version_count': len(versions)
                    })

                except Exception as e:
                    app.logger.error(f"Error processing {blob.name}: {str(e)}")
    
    except Exception as e:
        app.logger.error(f"Error listing apps: {str(e)}")

    return render_template('index.html', apps=apps)

@app.route('/upload', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'POST':
        app_id = None
        try:
            file = request.files.get('file')
            app_name = request.form.get('app_name', '').strip()
            app_version = request.form.get('app_version', '1.0.0')
            icon_file = request.files.get('icon')

            if not app_name:
                return "App name is required", 400
            if not re.match(r'^\d+\.\d+\.\d+$', app_version):
                return "Invalid version format", 400
            if not file or not allowed_file(file.filename, 'ipa'):
                return "Invalid IPA file", 400
            if not icon_file or not allowed_file(icon_file.filename, 'icon'):
                return "Invalid icon file", 400

            app_id = str(uuid.uuid4())
            
            # Read IPA file into memory
            ipa_data = file.read()
            
            # Extract app info from IPA
            app_info = extract_app_info(ipa_data)
            if not app_info:
                raise ValueError("Invalid IPA file structure")

            bundle_id = app_info['bundle_id']
            metadata = get_app_versions(bundle_id) or {
                'bundle_id': bundle_id,
                'display_name': app_name,
                'versions': {},
                'created_at': datetime.now().isoformat()
            }

            if app_version in metadata['versions']:
                return "Version already exists", 400
                
            # Upload IPA to Azure
            ipa_blob_name = f"{app.config['IPA_PREFIX']}{app_id}.ipa"
            ipa_blob_client = blob_service_client.get_blob_client(
                container=app.config['AZURE_STORAGE_CONTAINER_NAME'],
                blob=ipa_blob_name
            )
            
            # Reset file cursor and upload
            file.seek(0)
            ipa_blob_client.upload_blob(
                file, 
                overwrite=True,
                content_settings=ContentSettings(content_type='application/octet-stream')
            )
            
            # Get file size
            ipa_size = len(ipa_data)

            # Process and upload icon
            icon_path = process_icon(icon_file, app_id)
            if not icon_path:
                raise ValueError("Icon processing failed")

            # Generate and save manifest
            ipa_url = get_blob_url(ipa_blob_name)
            icon_url = get_blob_url(icon_path)
            
            manifest = generate_manifest(
                {'title': app_name, 'version': app_version, 'bundle_id': bundle_id},
                ipa_url,
                icon_url
            )
            
            manifest_blob_name = f"{app.config['MANIFEST_PREFIX']}{app_id}.plist"
            manifest_blob_client = blob_service_client.get_blob_client(
                container=app.config['AZURE_STORAGE_CONTAINER_NAME'],
                blob=manifest_blob_name
            )
            
            manifest_blob_client.upload_blob(
                manifest, 
                overwrite=True,
                content_settings=ContentSettings(content_type='text/xml')
            )

            # Update metadata
            metadata['versions'][app_version] = {
                'id': app_id,
                'ipa': ipa_blob_name,
                'icon': icon_path,
                'uploaded_at': datetime.now().isoformat(),
                'version': app_version,
                'min_ios': app_info.get('min_os', '12.0'),
                'size': ipa_size
            }

            metadata['display_name'] = app_name
            
            # Save updated metadata
            save_app_versions(bundle_id, metadata)
            
            return redirect(url_for('app_detail', bundle_id=bundle_id))
            
        except Exception as e:
            if app_id:
                cleanup_partial_upload(app_id)
            return f"Upload failed: {str(e)}", 400
            
    return render_template('upload.html')

def get_app_versions(bundle_id):
    try:
        metadata_blob_name = f"{app.config['METADATA_PREFIX']}{bundle_id}.json"
        blob_client = blob_service_client.get_blob_client(
            container=app.config['AZURE_STORAGE_CONTAINER_NAME'],
            blob=metadata_blob_name
        )
        
        data_stream = blob_client.download_blob()
        metadata = json.loads(data_stream.readall())
        metadata.setdefault('versions', {})
        return metadata
    except Exception as e:
        app.logger.debug(f"Metadata not found for {bundle_id}: {str(e)}")
        return None

def save_app_versions(bundle_id, data):
    try:
        metadata_blob_name = f"{app.config['METADATA_PREFIX']}{bundle_id}.json"
        blob_client = blob_service_client.get_blob_client(
            container=app.config['AZURE_STORAGE_CONTAINER_NAME'],
            blob=metadata_blob_name
        )
        
        blob_client.upload_blob(
            json.dumps(data), 
            overwrite=True,
            content_settings=ContentSettings(content_type='application/json')
        )
    except Exception as e:
        app.logger.error(f"Error saving metadata for {bundle_id}: {str(e)}")
        raise

def cleanup_partial_upload(app_id):
    try:
        container_client = blob_service_client.get_container_client(app.config['AZURE_STORAGE_CONTAINER_NAME'])
        
        # Prefixes to check
        prefixes = [
            f"{app.config['IPA_PREFIX']}{app_id}.ipa",
            f"{app.config['ICON_PREFIX']}{app_id}-",
            f"{app.config['MANIFEST_PREFIX']}{app_id}.plist"
        ]
        
        for prefix in prefixes:
            blobs = container_client.list_blobs(name_starts_with=prefix)
            for blob in blobs:
                try:
                    blob_client = container_client.get_blob_client(blob.name)
                    blob_client.delete_blob()
                except Exception as e:
                    app.logger.error(f"Error deleting {blob.name}: {str(e)}")
    except Exception as e:
        app.logger.error(f"Error during cleanup: {str(e)}")

@app.route('/app/<bundle_id>')
def app_detail(bundle_id):
    metadata = get_app_versions(bundle_id)
    if not metadata or not metadata.get('versions'):
        return "App not found", 404
        
    versions = sorted(metadata['versions'].values(),
                    key=lambda v: version.parse(v['version']),
                    reverse=True)
    
    # Add URLs for each version
    for v in versions:
        v['ipa_url'] = get_blob_url(v['ipa'])
        v['icon_url'] = get_blob_url(v['icon'])
        v['manifest_url'] = get_blob_url(f"{app.config['MANIFEST_PREFIX']}{v['id']}.plist")
    
    return render_template('app_detail.html',
                         app=metadata,
                         versions=versions,
                         latest=versions[0])

@app.route('/delete/<bundle_id>/<version_id>', methods=['POST'])
def delete_version(bundle_id, version_id):
    metadata = get_app_versions(bundle_id)
    if not metadata:
        return "App not found", 404

    version_info = next((v for v in metadata['versions'].values() if v['id'] == version_id), None)
    if not version_info:
        return "Version not found", 404

    # Delete blobs
    try:
        container_client = blob_service_client.get_container_client(app.config['AZURE_STORAGE_CONTAINER_NAME'])
        
        # Files to delete
        blobs_to_delete = [
            version_info['ipa'],
            version_info['icon'],
            f"{app.config['MANIFEST_PREFIX']}{version_id}.plist"
        ]
        
        # Also delete the 1024x1024 icon if it exists
        if '-512x512.png' in version_info['icon']:
            large_icon = version_info['icon'].replace('-512x512.png', '-1024x1024.png')
            blobs_to_delete.append(large_icon)
        
        for blob_name in blobs_to_delete:
            try:
                blob_client = container_client.get_blob_client(blob_name)
                blob_client.delete_blob()
            except Exception as e:
                app.logger.error(f"Error deleting {blob_name}: {str(e)}")
    
    except Exception as e:
        app.logger.error(f"Error during blob deletion: {str(e)}")

    # Update metadata
    del metadata['versions'][version_info['version']]
    if metadata['versions']:
        save_app_versions(bundle_id, metadata)
    else:
        # Delete the metadata file if no versions remain
        try:
            metadata_blob_name = f"{app.config['METADATA_PREFIX']}{bundle_id}.json"
            blob_client = blob_service_client.get_blob_client(
                container=app.config['AZURE_STORAGE_CONTAINER_NAME'],
                blob=metadata_blob_name
            )
            blob_client.delete_blob()
        except Exception as e:
            app.logger.error(f"Error deleting metadata for {bundle_id}: {str(e)}")
    
    return redirect(url_for('index'))

@app.route('/download/<path:blob_path>')
def download_blob(blob_path):
    """Generic endpoint to download a blob by its path"""
    try:
        # Create a redirect to the Azure Storage URL
        blob_url = get_blob_url(blob_path)
        return redirect(blob_url)
    except Exception as e:
        app.logger.error(f"Error downloading {blob_path}: {str(e)}")
        return "File not found", 404

@app.route('/.well-known/apple-app-site-association')
def aasa():
    return jsonify({
        "applinks": {
            "apps": [],
            "details": []
        }
    })

if __name__ == '__main__':
    with app.app_context():
        migrate_old_metadata()
    
    ssl_context = ('cert.pem', 'key.pem') if os.path.exists('cert.pem') else 'adhoc'
    app.run(host='0.0.0.0', port=443, ssl_context=ssl_context, debug=True)