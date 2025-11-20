import { NextRequest, NextResponse } from 'next/server';
import { getServerSession } from 'next-auth';
import { authOptions } from '@/lib/auth';
import dbConnect from '@/lib/db';
import Organization from '@/models/Organization';
import User from '@/models/User';

// GET /api/organizations - List all organizations (primary_admin only)
export async function GET(request: NextRequest) {
    try {
        const session = await getServerSession(authOptions);

        if (!session || session.user.role !== 'primary_admin') {
            return NextResponse.json({ error: 'Unauthorized' }, { status: 403 });
        }

        await dbConnect();
        const organizations = await Organization.find({}).sort({ created_at: -1 }).lean();

        // Get member counts for each organization
        const orgsWithCounts = await Promise.all(
            organizations.map(async (org) => {
                const memberCount = await User.countDocuments({ org_id: org.id });
                return {
                    ...org,
                    memberCount
                };
            })
        );

        return NextResponse.json(orgsWithCounts);
    } catch (error) {
        console.error('Error fetching organizations:', error);
        return NextResponse.json({ error: 'Internal server error' }, { status: 500 });
    }
}

// POST /api/organizations - Create new organization (primary_admin only)
export async function POST(request: NextRequest) {
    try {
        const session = await getServerSession(authOptions);

        if (!session || session.user.role !== 'primary_admin') {
            return NextResponse.json({ error: 'Unauthorized' }, { status: 403 });
        }

        const body = await request.json();
        const { name, description } = body;

        if (!name) {
            return NextResponse.json({ error: 'Name is required' }, { status: 400 });
        }

        await dbConnect();

        // Check if organization with same name exists
        const existing = await Organization.findOne({ name });
        if (existing) {
            return NextResponse.json({ error: 'Organization with this name already exists' }, { status: 400 });
        }

        // Generate unique ID
        const id = `org_${Date.now()}_${Math.random().toString(36).substring(7)}`;

        const organization = await Organization.create({
            id,
            name,
            description: description || '',
            created_by: session.user.id
        });

        return NextResponse.json(organization, { status: 201 });
    } catch (error) {
        console.error('Error creating organization:', error);
        return NextResponse.json({ error: 'Internal server error' }, { status: 500 });
    }
}
