# Doodle History: 20th-Century Logic Game

## Overview

Doodle History is an interactive logic game set in the 20th century, where players combine historical concepts, events, or inventions to discover new ones. The game leverages artificial intelligence (via Google Gemini) to determine valid historical combinations, aiming to reach predefined milestones or guides. Combinations are cached in a local SQLite database for efficiency, and the system dynamically expands the item database as new concepts are discovered.

The project consists of three main Python files:
- `ai_engine.py`: Handles the core logic for combining items, querying the AI model, and managing database interactions via `DoodleHistoryEngine`.
- `game_manager.py`: Manages game state, tracks player progress, and orchestrates the combination process through the `DoodleHistoryGame` class.
- `db_setup.py`: Initializes the SQLite database with base items, target milestones, and guide elements from a CSV file.

## Features

- **AI-Powered Combinations**: Uses Google Gemini (gemini-1.5-flash) to evaluate if two inputs logically combine into a historical concept.
- **Database Caching**: Stores successful combinations in an SQLite database to avoid redundant AI queries.
- **Milestone and Guide System**: Targets specific historical milestones; if not matched, suggests guides or new concepts.
- **Dynamic Expansion**: New items are added to the database as they are discovered.
- **Pydantic Validation**: Ensures structured responses from the AI model.

## Requirements

- Python 3.8+
- SQLite3 (built-in with Python)
- Google Generative AI SDK (`google-genai`)
- Pydantic
