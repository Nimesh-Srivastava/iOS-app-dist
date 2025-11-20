import AdmZip from 'adm-zip';
import { parse } from 'plist';

interface AppInfo {
    name: string;
    version: string;
    build_number: string;
    bundle_id: string;
    icon?: string; // Base64 encoded icon
    expiration_date?: Date;
}

export async function parseIpa(buffer: Buffer): Promise<AppInfo> {
    const zip = new AdmZip(buffer);
    const zipEntries = zip.getEntries();

    // Find Info.plist
    const infoPlistEntry = zipEntries.find(entry =>
        entry.entryName.match(/^Payload\/[^/]+\.app\/Info\.plist$/)
    );

    if (!infoPlistEntry) {
        throw new Error('Invalid IPA: Info.plist not found');
    }

    // Parse Info.plist
    const infoPlistData = infoPlistEntry.getData().toString('utf8');

    // We need a plist parser. 'plist' package is good.
    // If we don't have it, we might need to install it.
    // For now, let's assume we can parse simple XML or binary plist.
    // Actually, binary plist parsing is hard without a library.
    // I should install 'plist' or 'simple-plist'.

    // Let's assume we installed 'plist' package as well.
    const info = parse(infoPlistData) as any;

    // Find Icon
    let iconBase64: string | undefined;

    // Try to find the largest icon
    if (info.CFBundleIconFiles && Array.isArray(info.CFBundleIconFiles)) {
        // This logic is simplified. In reality, we'd look for specific sizes.
        const iconName = info.CFBundleIconFiles[info.CFBundleIconFiles.length - 1];
        const iconEntry = zipEntries.find(entry =>
            entry.entryName.includes(iconName) && !entry.entryName.includes('.png') // Usually just name without extension in plist
        ) || zipEntries.find(entry =>
            entry.entryName.includes(iconName + '.png')
        ) || zipEntries.find(entry =>
            entry.entryName.includes(iconName + '@2x.png')
        );

        if (iconEntry) {
            const iconBuffer = iconEntry.getData();
            iconBase64 = `data:image/png;base64,${iconBuffer.toString('base64')}`;
        }
    }

    return {
        name: info.CFBundleDisplayName || info.CFBundleName || 'Unknown App',
        version: info.CFBundleShortVersionString || '1.0',
        build_number: info.CFBundleVersion || '1',
        bundle_id: info.CFBundleIdentifier || '',
        icon: iconBase64,
    };
}
