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
    version: string;
    bundle_id?: string;
    build_number?: string;
    min_ios_version?: string;
    size?: number;
    icon?: string;
    upload_date?: string;
    creation_date?: string;
    source?: string;
    github_repo?: string;
    file_path?: string;
    download_count?: number;
    description?: string;
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
    version: { type: String, required: true },
    bundle_id: String,
    build_number: String,
    min_ios_version: String,
    size: Number,
    icon: String,
    upload_date: String,
    creation_date: String,
    source: String,
    github_repo: String,
    file_path: String,
    download_count: { type: Number, default: 0 },
    description: String,
    versions: [VersionSchema],
    file_id: String
});

const App: Model<IApp> = mongoose.models.App || mongoose.model<IApp>('App', AppSchema, 'apps');

export default App;
