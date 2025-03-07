from flask import Flask, render_template, send_from_directory, request, redirect, url_for, jsonify
from datetime import datetime
import os
import uuid
import zipfile
import plistlib
import json
import re
import glob
import logging
from io import BytesIO
from biplist import readPlist, InvalidPlistException
from PIL import Image
from packaging import version
from hurry.filesize import size

app = Flask(__name__)
app.config.update({
    'UPLOAD_FOLDER': 'uploads',
    'IPA_FOLDER': 'uploads/ipas',
    'MANIFEST_FOLDER': 'uploads/manifests',
    'ICON_FOLDER': 'uploads/icons',
    'METADATA_FOLDER': 'uploads/metadata',
    'ALLOWED_EXTENSIONS': {
        'ipa': {'ipa'},
        'icon': {'png', 'jpg', 'jpeg'}
    },
    'MAX_CONTENT_LENGTH': 2 * 1024 * 1024 * 1024  # 2GB
})

# Configure logging
app.logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
app.logger.addHandler(handler)

# Create required directories
for folder in [app.config['UPLOAD_FOLDER'], app.config['IPA_FOLDER'], 
              app.config['MANIFEST_FOLDER'], app.config['ICON_FOLDER'],
              app.config['METADATA_FOLDER']]:
    os.makedirs(folder, exist_ok=True)

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

def extract_app_info(ipa_path):
    try:
        with zipfile.ZipFile(ipa_path) as ipa:
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
        for size_dim in sizes:
            resized = image.resize(size_dim, Image.LANCZOS)
            icon_path = os.path.join(app.config['ICON_FOLDER'], f'{app_id}-{size_dim[0]}x{size_dim[1]}.png')
            resized.save(icon_path, 'PNG')
            
        return True
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

def migrate_old_metadata():
    """Convert old per-version metadata to new format"""
    metadata_dir = app.config['METADATA_FOLDER']
    if not os.path.exists(metadata_dir):
        return

    for filename in os.listdir(metadata_dir):
        if not filename.endswith('.json'):
            continue
            
        try:
            file_path = os.path.join(metadata_dir, filename)
            with open(file_path, 'r') as f:
                data = json.load(f)
                
                if 'bundle_id' in data:
                    continue
                    
                if 'id' in data and 'name' in data:
                    app.logger.info(f"Migrating legacy metadata: {filename}")
                    
                    new_metadata = {
                        'bundle_id': data.get('bundle_id', 'unknown.bundle.id'),
                        'display_name': data['name'],
                        'created_at': data.get('created_at', datetime.now().isoformat()),
                        'versions': {
                            data.get('version', '1.0.0'): {
                                'id': data['id'],
                                'ipa': f"{data['id']}.ipa",
                                'icon': data.get('icon', 'default.png'),
                                'uploaded_at': data.get('created_at', datetime.now().isoformat()),
                                'version': data.get('version', '1.0.0'),
                                'min_ios': data.get('min_ios', '12.0'),
                                'size': data.get('size', 0)
                            }
                        }
                    }
                    
                    new_filename = f"{new_metadata['bundle_id']}.json"
                    new_path = os.path.join(metadata_dir, new_filename)
                    
                    with open(new_path, 'w') as nf:
                        json.dump(new_metadata, nf)
                        
                    os.remove(file_path)
                    
        except Exception as e:
            app.logger.error(f"Migration failed for {filename}: {str(e)}")

@app.route('/')
def index():
    apps = []
    metadata_dir = app.config['METADATA_FOLDER']
    
    if not os.path.exists(metadata_dir):
        return render_template('index.html', apps=apps)

    for filename in os.listdir(metadata_dir):
        if filename.endswith('.json'):
            file_path = os.path.join(metadata_dir, filename)
            try:
                with open(file_path, 'r') as f:
                    metadata = json.load(f)
                    
                    if 'bundle_id' not in metadata or 'versions' not in metadata:
                        continue

                    if not metadata['versions']:
                        continue

                    versions = sorted(metadata['versions'].values(),
                                    key=lambda v: version.parse(v['version']),
                                    reverse=True)
                    latest = versions[0]

                    apps.append({
                        'bundle_id': metadata['bundle_id'],
                        'name': metadata.get('display_name', 'Unnamed App'),
                        'latest_version': latest,
                        'icon': url_for('serve_icon', filename=latest['icon']),
                        'version_count': len(versions)
                    })

            except Exception as e:
                app.logger.error(f"Error processing {filename}: {str(e)}")

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
            ipa_filename = f"{app_id}.ipa"
            ipa_path = os.path.join(app.config['IPA_FOLDER'], ipa_filename)
            file.save(ipa_path)
            
            app_info = extract_app_info(ipa_path)
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

            if not process_icon(icon_file, app_id):
                raise ValueError("Icon processing failed")

            metadata['versions'][app_version] = {
                'id': app_id,
                'ipa': ipa_filename,
                'icon': f'{app_id}-512x512.png',
                'uploaded_at': datetime.now().isoformat(),
                'version': app_version,
                'min_ios': app_info.get('min_os', '12.0'),
                'size': os.path.getsize(ipa_path)
            }

            metadata['display_name'] = app_name

            manifest = generate_manifest(
                {'title': app_name, 'version': app_version, 'bundle_id': bundle_id},
                url_for('download_ipa', filename=ipa_filename, _external=True),
                url_for('serve_icon', filename=f'{app_id}-512x512.png', _external=True)
            )
            
            manifest_path = os.path.join(app.config['MANIFEST_FOLDER'], f'{app_id}.plist')
            with open(manifest_path, 'w') as f:
                f.write(manifest)

            save_app_versions(bundle_id, metadata)
            
            return redirect(url_for('app_detail', bundle_id=bundle_id))
            
        except Exception as e:
            if app_id:
                cleanup_partial_upload(app_id)
            return f"Upload failed: {str(e)}", 400
            
    return render_template('upload.html')

def get_app_versions(bundle_id):
    metadata_path = os.path.join(app.config['METADATA_FOLDER'], f'{bundle_id}.json')
    if os.path.exists(metadata_path):
        try:
            with open(metadata_path, 'r') as f:
                metadata = json.load(f)
                metadata.setdefault('versions', {})
                return metadata
        except Exception as e:
            app.logger.error(f"Error loading {bundle_id}: {str(e)}")
    return None

def save_app_versions(bundle_id, data):
    metadata_path = os.path.join(app.config['METADATA_FOLDER'], f'{bundle_id}.json')
    with open(metadata_path, 'w') as f:
        json.dump(data, f)

def cleanup_partial_upload(app_id):
    patterns = [
        (app.config['IPA_FOLDER'], f'{app_id}.ipa'),
        (app.config['ICON_FOLDER'], f'{app_id}-*.png'),
        (app.config['MANIFEST_FOLDER'], f'{app_id}.plist')
    ]
    for folder, pattern in patterns:
        for f in glob.glob(os.path.join(folder, pattern)):
            try:
                os.remove(f)
            except OSError:
                pass

@app.route('/app/<bundle_id>')
def app_detail(bundle_id):
    metadata = get_app_versions(bundle_id)
    if not metadata or not metadata.get('versions'):
        return "App not found", 404
        
    versions = sorted(metadata['versions'].values(),
                    key=lambda v: version.parse(v['version']),
                    reverse=True)
    
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

    # Delete files
    files_to_delete = [
        (app.config['IPA_FOLDER'], version_info['ipa']),
        (app.config['MANIFEST_FOLDER'], f"{version_id}.plist"),
        (app.config['ICON_FOLDER'], f"{version_id}-*.png")
    ]
    
    for folder, pattern in files_to_delete:
        for f in glob.glob(os.path.join(folder, pattern)):
            try:
                os.remove(f)
            except OSError:
                pass

    # Update metadata
    del metadata['versions'][version_info['version']]
    if metadata['versions']:
        save_app_versions(bundle_id, metadata)
    else:
        os.remove(os.path.join(app.config['METADATA_FOLDER'], f'{bundle_id}.json'))
    
    return redirect(url_for('index'))

@app.route('/ipa/<path:filename>')
def download_ipa(filename):
    return send_from_directory(app.config['IPA_FOLDER'], filename,
                             mimetype='application/octet-stream')

@app.route('/icon/<path:filename>')
def serve_icon(filename):
    return send_from_directory(app.config['ICON_FOLDER'], filename)

@app.route('/manifest/<path:filename>')
def download_manifest(filename):
    return send_from_directory(app.config['MANIFEST_FOLDER'], filename,
                             mimetype='text/xml')

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