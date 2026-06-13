#!/bin/bash
uv run uvicorn api:app --reload &
cd src/frontend && npm run dev
