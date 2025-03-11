@app.route('/')
def index():
    apps = []
    try:
        metadata_blobs = container_client.list_blobs(name_starts_with='metadata/')
        for blob in metadata_blobs:
            blob_client = container_client.get_blob_client(blob.name)
            metadata = json.loads(blob_client.download_blob().readall())
            
            if not metadata.get('versions'):
                continue

            # Get the latest version
            versions = sorted(metadata['versions'].values(),
                            key=lambda v: version.parse(v['version']),
                            reverse=True)
            latest = versions[0]

            apps.append({
                'bundle_id': metadata['bundle_id'],
                'name': metadata.get('display_name', 'Unnamed App'),
                'version': latest['version'],
                'icon_url': latest['icon_url'],
                'size': latest['size'],
                'uploaded_at': latest['uploaded_at']
            })

    except Exception as e:
        app.logger.error(f"Error loading apps: {str(e)}")
    
    return render_template('index.html', apps=apps)
