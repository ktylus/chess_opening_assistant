# Chess Opening Assistant

[![CI](https://github.com/ktylus/chess_opening_assistant/actions/workflows/ci.yml/badge.svg)](https://github.com/ktylus/chess_opening_assistant/actions/workflows/ci.yml)

An agentic assistant helping beginners and intermediate chess players explore ideas behind openings. Put a position on the board and engage in conversation.


## Demo

TODO


## Engineering

This is an agentic system with a few tools wired up:
- Document retrieval (based on matching the current board state, not vector-based)
- Chess engine (Stockfish) position evaluation
- Retrieval of statistics on move popularity in master games

Stack:
- Langchain
- FastAPI
- Pydantic
- python-chess

### Core idea

Despite well-known LLM limitations in chess understanding, well-known opening positions are well represented in the training data. Understanding the position is not required for our use case - the models absorbed large amounts of commentary on these positions. This very often involves didactic texts, chess studies - exactly what we need.

Coming into the project, my idea was that a large model (Opus or Gemini Pro class) or even a mid-sized one would be able to navigate many popular (and some less popular) opening variants, along with short continuations or sidelines.

### Document retrieval

In order to ensure accuracy and response quality, I gathered documents analyzing various positions and implemented their retrieval.
 
Chess is a domain structured by the current board state. So, we can retrieve documents relating to the current board position by choosing those documents which refer to the same position.


## Usage

The project is split into a Python backend (FastAPI) and a React frontend (Vite),
each with its own dependency manifest and lockfile.

### Prerequisites

- [`uv`](https://docs.astral.sh/uv/) (Python tooling - manages the env and Python version)
- [Node.js](https://nodejs.org/) 18+ (ships with `npm`)
- A [Stockfish](https://stockfishchess.org/download/) binary for engine evaluation

### Environment variables

Create a `.env` file and fill out the details using `.env.example` as reference.

### Setup

One-time install of dependencies after cloning:

```bash
uv sync                    # build the Python .venv from uv.lock
cd src/frontend && npm ci  # install frontend deps from package-lock.json
```

### Running

Start the backend and frontend (in separate terminals):

```bash
uv run uvicorn api:app --reload    # backend on http://localhost:8000
```

```bash
cd src/frontend && npm run dev     # frontend on http://localhost:5173
```

The Vite dev server proxies `/chat` to the backend on port 8000, so run both
together and open the frontend URL in your browser.

Alternatively, once set up, run `start.sh` to launch both at once
(requires bash - native on macOS/Linux, git bash or WSL on Windows).


## Data Sources

- The core opening document set was retrieved from the [Wikibooks Chess Opening Theory Book](https://en.wikibooks.org/wiki/Category:Book:Chess_Opening_Theory). (selected articles)
- [Lichess opening explorer](https://lichess.org/api#tag/opening-explorer) accessed through the API.


## Roadmap

### Evaluation
A comprehensive evaluation approach is being implemented.

### Move validation
I am planning to introduce a validation scheme ensuring that moves and variations suggested by the model are legal (consist of legal moves each step of the way).

The core idea is:
1. Use a small LLM (with the current board state) to extract moves/variations suggested in the response.
2. Run the variations, checking if they are legal all the way.
3. Rewrite the response without variations flagged as invalid, without introducing new ones.
4. Repeat until no variations are flagged as invalid. (probably max 2 iterations)

Having a loop operation like that would be an opportunity to use Langgraph.

### Semantic retrieval

Semantic retrieval is considered as a supporting measure, but it's a challenge - retrieval relies on move variations which appear in standard algebraic notation. Thus, achieving high-quality retrieval would have to be done through matching concepts, ideas - something described in natural language, as opposed to chess notation.