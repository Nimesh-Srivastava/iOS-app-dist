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
from dotenv import load_dotenv
load_dotenv()

app = Flask(__name__)

# Azure Storage Configuration
app.config.update({
    'AZURE_STORAGE_CONNECTION_STRING': os.getenv('AZURE_STORAGE_CONNECTION_STRING'),
    'AZURE_CONTAINER_NAME': 'ios-apps',
    'ALLOWED_EXTENSIONS': {
        'ipa': {'ipa'},
        'icon': {'png', 'jpg', 'jpeg'}
    },
    'MAX_CONTENT_LENGTH': 2 * 1024 * 1024 * 1024  # 2GB
})

# Initialize Azure clients
blob_service_client = BlobServiceClient.from_connection_string(
    app.config['AZURE_STORAGE_CONNECTION_STRING'])
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
                'title': plist.get('CFBundleDisplayName', plist.get('CFBundleName', 'Untitled App')),
                'min_os': plist.get('MinimumOSVersion', '12.0')
            }
    except Exception as e:
        app.logger.error(f"Error extracting app info: {str(e)}")
        return None

def azure_upload(blob_name, data, content_type):
    blob_client = container_client.get_blob_client(blob_name)
    blob_client.upload_blob(
        data,
        content_settings=ContentSettings(content_type=content_type),
        overwrite=True
    )
    return blob_client.url

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
                    'icon': latest['icon_url'],
                    'size': latest['size']
                })
    except Exception as e:
        app.logger.error(f"Error loading apps: {str(e)}")
    return render_template('index.html', apps=apps)

@app.route('/upload', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'POST':
        try:
            ipa_file = request.files['ipa']
            icon_file = request.files['icon']
            app_name = request.form['app_name']
            app_version = request.form['app_version']

            if not re.match(r'^\d+\.\d+\.\d+$', app_version):
                raise ValueError("Invalid version format")

            # Process IPA
            ipa_stream = ipa_file.stream.read()
            app_info = extract_app_info(BytesIO(ipa_stream))
            if not app_info:
                raise ValueError("Invalid IPA file")

            # Upload files
            app_id = str(uuid.uuid4())
            ipa_url = azure_upload(f"ipas/{app_id}.ipa", BytesIO(ipa_stream), 'application/octet-stream')
            icon_url = azure_upload(f"icons/{app_id}.png", icon_file.stream, 'image/png')

            # Create metadata
            metadata = {
                'bundle_id': app_info['bundle_id'],
                'display_name': app_name,
                'versions': {
                    app_version: {
                        'id': app_id,
                        'version': app_version,
                        'ipa_url': ipa_url,
                        'icon_url': icon_url,
                        'size': len(ipa_stream),
                        'uploaded_at': datetime.now().isoformat(),
                        'min_ios': app_info['min_os']
                    }
                }
            }

            # Upload manifest
            manifest = generate_manifest(app_info, ipa_url, icon_url)
            azure_upload(f"manifests/{app_id}.plist", BytesIO(manifest.encode()), 'text/xml')

            # Update metadata
            metadata_blob = f"metadata/{app_info['bundle_id']}.json"
            if container_client.get_blob_client(metadata_blob).exists():
                existing = json.loads(container_client.get_blob_client(metadata_blob).download_blob().readall())
                existing['versions'].update(metadata['versions'])
                metadata = existing
            azure_upload(metadata_blob, BytesIO(json.dumps(metadata).encode()), 'application/json')

            return redirect(url_for('index'))
        except Exception as e:
            app.logger.error(f"Upload failed: {str(e)}")
            return f"Error: {str(e)}", 400
    return render_template('upload.html')

@app.route('/delete/<bundle_id>/<version_id>', methods=['POST'])
def delete_version(bundle_id, version_id):
    try:
        metadata_blob = f"metadata/{bundle_id}.json"
        metadata = json.loads(container_client.get_blob_client(metadata_blob).download_blob().readall())
        version = metadata['versions'].get(version_id)
        
        if not version:
            raise ValueError("Version not found")

        # Delete blobs
        azure_delete(version['ipa_url'].split('/')[-1])
        azure_delete(version['icon_url'].split('/')[-1])
        azure_delete(f"manifests/{version_id}.plist")

        # Update metadata
        del metadata['versions'][version_id]
        if metadata['versions']:
            azure_upload(metadata_blob, BytesIO(json.dumps(metadata).encode()), 'application/json')
        else:
            azure_delete(metadata_blob)

        return redirect(url_for('index'))
    except Exception as e:
        app.logger.error(f"Delete failed: {str(e)}")
        return f"Error: {str(e)}", 400

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
