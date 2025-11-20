import mongoose, { Schema, Document, Model } from 'mongoose';

export interface IUser extends Document {
    username: string;
    password?: string;
    role: 'primary_admin' | 'admin' | 'user';
    org_id?: string | null;
    org_role?: 'admin' | 'developer' | 'tester' | null;
    github_token?: string;
    profile_picture_id?: string;
}

const UserSchema: Schema<IUser> = new Schema({
    username: { type: String, required: true, unique: true },
    password: { type: String },
    role: {
        type: String,
        enum: ['primary_admin', 'admin', 'user'],
        default: 'user'
    },
    org_id: { type: String, default: null },
    org_role: {
        type: String,
        enum: ['admin', 'developer', 'tester', null],
        default: null
    },
    github_token: { type: String },
    profile_picture_id: { type: String },
});

// Prevent recompilation of model in development
const User: Model<IUser> = mongoose.models.User || mongoose.model<IUser>('User', UserSchema, 'users');

export default User;
