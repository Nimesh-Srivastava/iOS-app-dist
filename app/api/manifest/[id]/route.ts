import { NextRequest, NextResponse } from 'next/server';
import dbConnect from '@/lib/db';
import App from '@/models/App';

// GET /api/manifest/[id] - Generate iOS manifest plist
export async function GET(
    request: NextRequest,
    { params }: { params: { id: string } }
) {
    try {
        await dbConnect();

        const app = await App.findById(params.id);
        if (!app) {
            return NextResponse.json({ error: 'App not found' }, { status: 404 });
        }

        // Increment download count
        app.download_count = (app.download_count || 0) + 1;
        await app.save();

        const baseUrl = process.env.NEXT_PUBLIC_BASE_URL || 'http://localhost:3000';
        const ipaUrl = app.file_path?.startsWith('http')
            ? app.file_path
            : `${baseUrl}${app.file_path}`;

        const iconUrl = app.icon?.startsWith('http')
            ? app.icon
            : app.icon
                ? `${baseUrl}${app.icon}`
                : '';

        // Generate plist manifest for iOS OTA installation
        const manifest = `<?xml version="1.0" encoding="UTF-8"?>
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
                    <string>${ipaUrl}</string>
                </dict>
                ${iconUrl ? `<dict>
                    <key>kind</key>
                    <string>display-image</string>
                    <key>url</key>
                    <string>${iconUrl}</string>
                </dict>
                <dict>
                    <key>kind</key>
                    <string>full-size-image</string>
                    <key>url</key>
                    <string>${iconUrl}</string>
                </dict>` : ''}
            </array>
            <key>metadata</key>
            <dict>
                <key>bundle-identifier</key>
                <string>${app.bundle_id || 'com.example.app'}</string>
                <key>bundle-version</key>
                <string>${app.version || '1.0'}</string>
                <key>kind</key>
                <string>software</string>
                <key>title</key>
                <string>${app.name}</string>
            </dict>
        </dict>
    </array>
</dict>
</plist>`;

        return new NextResponse(manifest, {
            headers: {
                'Content-Type': 'application/xml',
                'Content-Disposition': `attachment; filename="${app.name}.plist"`,
            },
        });
    } catch (error) {
        console.error('Error generating manifest:', error);
        return NextResponse.json({ error: 'Internal server error' }, { status: 500 });
    }
}
