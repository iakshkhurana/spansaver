# SpanSaver Mission Control - Deployment Guide

## Quick Start

### Using Vercel (Recommended)

1. **Connect GitHub Repository**
   ```bash
   git init
   git add .
   git commit -m "Initial commit: SpanSaver Mission Control"
   git push origin main
   ```

2. **Deploy to Vercel**
   - Visit [vercel.com](https://vercel.com)
   - Click "New Project"
   - Select your repository
   - Configure environment variables:
     ```
     NEXT_PUBLIC_USE_MOCK=true  # or false for production API
     NEXT_PUBLIC_API_BASE=https://api.spansaver.io
     ```
   - Click "Deploy"

3. **Your app is live!**
   - Vercel will automatically rebuild on every push
   - Access your dashboard at your Vercel URL

### Manual Deployment

1. **Build the project**
   ```bash
   pnpm build
   ```

2. **Start production server**
   ```bash
   pnpm start
   ```

3. **Access at**
   ```
   http://localhost:3000
   ```

## Environment Variables

### Development (.env.local)
```bash
NEXT_PUBLIC_USE_MOCK=true
```

### Production (.env.production)
```bash
NEXT_PUBLIC_USE_MOCK=false
NEXT_PUBLIC_API_BASE=https://api.spansaver.io
```

## Docker Deployment

1. **Build Docker image**
   ```bash
   docker build -t spansaver-mission-control .
   ```

2. **Run container**
   ```bash
   docker run -p 3000:3000 -e NEXT_PUBLIC_USE_MOCK=true spansaver-mission-control
   ```

## Performance Optimization

### Next.js Optimizations
- Image optimization enabled
- Font optimization with next/font
- Automatic code splitting
- React Compiler support (v16)

### Deployment Checklist
- [ ] Set production API endpoint
- [ ] Disable mock data (`NEXT_PUBLIC_USE_MOCK=false`)
- [ ] Configure CORS headers if needed
- [ ] Set up monitoring and error tracking
- [ ] Enable caching headers
- [ ] Configure CDN for static assets
- [ ] Set up database connection
- [ ] Configure authentication if needed

## Scaling Considerations

### Database
- Currently uses mock data
- For production, integrate with:
  - PostgreSQL with Neon
  - MongoDB with Atlas
  - Firebase Realtime Database

### Caching
- Cache findings data with 5-minute TTL
- Use Redis for session management
- Implement Next.js data revalidation

### Load Balancing
- Vercel automatically handles load balancing
- For self-hosted: use Nginx/HAProxy
- Enable HTTP/2 and gzip compression

## Monitoring

### Key Metrics
- **FCP** (First Contentful Paint) - Target: < 1.5s
- **LCP** (Largest Contentful Paint) - Target: < 2.5s
- **CLS** (Cumulative Layout Shift) - Target: < 0.1
- **INP** (Interaction to Next Paint) - Target: < 200ms

### Error Tracking
```bash
# Add Sentry integration
npm install @sentry/nextjs
```

### Analytics
```bash
# Already included
@vercel/analytics
```

## CI/CD Pipeline

### GitHub Actions Example
```yaml
name: Deploy

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: pnpm/action-setup@v2
      - uses: actions/setup-node@v3
        with:
          node-version: 18
          cache: 'pnpm'
      - run: pnpm install
      - run: pnpm build
      - run: pnpm lint
      - uses: vercel/action@main
        with:
          vercel-token: ${{ secrets.VERCEL_TOKEN }}
          vercel-org-id: ${{ secrets.VERCEL_ORG_ID }}
          vercel-project-id: ${{ secrets.VERCEL_PROJECT_ID }}
```

## Troubleshooting

### Build Fails
```bash
# Clear cache and rebuild
rm -rf .next
pnpm install
pnpm build
```

### API Connection Issues
- Verify `NEXT_PUBLIC_API_BASE` is correct
- Check CORS headers on API server
- Ensure API endpoint is accessible from deployment environment

### Performance Issues
- Check Core Web Vitals in Vercel Analytics
- Review Next.js build analysis
- Optimize images and fonts
- Enable incremental static regeneration (ISR)

## Support

For issues or questions:
1. Check the README.md for feature documentation
2. Review the API client in `lib/api.ts`
3. Check browser console for errors
4. Review Vercel deployment logs

---

**Built with v0.app**
