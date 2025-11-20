import { DefaultSession } from 'next-auth';

declare module 'next-auth' {
    interface Session {
        user: {
            id: string;
            role: string;
            org_id: string | null;
            org_role: string | null;
        } & DefaultSession['user'];
    }

    interface User {
        id: string;
        role: string;
        org_id: string | null;
        org_role: string | null;
    }
}

declare module 'next-auth/jwt' {
    interface JWT {
        id: string;
        role: string;
        org_id: string | null;
        org_role: string | null;
    }
}
