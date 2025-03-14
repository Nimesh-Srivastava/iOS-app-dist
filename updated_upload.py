@app.route('/upload', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'POST':
        try:
            # Validate files
            if 'ipa' not in request.files or 'icon' not in request.files:
                return "Both IPA and icon files are required", 400

            ipa_file = request.files['ipa']
            icon_file = request.files['icon']

            # Validate form fields
            if not all(k in request.form for k in ['app_name', 'app_version']):
                return "All form fields are required", 400

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

            # Read IPA file
            ipa_stream = ipa_file.stream.read()
            if not ipa_stream:
                return "Empty IPA file", 400

            # Extract app info
            app_info = extract_app_info(BytesIO(ipa_stream))
            if not app_info:
                return "Failed to extract app info from IPA", 400

            # Generate unique IDs
            app_id = str(uuid.uuid4())
            bundle_id = app_info['bundle_id']

            # Initialize Azure client with custom SSL context
            blob_service_client = BlobServiceClient.from_connection_string(
                app.config['AZURE_STORAGE_CONNECTION_STRING'],
                connection_verify=False
            )
            container_client = blob_service_client.get_container_client(
                app.config['AZURE_CONTAINER_NAME'])

            # Upload files
            ipa_url = azure_upload(container_client, f"ipas/{app_id}.ipa", BytesIO(ipa_stream), 'application/octet-stream')
            icon_url = azure_upload(container_client, f"icons/{app_id}.png", icon_file.stream, 'image/png')

            # Create metadata
            metadata = {
                'bundle_id': bundle_id,
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

            # Handle existing versions
            metadata_blob = f"metadata/{bundle_id}.json"
            if container_client.get_blob_client(metadata_blob).exists():
                existing = json.loads(container_client.get_blob_client(metadata_blob).download_blob().readall())
                metadata['versions'].update(existing.get('versions', {}))

            # Generate and upload manifest
            manifest = generate_manifest(app_info, ipa_url, icon_url)
            azure_upload(container_client, f"manifests/{app_id}.plist", BytesIO(manifest.encode()), 'text/xml')

            # Save metadata
            azure_upload(container_client, metadata_blob, BytesIO(json.dumps(metadata).encode()), 'application/json')

            return redirect(url_for('index'))

        except Exception as e:
            app.logger.error(f"Upload error: {str(e)}", exc_info=True)
            return f"Upload failed: {str(e)}", 500

    return render_template('upload.html')
