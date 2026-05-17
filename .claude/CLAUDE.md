I'm learning - when asked about how to do something, don't go and write the code immediately. Instead, favor discussion over code generation.

This project is about creating an agent-powered LLM-based assistant which aids in learning chess openings.
The idea is to ask questions about the position currently on the chessboard. The assistant should be able to answer questions about the nature of the position, highlighting key tactical and positional ideas, topical pawn breaks, etc.
The system will be supported by relevant documents allowing for augmenting the context by precise retrieval.

Stack (probably):
- Claude Sonnet 4.6 (main LLM)
- Gemini 3.1 Flash Lite (fast, cheap LLM for evals)
- LangChain + LangGraph (orchestration)
- Qdrant (vector store)
- OpenAI embeddings
- FastAPI (backend)