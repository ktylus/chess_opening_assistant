I'm learning - when asked about how to do something, don't go and write the code immediately. Instead, favor discussion over code generation. Favor modern approaches and good practices that scale with project growth.

This project is about creating an agent-powered LLM-based assistant which aids in learning chess openings. It's important that the system is limited to openings, probably max 6 moves deep.
The idea is to ask questions about the position currently on the chessboard. The assistant should be able to answer questions about the nature of the position, highlighting key tactical and positional ideas, topical pawn breaks, etc.
The system will be supported by relevant documents allowing for augmenting the context by precise retrieval.

Pointers on writing function docstrings:
- Stick to the module interface, don't comment on implementation details.
- Docstrings should be PEP-8-compliant.
- Don't include your reasoning noise that concerns consumers of the module - it makes the comment fragile and also it's not the docstring's responsibility.

The environment is controlled with `uv`. Git bash is available for bash execution.