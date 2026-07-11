I'm learning - you can author code but let's work through possible approaches first. I'm willing to engage with decisions involving tradeoffs to practice.
This is a portfolio project.

This project is about creating an agent-powered LLM-based assistant which aids in learning chess openings. It's important that the system is limited to openings, probably max 6 moves deep.
The idea is to ask questions about the position currently on the chessboard. The assistant should be able to answer questions about the nature of the position, highlighting key tactical and positional ideas, topical pawn breaks, etc.
The system will be supported by relevant documents allowing for augmenting the context by precise retrieval.

Pointers on writing function docstrings:
- Stick to the module interface, don't comment on implementation details.
- Docstrings should be PEP-8-compliant.
- Don't include your reasoning noise that concerns consumers of the module - it makes the comment fragile and also it's not the docstring's responsibility.

The environment is controlled with `uv`. Git bash is available for bash execution.