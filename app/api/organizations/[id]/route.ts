import { NextRequest, NextResponse } from 'next/server';
import { getServerSession } from 'next-auth';
import { authOptions } from '@/lib/auth';
import dbConnect from '@/lib/db';
import Organization from '@/models/Organization';

// DELETE /api/organizations/[id] - Delete organization (primary_admin only)
export async function DELETE(
    request: NextRequest,
    { params }: { params: { id: string } }
) {
    try {
        const session = await getServerSession(authOptions);

        if (!session || session.user.role !== 'primary_admin') {
            return NextResponse.json({ error: 'Unauthorized' }, { status: 403 });
        }

        await dbConnect();

        const organization = await Organization.findOne({ id: params.id });
        if (!organization) {
            return NextResponse.json({ error: 'Organization not found' }, { status: 404 });
        }

        await Organization.deleteOne({ id: params.id });

        return NextResponse.json({ message: 'Organization deleted successfully' });
    } catch (error) {
        console.error('Error deleting organization:', error);
        return NextResponse.json({ error: 'Internal server error' }, { status: 500 });
    }
}

// PATCH /api/organizations/[id] - Update organization (primary_admin only)
export async function PATCH(
    request: NextRequest,
    { params }: { params: { id: string } }
) {
    try {
        const session = await getServerSession(authOptions);

        if (!session || session.user.role !== 'primary_admin') {
            return NextResponse.json({ error: 'Unauthorized' }, { status: 403 });
        }

        const body = await request.json();
        const { name, description } = body;

        await dbConnect();

        const organization = await Organization.findOne({ id: params.id });
        if (!organization) {
            return NextResponse.json({ error: 'Organization not found' }, { status: 404 });
        }

        if (name) organization.name = name;
        if (description !== undefined) organization.description = description;

        await organization.save();

        return NextResponse.json(organization);
    } catch (error) {
        console.error('Error updating organization:', error);
        return NextResponse.json({ error: 'Internal server error' }, { status: 500 });
    }
}
