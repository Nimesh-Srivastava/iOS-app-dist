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
