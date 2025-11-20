'use client';

import { useState, useRef } from 'react';
import { useRouter } from 'next/navigation';
import { motion } from 'framer-motion';
import { Upload, File, X, CheckCircle, AlertCircle, Loader2 } from 'lucide-react';

export default function UploadPage() {
    const router = useRouter();
    const [file, setFile] = useState<File | null>(null);
    const [dragActive, setDragActive] = useState(false);
    const [uploading, setUploading] = useState(false);
    const [progress, setProgress] = useState(0);
    const [error, setError] = useState('');
    const [releaseNotes, setReleaseNotes] = useState('');
    const inputRef = useRef<HTMLInputElement>(null);

    const handleDrag = (e: React.DragEvent) => {
        e.preventDefault();
        e.stopPropagation();
        if (e.type === 'dragenter' || e.type === 'dragover') {
            setDragActive(true);
        } else if (e.type === 'dragleave') {
            setDragActive(false);
        }
    };

    const handleDrop = (e: React.DragEvent) => {
        e.preventDefault();
        e.stopPropagation();
        setDragActive(false);

        if (e.dataTransfer.files && e.dataTransfer.files[0]) {
            validateAndSetFile(e.dataTransfer.files[0]);
        }
    };

    const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        e.preventDefault();
        if (e.target.files && e.target.files[0]) {
            validateAndSetFile(e.target.files[0]);
        }
    };

    const validateAndSetFile = (file: File) => {
        if (!file.name.endsWith('.ipa')) {
            setError('Please upload a valid .ipa file');
            return;
        }
        setError('');
        setFile(file);
    };

    const removeFile = () => {
        setFile(null);
        setError('');
        if (inputRef.current) {
            inputRef.current.value = '';
        }
    };

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!file) return;

        setUploading(true);
        setProgress(0);

        const formData = new FormData();
        formData.append('file', file);
        formData.append('release_notes', releaseNotes);

        try {
            // We'll implement this API route next
            const xhr = new XMLHttpRequest();
            xhr.open('POST', '/api/upload', true);

            xhr.upload.onprogress = (event) => {
                if (event.lengthComputable) {
                    const percentComplete = (event.loaded / event.total) * 100;
                    setProgress(percentComplete);
                }
            };

            xhr.onload = () => {
                if (xhr.status === 200) {
                    const response = JSON.parse(xhr.responseText);
                    router.push(`/apps/${response.appId}`);
                    router.refresh();
                } else {
                    setError('Upload failed. Please try again.');
                    setUploading(false);
                }
            };

            xhr.onerror = () => {
                setError('Network error occurred.');
                setUploading(false);
            };

            xhr.send(formData);
        } catch (err) {
            setError('An error occurred during upload.');
            setUploading(false);
        }
    };

    return (
        <div className="max-w-2xl mx-auto">
            <div className="mb-8">
                <h1 className="text-3xl font-bold text-white mb-2">Upload App</h1>
                <p className="text-slate-400">Upload a new iOS application or update an existing one</p>
            </div>

            <div className="glass-card p-8">
                <form onSubmit={handleSubmit}>
                    {/* Drag and Drop Zone */}
                    <div
                        className={`relative border-2 border-dashed rounded-2xl p-10 text-center transition-all duration-300 ${dragActive
                                ? 'border-indigo-500 bg-indigo-500/10'
                                : file
                                    ? 'border-emerald-500/50 bg-emerald-500/5'
                                    : 'border-slate-700 hover:border-slate-500 hover:bg-slate-800/50'
                            }`}
                        onDragEnter={handleDrag}
                        onDragLeave={handleDrag}
                        onDragOver={handleDrag}
                        onDrop={handleDrop}
                    >
                        <input
                            ref={inputRef}
                            type="file"
                            className="hidden"
                            accept=".ipa"
                            onChange={handleChange}
                            disabled={uploading}
                        />

                        {file ? (
                            <div className="flex flex-col items-center">
                                <div className="w-16 h-16 bg-emerald-500/20 rounded-full flex items-center justify-center mb-4">
                                    <File className="w-8 h-8 text-emerald-400" />
                                </div>
                                <h3 className="text-lg font-medium text-white mb-1">{file.name}</h3>
                                <p className="text-sm text-slate-400 mb-4">
                                    {(file.size / (1024 * 1024)).toFixed(2)} MB
                                </p>
                                {!uploading && (
                                    <button
                                        type="button"
                                        onClick={removeFile}
                                        className="text-red-400 hover:text-red-300 text-sm flex items-center transition-colors"
                                    >
                                        <X className="w-4 h-4 mr-1" />
                                        Remove file
                                    </button>
                                )}
                            </div>
                        ) : (
                            <div className="flex flex-col items-center">
                                <div className="w-16 h-16 bg-indigo-500/20 rounded-full flex items-center justify-center mb-4">
                                    <Upload className="w-8 h-8 text-indigo-400" />
                                </div>
                                <h3 className="text-lg font-medium text-white mb-1">
                                    Drag and drop your .ipa file
                                </h3>
                                <p className="text-sm text-slate-400 mb-6">
                                    or click to browse from your computer
                                </p>
                                <button
                                    type="button"
                                    onClick={() => inputRef.current?.click()}
                                    className="bg-indigo-600 hover:bg-indigo-500 text-white px-6 py-2 rounded-xl font-medium transition-colors"
                                >
                                    Browse Files
                                </button>
                            </div>
                        )}
                    </div>

                    {error && (
                        <motion.div
                            initial={{ opacity: 0, height: 0 }}
                            animate={{ opacity: 1, height: 'auto' }}
                            className="mt-6 bg-red-500/10 border border-red-500/20 text-red-400 px-4 py-3 rounded-xl flex items-center"
                        >
                            <AlertCircle className="w-5 h-5 mr-2 flex-shrink-0" />
                            {error}
                        </motion.div>
                    )}

                    {/* Release Notes */}
                    <div className="mt-6">
                        <label htmlFor="release_notes" className="block text-sm font-medium text-slate-300 mb-2">
                            Release Notes (Optional)
                        </label>
                        <textarea
                            id="release_notes"
                            rows={4}
                            className="w-full bg-slate-900/60 border border-white/10 text-white rounded-xl px-4 py-3 focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 outline-none transition-all resize-none"
                            placeholder="What's new in this version?"
                            value={releaseNotes}
                            onChange={(e) => setReleaseNotes(e.target.value)}
                            disabled={uploading}
                        />
                    </div>

                    {/* Progress Bar */}
                    {uploading && (
                        <div className="mt-6">
                            <div className="flex justify-between text-sm text-slate-400 mb-2">
                                <span>Uploading...</span>
                                <span>{Math.round(progress)}%</span>
                            </div>
                            <div className="w-full bg-slate-700 rounded-full h-2 overflow-hidden">
                                <motion.div
                                    className="bg-indigo-500 h-full rounded-full"
                                    initial={{ width: 0 }}
                                    animate={{ width: `${progress}%` }}
                                    transition={{ duration: 0.2 }}
                                />
                            </div>
                        </div>
                    )}

                    {/* Submit Button */}
                    <div className="mt-8 flex justify-end">
                        <button
                            type="submit"
                            disabled={!file || uploading}
                            className="bg-gradient-to-r from-indigo-600 to-purple-600 text-white px-8 py-3 rounded-xl font-semibold shadow-lg shadow-indigo-500/30 hover:shadow-indigo-500/50 transition-all duration-300 disabled:opacity-50 disabled:cursor-not-allowed flex items-center"
                        >
                            {uploading ? (
                                <>
                                    <Loader2 className="w-5 h-5 mr-2 animate-spin" />
                                    Processing...
                                </>
                            ) : (
                                <>
                                    Upload App
                                    <Upload className="w-5 h-5 ml-2" />
                                </>
                            )}
                        </button>
                    </div>
                </form>
            </div>
        </div>
    );
}
