#!/bin/bash
# File Guard - Protects sensitive files from modification
# Hook: PreToolUse (Write|Edit)

source "$(dirname "$0")/../../_lib/common.sh"

FILE_PATH=$(get_field '.tool_input.file_path')

log_hook "File write/edit: $FILE_PATH"

# Protected file patterns
PROTECTED_PATTERNS=(
  '\.env$'
  '\.env\.local$'
  '\.env\.production$'
  'credentials\.json$'
  'secrets\.json$'
  'private\.key$'
  '\.pem$'
  'id_rsa$'
  'id_ed25519$'
)

# Check if file matches protected patterns
for pattern in "${PROTECTED_PATTERNS[@]}"; do
  if [[ "$FILE_PATH" =~ $pattern ]]; then
    block_with_error "Protected File" "Cannot modify protected file: $FILE_PATH

This file matches protected pattern: $pattern

Protected files include:
- Environment files (.env, .env.local, .env.production)
- Credential files (credentials.json, secrets.json)
- Private keys (.pem, id_rsa, id_ed25519)

If you need to modify this file, do it manually outside Claude Code."
  fi
done

# Warn on configuration files (but allow)
CONFIG_PATTERNS=(
  'package\.json$'
  'pyproject\.toml$'
  'tsconfig\.json$'
)

for pattern in "${CONFIG_PATTERNS[@]}"; do
  if [[ "$FILE_PATH" =~ $pattern ]]; then
    warn "Modifying configuration file: $FILE_PATH"
    log_hook "WARNING: Config file modification: $FILE_PATH"
  fi
done

exit 0
