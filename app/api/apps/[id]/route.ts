import { NextRequest, NextResponse } from 'next/server';
import { getServerSession } from 'next-auth';
import { authOptions } from '@/lib/auth';
import dbConnect from '@/lib/db';
import App from '@/models/App';

// DELETE /api/apps/[id] - Delete app
export async function DELETE(
    request: NextRequest,
    { params }: { params: { id: string } }
) {
    try {
        const session = await getServerSession(authOptions);

        if (!session) {
            return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
        }

        await dbConnect();

        const app = await App.findById(params.id);
        if (!app) {
            return NextResponse.json({ error: 'App not found' }, { status: 404 });
        }

        await App.findByIdAndDelete(params.id);

        return NextResponse.json({ message: 'App deleted successfully' });
    } catch (error) {
        console.error('Error deleting app:', error);
        return NextResponse.json({ error: 'Internal server error' }, { status: 500 });
    }
}

// PATCH /api/apps/[id] - Update app
export async function PATCH(
    request: NextRequest,
    { params }: { params: { id: string } }
) {
    try {
        const session = await getServerSession(authOptions);

        if (!session) {
            return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
        }

        const body = await request.json();
        const { name, version, bundle_id, min_ios_version } = body;

        await dbConnect();

        const app = await App.findById(params.id);
        if (!app) {
            return NextResponse.json({ error: 'App not found' }, { status: 404 });
        }

        if (name) app.name = name;
        if (version) app.version = version;
        if (bundle_id) app.bundle_id = bundle_id;
        if (min_ios_version) app.min_ios_version = min_ios_version;

        await app.save();

        return NextResponse.json(app);
    } catch (error) {
        console.error('Error updating app:', error);
        return NextResponse.json({ error: 'Internal server error' }, { status: 500 });
    }
}
