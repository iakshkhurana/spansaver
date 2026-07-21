# SpanSaver Mission Control

A sophisticated observability dashboard for analyzing and fixing performance issues in your applications. Built with Next.js 16, React 19, and Tailwind CSS with a professional cyberpunk hacker aesthetic featuring cyan, green, and black neon accents.

## Features

### 🎯 Core Features

- **Mission Control Dashboard**: Real-time performance monitoring with KPI cards, findings table, and statistics
- **Finding Detail Page**: In-depth analysis of each performance issue with before/after metrics, recommendations, and financial impact
- **Judge Mode**: Interactive review interface for collaborative finding verification and approval
- **Terminal CLI**: Command-line interface for executing audit, listing, applying, and verifying findings
- **Real API Integration**: Fully typed API client with mock mode for development

### 🖥️ Pages

1. **Dashboard** (`/`)
   - KPI overview with total findings, critical issues, savings, and verification status
   - Interactive findings table with severity indicators and status badges
   - Impact analysis and implementation tracking panels
   - Terminal CLI with command support (help, audit, ls, show, apply, verify, unapply, health)

2. **Finding Detail** (`/leak/[id]`)
   - Full finding information with severity, impact, and category
   - Performance metrics with baseline vs. current comparisons
   - Actionable recommendations
   - Code diff viewer (before/after)
   - Financial impact calculator
   - Action buttons: Apply, Verify, Revert with state management

3. **Judge Mode** (`/judge`)
   - Sequential review interface for collaborative approval
   - Find metrics, recommendations, and code changes
   - Three verdict options: Approve, Review, Reject
   - Progress bar and verdict tracking
   - Final summary with approval statistics

### 🎨 Design System

**Cyberpunk Hacker Aesthetic**
- Cyan, green, and black color scheme with neon accents
- Monospace typography (`Space Mono`, `JetBrains Mono`, `Courier New`)
- CRT scanline effect with ambient radial gradient glow
- Glitch effects on text (optional enhancement)
- Rounded corners (0.5rem) for modern polish
- Pulse animations and hover state glows

**Color Palette**
- **Primary (Cyan)**: `rgb(34 211 238)` - Neon cyan accent
- **Secondary (Green)**: `rgb(34 197 94)` - Neon green accent  
- **Accent (Orange)**: `rgb(249 115 22)` - Warning/alert accent
- **Background**: `rgb(8 17 28)` - Deep dark navy
- **Card**: `rgb(15 27 42)` - Slightly lighter navy
- **Foreground**: `rgb(203 213 225)` - Light slate text
- **Muted**: `rgb(51 65 85)` - Muted slate for secondary text

**Layout**
- Mobile-first responsive design
- Flexbox for most layouts
- Semantic HTML with ARIA labels
- Respects `prefers-reduced-motion`

## Project Structure

```
├── app/
│   ├── layout.tsx              # Root layout with metadata
│   ├── page.tsx                # Dashboard page
│   ├── globals.css             # Terminal aesthetics & CRT effects
│   ├── leak/
│   │   └── [id]/page.tsx       # Finding detail page
│   └── judge/
│       └── page.tsx            # Judge mode page
├── components/
│   ├── header.tsx              # Navigation header
│   ├── kpi-row.tsx             # KPI card grid
│   ├── findings-table.tsx       # Interactive findings table
│   ├── terminal-cli.tsx         # Terminal CLI component
│   ├── action-bar.tsx           # Finding action buttons
│   ├── code-diff.tsx            # Before/after code viewer
│   ├── money-math.tsx           # Financial impact calculator
│   └── ui/
│       └── button.tsx           # Base button component
├── lib/
│   ├── types.ts                # TypeScript interfaces
│   ├── api.ts                  # API client with mock support
│   └── utils.ts                # Utility functions
└── .env.local                  # Environment variables
```

## Setup & Installation

### Prerequisites
- Node.js 18+
- pnpm (or npm/yarn)

### Installation

1. **Install dependencies**
```bash
pnpm install
```

2. **Set up environment variables**
```bash
# .env.local
NEXT_PUBLIC_USE_MOCK=true
```

3. **Run the development server**
```bash
pnpm dev
```

4. **Open in browser**
Visit `http://localhost:3000`

## Usage

### Dashboard
- View all findings with severity levels and impact metrics
- Click any finding to see detailed analysis
- Track applied and verified findings
- Execute CLI commands from the Terminal CLI at the bottom

### Finding Detail
- **Apply**: Convert a detected finding to applied status
- **Verify**: Confirm improvements after applying a finding
- **Revert**: Undo changes and return to detected status
- View financial impact and payback period

### Judge Mode
- Review findings one at a time
- Vote to Approve, Review, or Reject each finding
- See progress bar and vote tracking
- View final summary at the end

### Terminal CLI Commands
```
help              - Show available commands
audit [id]        - Start audit for application
ls [filter]       - List all findings
show <id>         - Show finding details
apply <id>        - Apply a finding
verify <id>       - Verify a finding
unapply <id>      - Revert a finding
open <id>         - Open finding detail page
health            - Check system health
clear             - Clear terminal
```

## API Integration

### Mock Mode
By default, the app runs with mock data. Set `NEXT_PUBLIC_USE_MOCK=true` in `.env.local`.

### Real API
To use a real API, update `.env.local`:
```bash
NEXT_PUBLIC_API_BASE=https://api.spansaver.io
NEXT_PUBLIC_USE_MOCK=false
```

### API Client
The API client (`lib/api.ts`) provides methods:
- `startAudit(applicationId)` - Begin performance audit
- `getFindings(auditId)` - Fetch all findings
- `getFinding(findingId)` - Get specific finding
- `applyFinding(findingId)` - Apply optimization
- `verifyFinding(findingId)` - Verify improvements
- `unapplyFinding(findingId)` - Revert changes
- `getHealthCheck()` - Check API status

## Technologies

- **Framework**: Next.js 16 with App Router
- **UI Library**: React 19
- **Styling**: Tailwind CSS v4
- **Icons**: Lucide React
- **Language**: TypeScript
- **Package Manager**: pnpm
- **API Client**: Typed fetch-based client

## Accessibility Features

- Semantic HTML (`main`, `header`, `nav`)
- ARIA labels and roles throughout
- Screen reader optimized
- Keyboard navigation support
- Focus indicators on interactive elements
- Respects `prefers-reduced-motion` media query

## Performance

- Server-side rendering by default
- Client-side state with React hooks
- Optimistic UI updates
- CRT scanlines implemented with CSS (efficient GPU rendering)
- Minimal JavaScript bundle size

## Responsive Design

- **Mobile**: 375px - Single column layout, optimized touch targets
- **Tablet**: 768px - Multi-column grids, 2-column findings table
- **Desktop**: 1216px+ - Full dashboard with sidebar stats and CLI

## Future Enhancements

- Real-time dashboard updates with WebSocket
- Advanced filtering and sorting in findings table
- Custom alert thresholds and notifications
- Integration with monitoring platforms
- Historical trend analysis
- Export and reporting features
- Multi-application support

## License

Created with v0.app
