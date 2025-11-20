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

// DELETE /api/users/[id] - Delete user (primary_admin only, cannot delete admin)
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

        const user = await User.findById(params.id);
        if (!user) {
            return NextResponse.json({ error: 'User not found' }, { status: 404 });
        }

        // Prevent deletion of primary_admin
        if (user.username === 'admin' || user.role === 'primary_admin') {
            return NextResponse.json({ error: 'Cannot delete primary admin user' }, { status: 403 });
        }

        await User.findByIdAndDelete(params.id);

        return NextResponse.json({ message: 'User deleted successfully' });
    } catch (error) {
        console.error('Error deleting user:', error);
        return NextResponse.json({ error: 'Internal server error' }, { status: 500 });
    }
}

// PATCH /api/users/[id] - Update user (primary_admin only)
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
        const { username, password, role, org_id, org_role } = body;

        await dbConnect();

        const user = await User.findById(params.id);
        if (!user) {
            return NextResponse.json({ error: 'User not found' }, { status: 404 });
        }

        // Prevent modification of primary_admin role
        if (user.username === 'admin' || user.role === 'primary_admin') {
            if (role && role !== 'primary_admin') {
                return NextResponse.json({ error: 'Cannot change primary admin role' }, { status: 403 });
            }
        }

        if (username) user.username = username;
        if (password) user.password = hashPassword(password);
        if (role) user.role = role;
        if (org_id !== undefined) user.org_id = org_id;
        if (org_role !== undefined) user.org_role = org_role;

        await user.save();

        // Return user without password
        const userObj = user.toObject();
        delete userObj.password;

        return NextResponse.json(userObj);
    } catch (error) {
        console.error('Error updating user:', error);
        return NextResponse.json({ error: 'Internal server error' }, { status: 500 });
    }
}
