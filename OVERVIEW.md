# Telegram News Intelligence Bot

A multilingual Telegram bot that collects RSS articles, groups duplicate stories, and prepares scheduled news digests.

## Components

- FastAPI manages users, interests, news sources, and digest previews.
- The aiogram bot handles Telegram interactions and delivers digests.
- Celery workers collect and process articles, score stories, and schedule delivery.
- PostgreSQL and pgvector store application and article data. Redis is used by the worker stack.

## Project layout

- `backend/` contains the API and database code.
- `bot/` contains the Telegram interface and localization.
- `pipeline/` and `workers/` contain news processing and scheduled tasks.
- `tests/` contains unit and integration tests.
- `docker/` contains the Compose setup and container build files.
