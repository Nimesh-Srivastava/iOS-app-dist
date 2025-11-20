import { NextAuthOptions } from 'next-auth';
import CredentialsProvider from 'next-auth/providers/credentials';
import dbConnect from '@/lib/db';
import User from '@/models/User';
import crypto from 'crypto';

// Helper to verify Werkzeug pbkdf2:sha256 hashes
// Format: pbkdf2:sha256:iterations$salt$hash
function verifyPassword(password: string, hash: string): boolean {
    try {
        console.log('[AUTH] Verifying password...');
        console.log('[AUTH] Hash format:', hash?.substring(0, 60));

        if (!hash) {
            console.log('[AUTH] No hash provided');
            return false;
        }

        // Werkzeug format: method:digest:iterations$salt$hash
        // Example: pbkdf2:sha256:600000$salt$hash
        const parts = hash.split('$');
        console.log('[AUTH] Hash parts (split by $):', parts.length);

        if (parts.length !== 3) {
            console.log('[AUTH] Invalid hash format - expected 3 parts separated by $');
            return false;
        }

        const methodPart = parts[0]; // e.g., "pbkdf2:sha256:600000"
        const salt = parts[1];
        const originalHash = parts[2];

        console.log('[AUTH] Method part:', methodPart);
        console.log('[AUTH] Salt length:', salt?.length);
        console.log('[AUTH] Hash length:', originalHash?.length);

        // Parse method part
        const methodParts = methodPart.split(':');
        if (methodParts.length !== 3) {
            console.log('[AUTH] Invalid method format');
            return false;
        }

        const [method, digest, iterationsStr] = methodParts;
        const iterations = parseInt(iterationsStr, 10);

        console.log('[AUTH] Method:', method);
        console.log('[AUTH] Digest:', digest);
        console.log('[AUTH] Iterations:', iterations);

        if (method !== 'pbkdf2' || digest !== 'sha256') {
            console.log('[AUTH] Unsupported method or digest');
            return false;
        }

        // Generate hash using the same parameters
        const key = crypto.pbkdf2Sync(password, salt, iterations, 32, 'sha256');
        const newHash = key.toString('hex');

        console.log('[AUTH] Generated hash:', newHash);
        console.log('[AUTH] Original hash: ', originalHash);
        console.log('[AUTH] Hashes match:', newHash === originalHash);

        const isValid = newHash === originalHash;
        console.log('[AUTH] Password valid:', isValid);
        return isValid;
    } catch (error) {
        console.error('[AUTH] Error verifying password:', error);
        return false;
    }
}

export const authOptions: NextAuthOptions = {
    providers: [
        CredentialsProvider({
            name: 'Credentials',
            credentials: {
                username: { label: "Username", type: "text" },
                password: { label: "Password", type: "password" }
            },
            async authorize(credentials) {
                console.log('[AUTH] ========== LOGIN ATTEMPT ==========');
                console.log('[AUTH] Username:', credentials?.username);

                if (!credentials?.username || !credentials?.password) {
                    console.log('[AUTH] Missing credentials');
                    return null;
                }

                await dbConnect();
                console.log('[AUTH] Database connected');

                const user = await User.findOne({ username: credentials.username });
                console.log('[AUTH] User found:', !!user);

                if (!user) {
                    console.log('[AUTH] User not found in database');
                    return null;
                }

                if (!user.password) {
                    console.log('[AUTH] User has no password set');
                    return null;
                }

                console.log('[AUTH] Attempting password verification...');
                const isValid = verifyPassword(credentials.password, user.password);

                if (!isValid) {
                    console.log('[AUTH] Password verification FAILED');
                    return null;
                }

                console.log('[AUTH] Login SUCCESSFUL for:', user.username);
                console.log('[AUTH] ====================================');

                return {
                    id: user._id.toString(),
                    name: user.username,
                    email: user.username, // We use username as email for NextAuth compatibility
                    image: user.profile_picture_id,
                    role: user.role,
                    org_id: user.org_id,
                    org_role: user.org_role
                };
            }
        })
    ],
    callbacks: {
        async jwt({ token, user }) {
            if (user) {
                token.role = user.role;
                token.org_id = user.org_id;
                token.org_role = user.org_role;
                token.id = user.id;
            }
            return token;
        },
        async session({ session, token }) {
            if (session.user) {
                session.user.role = token.role as string;
                session.user.org_id = token.org_id as string | null;
                session.user.org_role = token.org_role as string | null;
                session.user.id = token.id as string;
            }
            return session;
        }
    },
    pages: {
        signIn: '/login',
    },
    session: {
        strategy: 'jwt',
    },
    secret: process.env.NEXTAUTH_SECRET,
};
