#!/bin/bash
# Desktop Notifications - Sends desktop notifications for important events
# Hook: Notification

source "$(dirname "$0")/../_lib/common.sh"

MESSAGE=$(get_field '.message')
LEVEL=$(get_field '.level')

log_hook "Notification: [$LEVEL] $MESSAGE"

# Only show desktop notifications for important events
if [[ "$LEVEL" == "error" ]] || [[ "$LEVEL" == "warning" ]]; then
  # macOS notification
  if command -v osascript &>/dev/null; then
    osascript -e "display notification \"$MESSAGE\" with title \"Claude Code\" sound name \"Ping\"" 2>/dev/null
  # Linux notification
  elif command -v notify-send &>/dev/null; then
    notify-send "Claude Code" "$MESSAGE" 2>/dev/null
  fi
fi

exit 0
