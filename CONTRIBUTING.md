# Contributing to VoiceFlow

Thanks for your interest in contributing to VoiceFlow!

## Getting Started

### Prerequisites

- Node.js (with pnpm)
- Python 3.10-3.13 (3.14+ not yet supported due to onnxruntime)
- uv (Python package manager)

### Setup

```bash
# Clone the repo
git clone https://github.com/infiniV/VoiceFlow.git
cd VoiceFlow

# Install dependencies (Node + Python)
pnpm run setup

# Run in development mode
pnpm run dev
```

## Development

### Commands

```bash
pnpm run dev          # Run frontend + backend
pnpm run dev:watch    # With Python hot-reload
pnpm run build        # Build desktop app
pnpm run lint         # Lint frontend
```

### Running Tests

```bash
uv run -p .venv pytest src-pyloid/tests/ -v
```

### Project Structure

- `src-pyloid/` - Python backend (Pyloid/PySide6)
- `src/` - React frontend (TypeScript + Vite)
- `src/components/ui/` - shadcn/ui components

## Submitting Changes

1. Fork the repo
2. Create a feature branch (`git checkout -b feature/my-feature`)
3. Make your changes
4. Run tests and linting
5. Commit with a clear message (`feat: add cool feature`)
6. Open a PR against `main`

### Commit Style

Use conventional commits:
- `feat:` - New feature
- `fix:` - Bug fix
- `update:` - Enhancement to existing feature
- `refactor:` - Code restructuring
- `docs:` - Documentation only

## Reporting Issues

When opening an issue, please include:
- VoiceFlow version
- OS and version
- Steps to reproduce
- Expected vs actual behavior

## Questions?

Open an issue or start a discussion. Thanks for contributing!
