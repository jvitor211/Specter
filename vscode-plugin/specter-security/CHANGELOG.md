# Changelog

All notable changes to the Specter Security extension will be documented in this file.

## [0.1.0] - 2026-02-19

### Added

- Initial release
- Real-time scanning of `package.json` and `requirements.txt`
- Automatic scan on file save (configurable)
- VS Code diagnostics (inline warnings/errors) for flagged packages
- Hover tooltips with risk score and reasons
- Status bar indicator during scans
- Manual scan command (`Specter: Scan All Dependencies`)
- Configurable risk threshold (0-1)
- Support for custom API URL
- Filters out `node_modules/` from workspace scans
