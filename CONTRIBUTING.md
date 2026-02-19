# Contributing to Specter

Thanks for your interest in contributing. Specter is an open-source supply chain security tool and we welcome contributions of all kinds.

## Getting Started

1. Fork the repository
2. Clone your fork locally
3. Set up the development environment (see README)
4. Create a feature branch: `git checkout -b feat/my-feature`
5. Make your changes
6. Run tests: `pytest tests/`
7. Commit with a clear message
8. Push and open a Pull Request

## Development Setup

```bash
git clone https://github.com/YOUR_USER/specter.git
cd specter
cp .env.example .env
docker-compose up -d
python -m venv .venv
source .venv/Scripts/activate  # Windows Git Bash
pip install -r requirements.txt
```

## Code Style

- **Python**: Follow PEP 8. Use type hints. Docstrings in Portuguese.
- **TypeScript/React**: Functional components, hooks, Tailwind CSS.
- **Commits**: Use conventional commits (`feat:`, `fix:`, `docs:`, `refactor:`).
- **No dead code**: Remove unused imports, variables, and functions.
- **Error handling**: Never ignore return values or exceptions silently.

## Pull Request Process

1. Ensure your branch is up to date with `main`
2. Include a clear description of what changed and why
3. Add tests for new functionality when possible
4. Update documentation if behavior changes
5. One feature per PR — keep them focused

## What to Contribute

- Bug fixes and error handling improvements
- New package ecosystem support
- ML model improvements (better features, training data)
- VS Code plugin enhancements
- Dashboard UI improvements
- Documentation and examples
- Performance optimizations

## Reporting Issues

Use GitHub Issues with the provided templates. Include:
- Steps to reproduce
- Expected vs actual behavior
- OS, Python version, Node version
- Relevant logs or error messages

## Code of Conduct

This project follows the [Contributor Covenant](CODE_OF_CONDUCT.md). Be respectful, constructive, and professional.

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
