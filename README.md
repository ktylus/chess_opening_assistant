# Chess Opening Assistant

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

Frontend was AI-generated - I have no experience in this area.

### Core idea

Despite well-known LLM limitations in chess understanding, well-known opening positions are well represented in the training data. Understanding the position is not required for our use case - the models absorbed large amounts of commentary on these positions. This very often involves didactic texts, chess studies - exactly what we need.

The hope is that a large model (Opus or Gemini Pro class) or even a mid-sized one would be able to navigate many popular (and some less popular) opening variants, along with short continuations or sidelines.

In order to ensure accuracy and response quality, I gathered documents analyzing various positions and implemented their retrieval.

### Document retrieval
Chess is a domain structured by the current board state. So, we can retrieve documents relating to the current board position by choosing those documents which refer to the same position.

Semantic retrieval is considered as a supporting measure, but it isn't promising - retrieval relies on move variations which appear in standard algebraic notation. Thus, achieving high-quality retrieval through embeddings might not be possible. It might be possible to search for openings that **share ideas** with the one discussed at the moment. This is where semantic retrieval could shine.

### Move validation
I am planning to introduce a validation scheme ensuring that moves and variations suggested by the model are legal (consist of legal moves each step of the way).

The core idea is:
1. Use a small LLM (with the current board state) to extract moves/variations suggested in the response.
2. Run the variations, checking if they are legal all the way.
3. Rewrite the response without variations flagged as invalid, without introducing new ones.
4. Repeat until no variations are flagged as invalid. (probably max 2 iterations)

Having a loop operation like that would be an opportunity to use Langgraph.

### Evaluation
A comprehensive evaluation approach is being implemented.

## Usage

TODO

## Data Sources

- [Lichess opening explorer](https://lichess.org/api#tag/opening-explorer) accessed through the API.
- The core opening document set was retrieved from the [Wikibooks Chess Opening Theory Book](https://en.wikibooks.org/wiki/Category:Book:Chess_Opening_Theory). (selected articles)