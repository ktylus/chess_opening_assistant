#!/bin/bash
uv run uvicorn backend.app.app:app --reload &
cd frontend && npm run dev
