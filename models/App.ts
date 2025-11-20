import mongoose, { Schema, Document, Model } from 'mongoose';

export interface IVersion {
    version: string;
    build_number: string;
    filename: string;
    file_id: string;
    upload_date: string;
    release_notes?: string;
    size?: number;
}

export interface IApp extends Document {
    id: string;
    name: string;
    bundle_id?: string;
    version: string;
    build_number: string;
    icon?: string;
    size?: number;
    upload_date?: string;
    creation_date?: string;
    owner?: string;
    org_id?: string;
    description?: string;
    source?: string; // e.g., 'github'
    versions: IVersion[];
    file_id?: string; // Main file ID (usually latest)
}

const VersionSchema = new Schema({
    version: String,
    build_number: String,
    filename: String,
    file_id: String,
    upload_date: String,
    release_notes: String,
    size: Number
}, { _id: false });

const AppSchema: Schema<IApp> = new Schema({
    id: { type: String, required: true, unique: true },
    name: { type: String, required: true },
    bundle_id: String,
    version: String,
    build_number: String,
    icon: String,
    size: Number,
    upload_date: String,
    creation_date: String,
    owner: String,
    org_id: String,
    description: String,
    source: String,
    versions: [VersionSchema],
    file_id: String
});

const App: Model<IApp> = mongoose.models.App || mongoose.model<IApp>('App', AppSchema, 'apps');

export default App;
