# Contributing to YG Starter

Thank you for your interest in contributing to YG Starter! This document provides guidelines and instructions for contributing.

## Code of Conduct

By participating in this project, you agree to maintain a respectful and inclusive environment for everyone.

## How to Contribute

### Reporting Bugs

1. **Check existing issues** - Search [GitHub Issues](https://github.com/yonatangross/yg-starter/issues) to avoid duplicates
2. **Create a new issue** with:
   - Clear, descriptive title
   - Steps to reproduce
   - Expected vs actual behavior
   - Environment details (OS, Python/Node versions, Docker version)

### Suggesting Features

1. Open a [GitHub Issue](https://github.com/yonatangross/yg-starter/issues/new) with the `enhancement` label
2. Describe the feature and its use case
3. Explain why it would benefit the project

### Pull Requests

1. **Fork the repository** and create your branch from `dev`
2. **Follow the branch naming convention**:
   - `feature/<description>` - New features
   - `fix/<description>` - Bug fixes
   - `docs/<description>` - Documentation updates
   - `refactor/<description>` - Code refactoring
3. **Make your changes** following the code style guidelines below
4. **Write or update tests** as needed
5. **Run quality checks** before submitting:
   ```bash
   make quality  # Runs lint, format check, and tests
   ```
6. **Create a Pull Request** targeting `dev` branch

## Development Setup

### Prerequisites

- Docker & Docker Compose
- Python 3.12+
- Node.js 22+
- uv (Python package manager)

### Getting Started

```bash
# Clone and setup
git clone https://github.com/yonatangross/yg-starter.git
cd yg-starter
./init.sh "YG Starter"

# Add at least one LLM API key to backend/.env
# OPENAI_API_KEY=sk-...

# Start development
make dev
```

## Code Style Guidelines

### Python (Backend)

- **Formatter**: Ruff
- **Linter**: Ruff
- **Type Checker**: ty (Red Knot)
- **Style**: Follow existing patterns in codebase

```bash
# Check formatting
cd backend && uv run ruff format --check app/

# Check linting
cd backend && uv run ruff check app/

# Check types
cd backend && uv run ty check app/
```

### TypeScript (Frontend)

- **Formatter**: Biome
- **Linter**: Biome
- **Style**: Follow existing patterns in codebase

```bash
cd frontend
npm run lint
npm run format:check
npm run typecheck
```

### Commit Messages

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <description>

[optional body]

[optional footer]
```

**Types**:
- `feat` - New feature
- `fix` - Bug fix
- `docs` - Documentation changes
- `refactor` - Code refactoring
- `test` - Adding or updating tests
- `chore` - Maintenance tasks

**Examples**:
```
feat(api): add user authentication endpoint
fix(chat): handle empty message validation
docs(readme): update installation instructions
refactor(agent): simplify state management
```

## Testing

### Backend Tests

```bash
cd backend

# Run all tests
uv run pytest tests/

# Run with coverage
uv run pytest tests/ --cov=app --cov-report=term-missing

# Run specific test file
uv run pytest tests/unit/test_example.py -v
```

### Frontend Tests

```bash
cd frontend

# Run tests
npm test

# Run with coverage
npm run test:coverage
```

## Project Structure

```
yg-starter/
├── backend/           # FastAPI + LangGraph backend
│   ├── app/
│   │   ├── api/       # HTTP endpoints
│   │   ├── agent/     # LangGraph workflows
│   │   ├── core/      # Configuration, logging
│   │   ├── db/        # Database models
│   │   └── shared/    # Shared services
│   └── tests/
├── frontend/          # React 19 + TypeScript frontend
│   └── src/
├── .claude/           # Claude Code AI configuration
└── docs/              # Documentation
```

## Questions?

- Open a [GitHub Issue](https://github.com/yonatangross/yg-starter/issues)
- Check existing [Documentation](./docs/)

Thank you for contributing!
