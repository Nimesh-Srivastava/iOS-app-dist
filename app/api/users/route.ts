import { NextRequest, NextResponse } from 'next/server';
import { getServerSession } from 'next-auth';
import { authOptions } from '@/lib/auth';
import dbConnect from '@/lib/db';
import User from '@/models/User';
import crypto from 'crypto';

// Helper to hash password using Werkzeug format
function hashPassword(password: string): string {
    const iterations = 600000;
    const salt = crypto.randomBytes(16).toString('hex');
    const hash = crypto.pbkdf2Sync(password, salt, iterations, 32, 'sha256').toString('hex');
    return `pbkdf2:sha256:${iterations}$${salt}$${hash}`;
}

// GET /api/users - List all users (primary_admin only)
export async function GET(request: NextRequest) {
    try {
        const session = await getServerSession(authOptions);

        if (!session || session.user.role !== 'primary_admin') {
            return NextResponse.json({ error: 'Unauthorized' }, { status: 403 });
        }

        await dbConnect();
        const users = await User.find({}).select('-password').sort({ username: 1 }).lean();

        return NextResponse.json(users);
    } catch (error) {
        console.error('Error fetching users:', error);
        return NextResponse.json({ error: 'Internal server error' }, { status: 500 });
    }
}

// POST /api/users - Create new user (primary_admin only)
export async function POST(request: NextRequest) {
    try {
        const session = await getServerSession(authOptions);

        if (!session || session.user.role !== 'primary_admin') {
            return NextResponse.json({ error: 'Unauthorized' }, { status: 403 });
        }

        const body = await request.json();
        const { username, password, role, org_id, org_role } = body;

        if (!username || !password) {
            return NextResponse.json({ error: 'Username and password are required' }, { status: 400 });
        }

        await dbConnect();

        // Check if user exists
        const existing = await User.findOne({ username });
        if (existing) {
            return NextResponse.json({ error: 'User already exists' }, { status: 400 });
        }

        // Hash password
        const hashedPassword = hashPassword(password);

        // Create user
        const user = await User.create({
            username,
            password: hashedPassword,
            role: role || 'user',
            org_id: org_id || null,
            org_role: org_role || null
        });

        // Return user without password
        const userObj = user.toObject();
        delete userObj.password;

        return NextResponse.json(userObj, { status: 201 });
    } catch (error) {
        console.error('Error creating user:', error);
        return NextResponse.json({ error: 'Internal server error' }, { status: 500 });
    }
}
