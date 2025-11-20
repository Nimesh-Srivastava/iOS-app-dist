import mongoose, { Schema, Document, Model } from 'mongoose';

export interface IOrganization extends Document {
    id: string;
    name: string;
    description?: string;
    created_at: string;
    created_by: string;
}

const OrganizationSchema: Schema<IOrganization> = new Schema({
    id: { type: String, required: true, unique: true },
    name: { type: String, required: true, unique: true },
    description: String,
    created_at: { type: String, default: () => new Date().toISOString() },
    created_by: { type: String, required: true }
});

const Organization: Model<IOrganization> = mongoose.models.Organization || mongoose.model<IOrganization>('Organization', OrganizationSchema, 'organizations');

export default Organization;
