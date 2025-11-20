# iOS App Distribution Platform - v3 (Next.js)

Modern, full-stack iOS app distribution platform built with Next.js 16, TypeScript, and MongoDB.

## Features

- 🚀 **Next.js 16** with App Router and Server Components
- 🔐 **NextAuth.js** authentication with existing user database
- 🎨 **Futuristic UI** with Tailwind CSS and Framer Motion
- 📱 **IPA Upload** with automatic parsing and metadata extraction
- 🗄️ **MongoDB** database (shared with Flask v2.x)
- 💎 **TypeScript** for type safety
- ✨ **Glassmorphism** design with smooth animations

## Tech Stack

- **Framework**: Next.js 16.0.3 (App Router, Turbopack)
- **Language**: TypeScript 5
- **Database**: MongoDB (Mongoose 8.20.0)
- **Authentication**: NextAuth.js 4.24.13
- **Styling**: Tailwind CSS 3
- **Animations**: Framer Motion 12.23.24
- **Icons**: Lucide React 0.554.0
- **File Parsing**: adm-zip, plist

## Getting Started

### Prerequisites

- Node.js 18+ and npm
- MongoDB Atlas account (or local MongoDB)
- Existing user database from Flask v2.x (optional)

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/Nimesh-Srivastava/iOS-app-dist.git
   cd iOS-app-dist
   git checkout v3
   ```

2. **Install dependencies**
   ```bash
   npm install
   ```

3. **Configure environment variables**
   
   Create `.env.local` file:
   ```env
   MONGODB_URI=mongodb+srv://your-connection-string
   DB_NAME=app_distribution
   NEXTAUTH_SECRET=your-secret-key-here
   NEXTAUTH_URL=http://localhost:3000
   ```

4. **Run development server**
   ```bash
   npm run dev
   ```

5. **Open in browser**
   
   Navigate to [http://localhost:3000](http://localhost:3000)

### Default Login

If using the existing database:
- **Username**: `admin`
- **Password**: Your configured admin password

## Project Structure

```
├── app/                    # Next.js App Router
│   ├── (auth)/            # Authentication routes
│   │   └── login/         # Login page
│   ├── (dashboard)/       # Protected dashboard routes
│   │   ├── apps/[id]/     # App detail page
│   │   ├── upload/        # Upload page
│   │   └── page.tsx       # Dashboard home
│   ├── api/               # API routes
│   │   ├── auth/          # NextAuth endpoints
│   │   └── upload/        # File upload endpoint
│   ├── globals.css        # Global styles
│   └── layout.tsx         # Root layout
├── components/            # React components
│   ├── AppCard.tsx        # App card component
│   └── Navbar.tsx         # Navigation bar
├── lib/                   # Utilities
│   ├── auth.ts            # NextAuth configuration
│   ├── db.ts              # MongoDB connection
│   └── ipa-parser.ts      # IPA file parser
├── models/                # Mongoose models
│   ├── User.ts            # User model
│   ├── App.ts             # App model
│   └── Organization.ts    # Organization model
└── types/                 # TypeScript types
    └── next-auth.d.ts     # NextAuth type extensions
```

## Available Scripts

- `npm run dev` - Start development server
- `npm run build` - Build for production
- `npm start` - Start production server
- `npm run lint` - Run ESLint

## Database Compatibility

This v3 Next.js app uses the **same MongoDB database** as the Flask v2.x application. All user data, apps, and organizations are shared between versions.

### Password Compatibility

The authentication system is compatible with Werkzeug password hashes from Flask, using the format:
```
pbkdf2:sha256:iterations$salt$hash
```

## Migration from v2.x

The v3 branch contains only the Next.js application. The Flask v2.x code remains on branches:
- `v2.2.1` - Latest Flask version
- `main` - Original Flask implementation

Both applications can run simultaneously on different ports and share the same database.

## Deployment

### Vercel (Recommended)

1. Push to GitHub
2. Import project in Vercel
3. Configure environment variables
4. Deploy

### Manual Deployment

```bash
npm run build
npm start
```

## Features Implemented

✅ User authentication (NextAuth.js)  
✅ App library with grid display  
✅ App detail page with version history  
✅ IPA file upload and parsing  
✅ Glassmorphism UI design  
✅ Framer Motion animations  
✅ Responsive layout  
✅ Organization-aware data access  
✅ Type-safe codebase  

## Roadmap

- [ ] GitHub build integration
- [ ] Comment system for app versions
- [ ] Notification system
- [ ] User profile management
- [ ] App sharing functionality
- [ ] Download/install endpoints
- [ ] GridFS for large file storage
- [ ] Comprehensive testing

## License

MIT

## Support

For issues and questions, please open an issue on GitHub.
