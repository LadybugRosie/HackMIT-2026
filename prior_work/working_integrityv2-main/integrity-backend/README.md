# Kuizlo Integrity Backend

FastAPI backend for document integrity tracking with provenance-based trust scoring.

## Setup

```bash
cd integrity-backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

## Configuration

Copy `env.example` to `.env` and configure:

```bash
cp env.example .env
```

## Run

```bash
export MONGO_URI="mongodb://localhost:27017"
export DB_NAME="kuizlo_integrity"
uvicorn app.main:app --reload --port 8080
```

## API Endpoints

- `POST /api/integrity/session/start` - Start new integrity session
- `POST /api/integrity/ingest` - Process document events and update trust score
- `GET /api/integrity/status` - Get current integrity status
- `POST /api/integrity/export/check` - Check if export is allowed based on trust

## Architecture

- **Piece Table**: Tracks document provenance (Typed, Internal, External)
- **N-gram Index**: Classifies paste origins
- **Real-time Scoring**: Updates trust based on current document state

