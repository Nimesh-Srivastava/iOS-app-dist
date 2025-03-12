from dotenv import load_dotenv
load_dotenv()
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
import ssl

app = Flask(__name__)

# Configuration
app.config.update({
    'AZURE_STORAGE_CONNECTION_STRING': os.getenv('AZURE_STORAGE_CONNECTION_STRING'),
    'AZURE_CONTAINER_NAME': 'ios-apps',
    'ALLOWED_EXTENSIONS': {
        'ipa': {'ipa'},
        'icon': {'png', 'jpg', 'jpeg'}
    },
    'MAX_CONTENT_LENGTH': 2 * 1024 * 1024 * 1024  # 2GB
})

# Initialize Azure clients with SSL verification disabled
ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

blob_service_client = BlobServiceClient.from_connection_string(
    app.config['AZURE_STORAGE_CONNECTION_STRING'],
    connection_verify=False
)
container_client = blob_service_client.get_container_client(
    app.config['AZURE_CONTAINER_NAME'])

# Configure logging
logging.basicConfig(level=logging.INFO)
app.logger = logging.getLogger(__name__)

# Custom Jinja filters
def format_datetime(value, fmt="%b %d, %Y %H:%M"):
    try:
        return datetime.fromisoformat(value).strftime(fmt)
    except:
        return "Unknown date"

app.jinja_env.filters['datetimeformat'] = format_datetime
app.jinja_env.filters['filesizeformat'] = lambda x: size(x)

def allowed_file(filename, file_type='ipa'):
    ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
    return ext in app.config['ALLOWED_EXTENSIONS'].get(file_type, set())

def extract_app_info(file_stream):
    try:
        with zipfile.ZipFile(file_stream) as ipa:
            plist_path = next(
                (n for n in ipa.namelist() 
                 if 'Payload/' in n and n.endswith('Info.plist')), None)
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

# def azure_upload(blob_name, data, content_type):
#     blob_client = container_client.get_blob_client(blob_name)
#     blob_client.upload_blob(
#         data,
#         content_settings=ContentSettings(content_type=content_type),
#         overwrite=True
#     )
#     return blob_client.url

def azure_upload(blob_name, data, content_type):
    blob_client = container_client.get_blob_client(blob_name)
    blob_client.upload_blob(
        data,
        content_settings=ContentSettings(content_type=content_type),
        overwrite=True
    )
    return url_for('serve_icon', filename=blob_name.split('/')[-1], _external=True)

def azure_delete(blob_name):
    blob_client = container_client.get_blob_client(blob_name)
    blob_client.delete_blob()

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
            </dict>
        </dict>
    </array>
</dict>
</plist>'''

@app.route('/')
def index():
    apps = []
    try:
        metadata_blobs = container_client.list_blobs(name_starts_with='metadata/')
        for blob in metadata_blobs:
            data = json.loads(container_client.get_blob_client(blob.name).download_blob().readall())
            if data.get('versions'):
                latest = max(data['versions'].values(), 
                           key=lambda v: version.parse(v['version']))
                apps.append({
                    'bundle_id': data['bundle_id'],
                    'name': data['display_name'],
                    'version': latest['version'],
                    'icon_url': latest['icon_url'],
                    'size': latest['size'],
                    'uploaded_at': latest['uploaded_at']
                })
    except Exception as e:
        app.logger.error(f"Error loading apps: {str(e)}")
    return render_template('index.html', apps=apps)

@app.route('/upload', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'POST':
        try:
            # Validate required fields
            if 'ipa' not in request.files or 'icon' not in request.files:
                return "Both IPA and icon files are required", 400
                
            ipa_file = request.files['ipa']
            icon_file = request.files['icon']
            
            if ipa_file.filename == '' or icon_file.filename == '':
                return "Please select both IPA and icon files", 400

            # Validate form fields
            if 'app_name' not in request.form or 'app_version' not in request.form:
                return "App name and version are required", 400
                
            app_name = request.form['app_name'].strip()
            app_version = request.form['app_version'].strip()

            # Validate inputs
            if not app_name:
                return "App name cannot be empty", 400
            if not re.match(r'^\d+\.\d+\.\d+$', app_version):
                return "Version must be in format X.Y.Z", 400
            if not allowed_file(ipa_file.filename, 'ipa'):
                return "Invalid IPA file type", 400
            if not allowed_file(icon_file.filename, 'icon'):
                return "Invalid icon file type", 400

            # Process IPA
            ipa_stream = ipa_file.stream.read()
            if not ipa_stream:
                return "Empty IPA file", 400

            app_info = extract_app_info(BytesIO(ipa_stream))
            if not app_info:
                return "Failed to extract app info from IPA", 400

            # Process icon
            icon_stream = icon_file.stream.read()
            icon_filename = f"{app_id}.png"
            icon_url = azure_upload(f"icons/{icon_filename}", BytesIO(icon_stream), 'image/png')

            # Upload files
            app_id = str(uuid.uuid4())
            ipa_url = azure_upload(f"ipas/{app_id}.ipa", BytesIO(ipa_stream), 'application/octet-stream')

            # Create metadata
            metadata = {
                'bundle_id': app_info['bundle_id'],
                'display_name': app_name,
                'versions': {
                    app_version: {
                        'id': app_id,
                        'version': app_version,
                        'ipa_url': ipa_url,
                        'icon_url': url_for('serve_icon', filename=icon_filename, _external=True),
                        'size': len(ipa_stream),
                        'uploaded_at': datetime.now().isoformat(),
                        'min_ios': app_info['min_os']
                    }
                }
            }

            # Handle existing versions
            metadata_blob = f"metadata/{app_info['bundle_id']}.json"
            if container_client.get_blob_client(metadata_blob).exists():
                existing = json.loads(container_client.get_blob_client(metadata_blob).download_blob().readall())
                metadata['versions'].update(existing['versions'])

            # Generate and upload manifest
            manifest = generate_manifest(app_info, ipa_url, icon_url)
            manifest_url = azure_upload(f"manifests/{app_id}.plist", BytesIO(manifest.encode()), 'text/xml')

            # Update version info with manifest URL
            metadata['versions'][app_version]['manifest_url'] = manifest_url

            # Save metadata
            azure_upload(metadata_blob, BytesIO(json.dumps(metadata).encode()), 'application/json')

            return redirect(url_for('index'))
            
        except Exception as e:
            app.logger.error(f"Upload error: {str(e)}", exc_info=True)
            return f"Upload failed: {str(e)}", 500

    return render_template('upload.html')

@app.route('/manifests/<path:filename>')
def download_manifest(filename):
    try:
        blob_name = f"manifests/{filename}"
        blob_client = container_client.get_blob_client(blob_name)
        
        if not blob_client.exists():
            return "Manifest not found", 404
            
        manifest = blob_client.download_blob().readall()
        return manifest, 200, {'Content-Type': 'text/xml'}
    except Exception as e:
        app.logger.error(f"Error serving manifest {filename}: {str(e)}")
        return "Error serving manifest", 500

@app.route('/app/<bundle_id>')
def app_detail(bundle_id):
    try:
        metadata_blob = f"metadata/{bundle_id}.json"
        blob_client = container_client.get_blob_client(metadata_blob)
        
        if not blob_client.exists():
            return "App not found", 404
            
        metadata = json.loads(blob_client.download_blob().readall())
        versions = sorted(metadata['versions'].values(),
                        key=lambda v: version.parse(v['version']),
                        reverse=True)
        
        return render_template('app_detail.html', 
                             app=metadata,
                             versions=versions,
                             latest=versions[0])
    except Exception as e:
        app.logger.error(f"Error loading app {bundle_id}: {str(e)}")
        return "Error loading app", 500

@app.route('/delete/<bundle_id>/<version_id>', methods=['POST'])
def delete_version(bundle_id, version_id):
    try:
        metadata_blob = f"metadata/{bundle_id}.json"
        blob_client = container_client.get_blob_client(metadata_blob)
        
        if not blob_client.exists():
            return "App not found", 404
            
        metadata = json.loads(blob_client.download_blob().readall())
        version_info = next((v for v in metadata['versions'].values() if v['id'] == version_id), None)
        
        if not version_info:
            return "Version not found", 404

        # Delete associated files
        azure_delete(version_info['ipa_url'].split('/')[-1])
        azure_delete(version_info['icon_url'].split('/')[-1])
        azure_delete(f"manifests/{version_id}.plist")

        # Update metadata
        del metadata['versions'][version_info['version']]
        if metadata['versions']:
            azure_upload(metadata_blob, BytesIO(json.dumps(metadata).encode()), 'application/json')
        else:
            azure_delete(metadata_blob)

        return redirect(url_for('index'))
    except Exception as e:
        app.logger.error(f"Delete error: {str(e)}")
        return f"Error deleting version: {str(e)}", 500

@app.route('/icons/<path:filename>')
def serve_icon(filename):
    try:
        blob_name = f"icons/{filename}"
        blob_client = container_client.get_blob_client(blob_name)
        
        if not blob_client.exists():
            return "Icon not found", 404
            
        icon = blob_client.download_blob().readall()
        return icon, 200, {'Content-Type': 'image/png'}
    except Exception as e:
        app.logger.error(f"Error serving icon {filename}: {str(e)}")
        return "Error serving icon", 500

@app.route('/.well-known/apple-app-site-association')
def aasa():
    return jsonify({
        "applinks": {
            "apps": [],
            "details": []
        }
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
