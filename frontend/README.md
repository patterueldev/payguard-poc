# PayGuard Frontend

A modern React web application for testing and interacting with the PayGuard fraud detection API.

## Features

✨ **Core Features:**
- 🔐 JWT Token Generation - Securely authenticate with the API
- 📤 Transaction Submission - Send transactions for fraud detection
- 📊 Real-time Results - View transaction processing status
- 🎯 Pre-built Scenarios - Quick test cases with common fraud patterns
- 📱 Responsive Design - Works on desktop and mobile devices

## Technology Stack

- **Framework**: React 18 with TypeScript
- **Build Tool**: Vite (lightning-fast development)
- **HTTP Client**: Axios
- **UI Icons**: Lucide React
- **Styling**: CSS3 with CSS Variables

## Prerequisites

- Node.js 16+ (for development)
- PayGuard API running on `localhost:8000`

## Installation

```bash
cd frontend
npm install
```

## Running the Application

### Development Mode

```bash
npm run dev
```

Opens automatically at `http://localhost:3000`

### Production Build

```bash
npm run build
```

Creates optimized build in `dist/` directory

### Preview Production Build

```bash
npm run preview
```

## API Integration

The frontend connects to the PayGuard API with these endpoints:

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/token` | POST | Generate JWT authentication token |
| `/transaction` | POST | Submit transaction for fraud analysis |
| `/health` | GET | Check API health status |

### Example API Call

```typescript
// Generate token
POST http://localhost:8000/token?user_id=user_123

// Submit transaction
POST http://localhost:8000/transaction
Headers: Authorization: Bearer <token>
Body: {
  "amount": 100.00,
  "merchant": "Starbucks",
  "description": "Coffee purchase"
}
```

## Using the Frontend

### 1. Generate Authentication Token

- Enter or accept the auto-generated User ID
- Click "Generate Token" button
- Token is now ready for API calls

### 2. Select a Test Scenario (Optional)

Choose from pre-built scenarios:
- **Normal Transaction**: $75.50 at Starbucks
- **Large Purchase**: $8,500 at unknown merchant
- **Grocery Shopping**: $120 at Target
- **Online Shopping**: $299.99 at Amazon
- **Gas Station**: $45.20 at Shell

Or manually enter transaction details.

### 3. Submit Transaction

- Enter amount, merchant, and description
- Click "Submit Transaction"
- View result in the Results section below

### 4. View Results

Transaction results display:
- Transaction ID (shortened for readability)
- Status (accepted)
- Submission timestamp

## Component Architecture

```
App.tsx
├── Authentication Section
│   ├── User ID input
│   ├── Token generation button
│   └── Token display
├── Transaction Section
│   ├── Preset scenarios
│   ├── Transaction form
│   │   ├── Amount input
│   │   ├── Merchant input
│   │   └── Description input
│   └── Submit button
├── Status Alerts
│   ├── Error messages
│   └── Success messages
├── Results Section
│   └── Transaction results list
└── API Info Section
    └── Connection status & endpoints
```

## State Management

The application uses React hooks for state:

```typescript
// Authentication state
const [auth, setAuth] = useState<AuthState>({
  token: null,
  userId: string,
  isAuthenticated: boolean
});

// Transaction form state
const [transaction, setTransaction] = useState<Transaction>({
  amount: number,
  merchant: string,
  description: string
});

// Results history
const [results, setResults] = useState<Result[]>([]);

// UI state
const [loading, setLoading] = useState(false);
const [error, setError] = useState<string | null>(null);
const [success, setSuccess] = useState<string | null>(null);
```

## Error Handling

The application handles common errors:

- **Connection Error**: "Failed to generate token. Is the API running?"
- **Auth Error**: "Please generate a token first"
- **API Errors**: Display server error messages

## Styling

The application uses:
- **CSS Variables** for consistent theming
- **CSS Grid** for responsive layouts
- **Flexbox** for component alignment
- **Transitions** for smooth interactions

### Color Palette

```css
--primary: #3b82f6        /* Blue */
--success: #10b981        /* Green */
--error: #ef4444          /* Red */
--warning: #f59e0b        /* Yellow */
--text: #1f2937           /* Dark Gray */
--bg: #f9fafb             /* Light Gray */
```

## Development

### Adding New Features

1. Create new components in `src/components/`
2. Import and use in `App.tsx`
3. Update styling in `src/App.css`

### Building for Production

```bash
npm run build
npm run preview
```

The `dist/` folder can be served by any static file server.

## Deployment

### Docker Deployment

Create `Dockerfile`:
```dockerfile
FROM node:18-alpine as build
WORKDIR /app
COPY . .
RUN npm ci && npm run build

FROM node:18-alpine
WORKDIR /app
RUN npm install -g serve
COPY --from=build /app/dist ./dist
EXPOSE 3000
CMD ["serve", "-s", "dist", "-l", "3000"]
```

Build and run:
```bash
docker build -t payguard-frontend .
docker run -p 3000:3000 payguard-frontend
```

### Vercel Deployment

```bash
npm install -g vercel
vercel
```

### Netlify Deployment

1. Connect GitHub repository
2. Set build command: `npm run build`
3. Set publish directory: `dist`

## Troubleshooting

### API Connection Issues

1. Verify API is running: `curl http://localhost:8000/health`
2. Check that port 8000 is not blocked
3. Ensure API CORS is configured (if running on different domain)

### Token Generation Fails

- Verify API is running and healthy
- Check browser console for detailed error messages
- Ensure User ID is not empty

### Transactions Not Submitting

- Verify token has been generated
- Check that merchant name is not empty
- Review browser console for API error messages

## API Documentation

Full API documentation available at `/Users/pat/Projects/PAT/payguard-poc/README_IMPLEMENTATION.md`

## Architecture Diagram

See `payguard_fraud_detection_flowchart.svg` for the complete system architecture.

## Performance

- **Initial Load**: < 1 second (Vite optimizations)
- **API Calls**: < 200ms (local network)
- **State Updates**: Instant (React optimization)

## Browser Support

- Chrome 90+
- Firefox 88+
- Safari 14+
- Edge 90+

## Future Enhancements

- [ ] Real-time transaction status polling
- [ ] Redis result lookup
- [ ] User profile visualization
- [ ] Transaction history export
- [ ] Dark mode
- [ ] Multi-user dashboard
- [ ] Advanced filtering and search

## Contributing

To improve the frontend:

1. Create a new branch
2. Make your changes
3. Test thoroughly
4. Submit a pull request

## License

Same as parent PayGuard project

---

**Quick Start Command:**
```bash
cd frontend && npm install && npm run dev
```

**API Base URL:** `http://localhost:8000`
**Frontend URL:** `http://localhost:3000`
