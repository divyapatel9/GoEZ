# Health Intelligence App

A unified health analytics and AI-powered deep analysis platform.

## Overview

This application combines two health projects into a single unified experience:

- **Visual Analytics** - Interactive charts and trend visualization from your Apple Health data
- **Deep Analysis** - AI-powered health insights using LangGraph agents

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Unified Frontend                         │
│                  http://localhost:3000                       │
├─────────────────────────────────────────────────────────────┤
│  Overview │ Visual Analytics │ Deep Analysis │ Sessions     │
└─────────────────────────────────────────────────────────────┘
                              │
                    Vite Proxy │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    Unified Backend                          │
│                  http://localhost:8000                       │
├────────────────┬────────────────────┬──────────────────────┤
│   /agent/*     │    /analytics/*    │      /ai/*           │
│  Deep Analysis │  Visual Analytics  │   Chart Assistant    │
│  (LangGraph)   │     (DuckDB)       │    (Anthropic)       │
└────────────────┴────────────────────┴──────────────────────┘
```

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 20+
- MongoDB (for agent session storage)
- Anthropic API key

### 1. Backend Setup

```bash
# From project root
pip install -r requirements.txt

# Configure environment variables
cp .env.example .env
# Edit .env with your API keys and paths

# Start the unified backend
python run.py
```

The backend will start at http://localhost:8000

### 2. Frontend Setup

```bash
# From project root
cd frontend

# Install dependencies
npm install

# Start development server
npm run dev
```

The frontend will start at http://localhost:3000

## Navigation

| Route | Page | Description |
|-------|------|-------------|
| `/` | Overview | Health metrics dashboard with quick actions |
| `/visual-analytics` | Visual Analytics | Interactive charts and trend visualization |
| `/deep-analysis` | Deep Analysis | AI-powered conversational health insights |
| `/sessions` | Sessions | History of your analysis sessions |
| `/settings` | Settings | Backend status and preferences |

## API Endpoints

### Agent Backend (`/agent/*`)
- `POST /agent/chat/stream` - Streaming chat for deep analysis
- `GET /agent/sessions/:userId` - Get user sessions
- `GET /agent/sessions/:userId/:sessionId/history` - Get session history
- `DELETE /agent/sessions/:userId/:sessionId` - Delete session

### Analytics Backend (`/analytics/*`)
- `GET /analytics/metrics` - List available metrics
- `GET /analytics/metric/daily` - Get daily metric data
- `GET /analytics/overview` - Get overview tiles
- `GET /analytics/scores` - Get recovery/strain scores

### AI Backend (`/ai/*`)
- `POST /ai/chat` - Chart-focused AI chat
- `GET /ai/charts` - List available charts
- `GET /ai/chat/thread` - Get conversation thread

## Environment Variables

Copy `.env.example` to `.env` and configure:

```bash
# Anthropic API (used by both backends)
ANTHROPIC_API_KEY=your_key
ANTHROPIC_MODEL=claude-sonnet-4-20250514

# MongoDB (Deep Analysis sessions)
MONGODB_URI=mongodb://localhost:27017
MONGODB_DATABASE=health_data

# Health Data Paths (Visual Analytics)
HEALTH_EXPORT_DIR=/path/to/apple_health_export
HEALTH_DATA_DIR=/path/to/processed_data
```

## Development

### Project Structure

```
viz + deep report/
├── backend/                    # Consolidated Python backend
│   ├── __init__.py
│   ├── main.py                 # Unified FastAPI entrypoint
│   ├── agent/                  # Deep Analysis (LangGraph)
│   │   ├── api.py, config.py, graph.py, main.py
│   │   ├── nodes/              # Agent workflow nodes
│   │   ├── prompts/            # System prompts
│   │   ├── subagents/          # Sub-agent factories
│   │   └── utils/              # MongoDB tools
│   └── healthdata/             # Visual Analytics (DuckDB)
│       ├── ai/                 # Chart AI assistant
│       ├── analytics/          # Data processing
│       ├── api/                # FastAPI routers
│       ├── ingest/             # Health data parsing
│       └── storage/            # Storage utilities
├── frontend/                   # Unified React frontend
│   ├── src/
│   │   ├── app/layout/         # Layout components
│   │   ├── modules/            # Feature modules
│   │   ├── services/           # API clients
│   │   ├── store/              # Zustand stores
│   │   └── shared/             # Shared components
│   ├── package.json
│   └── vite.config.ts
├── .env.example                # Environment template
├── requirements.txt            # Python dependencies
└── run.py                      # Server runner
```

### Key Features

- **Unified Navigation** - Single sidebar for all features
- **Context Handoff** - Pass context from Overview/Visual Analytics to Deep Analysis
- **Floating AI Button** - Quick access to AI assistance from any page
- **Session Persistence** - Track analysis history across sessions
- **Responsive Design** - Works on desktop and tablet

## Troubleshooting

### Backend won't start
- Check that all environment variables are set
- Ensure MongoDB is running
- Verify Python dependencies are installed

### Frontend lint errors
- Run `npm install` in the frontend directory
- Errors about missing modules resolve after installation

### API calls failing
- Check backend is running at http://localhost:8000
- Verify proxy configuration in vite.config.ts
- Check browser console for CORS errors

## License

MIT
