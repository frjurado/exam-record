# Exam Record

**Exam Record** is a community-driven database designed to crowdsource music conservatory entrance exams (specifically Music Analysis).

## Documentation
The complete documentation is located in the `docs/` folder:
*   [Documentation Index](docs/README.md)
*   [Project Roadmap](docs/roadmap.md)
*   [Technical Specifications](docs/technical_specs.md)

## Technology Stack
*   **Backend:** Python 3.12+ / FastAPI / SQLAlchemy (Async)
*   **Database:** SQLite (Beta)
*   **Frontend:** Server-Side Rendering (Jinja2) + HTMX + Alpine.js

## Development Setup

```bash
python -m venv .venv
source .venv/Scripts/activate  # Windows (bash) — use source .venv/bin/activate on Linux/macOS
pip install -r requirements.txt
pip install pre-commit
pre-commit install            # install git hooks (run once per clone)
```

## Contributing
Please refer to [docs/meta/version_control.md](docs/meta/version_control.md) for our git workflow and commit standards.
