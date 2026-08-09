# homey
An AI assistant that helps you filter through airbnb listings and find the perfect one

## Tech Stack

- **Frontend**: [Nuxt 4](https://nuxt.com/) + [Tailwind CSS](https://tailwindcss.com/) — chatbot UI inspired by the [Nuxt AI Chatbot template](https://vercel.com/templates/nuxt/nuxt-ai-chatbot)
- **Backend**: [FastAPI](https://fastapi.tiangolo.com/) + [pydantic-ai](https://ai.pydantic.dev/) — streaming AI agent

## Project Structure

```
homey/
├── backend/           # FastAPI + pydantic-ai
│   ├── main.py        # FastAPI app entry point
│   ├── app/
│   │   ├── agent.py   # pydantic-ai agent definition
│   │   └── routers/
│   │       └── chat.py  # /api/chat streaming endpoint
│   └── requirements.txt
└── frontend/          # Nuxt 4 chatbot UI
    ├── app/app.vue    # Main chatbot interface
    ├── components/
    │   └── ChatMessage.vue
    ├── composables/
    │   └── useChat.ts  # Chat state & streaming logic
    └── nuxt.config.ts
```

## Setup

### Backend

```bash
cd backend
cp .env.example .env
# Edit .env and add your OPENAI_API_KEY
pip install -r requirements.txt
uvicorn main:app --reload
```

The API will be available at `http://localhost:8000`.

### Frontend

```bash
cd frontend
cp .env.example .env
npm install
npm run dev
```

The app will be available at `http://localhost:3000`.

## Environment Variables

### Backend (`backend/.env`)

| Variable | Description | Default |
|----------|-------------|---------|
| `OPENAI_API_KEY` | Your OpenAI API key | — |
| `OPENAI_MODEL` | Model to use | `gpt-4o-mini` |

### Frontend (`frontend/.env`)

| Variable | Description | Default |
|----------|-------------|---------|
| `NUXT_PUBLIC_API_BASE` | Backend API URL | `http://localhost:8000` |

