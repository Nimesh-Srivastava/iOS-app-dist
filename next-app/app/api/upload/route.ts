import { NextRequest, NextResponse } from 'next/server';
import { getServerSession } from 'next-auth';
import { authOptions } from '@/lib/auth';
import dbConnect from '@/lib/db';
import App from '@/models/App';
import { parseIpa } from '@/lib/ipa-parser';
import { v4 as uuidv4 } from 'uuid';
import mongoose from 'mongoose';

export async function POST(request: NextRequest) {
    const session = await getServerSession(authOptions);

    if (!session) {
        return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    }

    try {
        const formData = await request.formData();
        const file = formData.get('file') as File;
        const releaseNotes = formData.get('release_notes') as string;

        if (!file) {
            return NextResponse.json({ error: 'No file uploaded' }, { status: 400 });
        }

        const buffer = Buffer.from(await file.arrayBuffer());

        // Parse IPA
        const appInfo = await parseIpa(buffer);

        await dbConnect();

        // Generate IDs
        const fileId = uuidv4();
        const appId = appInfo.bundle_id || uuidv4(); // Use bundle_id as ID if available, else random
        // Actually, existing app uses 'id' field which seems to be a UUID or similar.
        // Let's check if app exists by bundle_id first to get its ID.

        let app = await App.findOne({ bundle_id: appInfo.bundle_id });
        let finalAppId = app ? app.id : uuidv4();

        // Save file to MongoDB (replicating existing schema)
        // Note: This has a 16MB limit. For larger files, we should use GridFS.
        // But to maintain compatibility with existing Python app, we use the same collection.
        const filesCollection = mongoose.connection.collection('files');
        await filesCollection.insertOne({
            file_id: fileId,
            filename: file.name,
            content_type: file.type || 'application/octet-stream',
            size: buffer.length,
            data: buffer, // Binary data
            upload_date: new Date().toISOString()
        });

        const newVersion = {
            version: appInfo.version,
            build_number: appInfo.build_number,
            filename: file.name,
            file_id: fileId,
            upload_date: new Date().toISOString(),
            release_notes: releaseNotes,
            size: buffer.length
        };

        if (app) {
            // Update existing app
            app.versions.push(newVersion);
            app.version = appInfo.version;
            app.build_number = appInfo.build_number;
            app.file_id = fileId;
            app.upload_date = new Date().toISOString();
            app.size = buffer.length;
            if (appInfo.icon) app.icon = appInfo.icon;

            await app.save();
        } else {
            // Create new app
            app = await App.create({
                id: finalAppId,
                name: appInfo.name,
                bundle_id: appInfo.bundle_id,
                version: appInfo.version,
                build_number: appInfo.build_number,
                icon: appInfo.icon,
                size: buffer.length,
                upload_date: new Date().toISOString(),
                creation_date: new Date().toISOString(),
                owner: session.user.name, // or username
                org_id: session.user.org_id,
                description: '',
                source: 'upload',
                versions: [newVersion],
                file_id: fileId
            });
        }

        return NextResponse.json({ success: true, appId: finalAppId });
    } catch (error) {
        console.error('Upload error:', error);
        return NextResponse.json({ error: 'Internal server error' }, { status: 500 });
    }
}
