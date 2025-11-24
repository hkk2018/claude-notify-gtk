---
title: "Focus Mapping Configuration"
description: "Configuration for focusing windows when clicking notification cards"
last_modified: "2025-11-24 15:31"
---

# Focus Mapping Configuration

## Overview

This feature allows you to focus specific application windows when clicking on notification cards. You can configure different focus behaviors for different projects.

## Configuration File

**Location**: `~/.config/claude-notify-gtk/focus-mapping.json`

## Configuration Format

```json
{
  "projects": {
    "/path/to/project1": {
      "type": "vscode",
      "window_title": "Visual Studio Code"
    },
    "/path/to/project2": {
      "type": "cursor"
    },
    "/path/to/project3": {
      "type": "custom",
      "custom_command": "/path/to/focus-script.sh",
      "pass_data": true
    }
  },
  "default": {
    "type": "vscode"
  },
  "builtin_editors": {
    "vscode": {
      "window_title": "Visual Studio Code",
      "window_class": "Code"
    },
    "cursor": {
      "window_title": "Cursor",
      "window_class": "Cursor"
    }
  }
}
```

## Configuration Options

### Project Configuration

Each project path can have the following settings:

- **type**: Editor type or "custom"
  - `"vscode"`: Visual Studio Code
  - `"cursor"`: Cursor editor
  - `"custom"`: Custom command

- **window_title** (optional): Specific window title to match
  - Overrides the default from `builtin_editors`

- **window_class** (optional): X11 window class to match
  - More reliable than window title

- **custom_command** (required for type="custom"): Script or command to execute
  - Can use placeholders: `{cwd}`, `{project}`, `{session}`, `{message}`

- **pass_data** (optional, default: true): Pass notification data to custom command
  - When true, sends all notification data as JSON to the command's stdin

### Default Configuration

The `default` section is used when a project has no specific configuration.

### Built-in Editors

The `builtin_editors` section defines default window matching rules for common editors.

## Examples

### Example 1: VSCode Project

```json
{
  "projects": {
    "/home/ubuntu/Projects/my-vscode-project": {
      "type": "vscode"
    }
  }
}
```

### Example 2: Multiple Projects with Different Editors

```json
{
  "projects": {
    "/home/ubuntu/Projects/vscode-project": {
      "type": "vscode"
    },
    "/home/ubuntu/Projects/cursor-project": {
      "type": "cursor"
    }
  },
  "default": {
    "type": "vscode"
  }
}
```

### Example 3: Custom Focus Script

```json
{
  "projects": {
    "/home/ubuntu/Projects/special-project": {
      "type": "custom",
      "custom_command": "/home/ubuntu/scripts/focus-tmux-window.sh",
      "pass_data": true
    }
  }
}
```

Custom script receives notification data as JSON via stdin:

```bash
#!/bin/bash
# focus-tmux-window.sh

# Read notification data from stdin
notification_data=$(cat)

# Extract fields
cwd=$(echo "$notification_data" | jq -r '.cwd')
session=$(echo "$notification_data" | jq -r '.session_id')

# Custom focus logic
# ... your implementation ...
```

### Example 4: Specific Window Title

```json
{
  "projects": {
    "/home/ubuntu/Projects/multiple-vscode-windows": {
      "type": "vscode",
      "window_title": "my-project - Visual Studio Code"
    }
  }
}
```

## How It Works

1. User clicks on a notification card
2. System extracts the project path (`cwd`) from notification data
3. System looks up the project in `focus-mapping.json`
4. If found, uses the project-specific configuration
5. If not found, uses the `default` configuration
6. Executes the focus command:
   - **Built-in editor**: Uses `xdotool` to find and focus the window
   - **Custom command**: Executes the command with notification data

## Notification Data Passed to Custom Commands

When `pass_data: true`, the following JSON is sent to the custom command's stdin:

```json
{
  "cwd": "/path/to/project",
  "message": "Notification message",
  "notification_type": "idle_prompt",
  "session_id": "abc123...",
  "hook_event_name": "notification",
  "transcript_path": "/path/to/transcript.md",
  "project_name": "project-name",
  "timestamp": "2025-11-24 12:34:56"
}
```

## Troubleshooting

### Window Not Found

If clicking a notification doesn't focus the window:

1. Check if the editor is actually running
2. Verify the window title/class matches:
   ```bash
   xdotool search --name "Visual Studio Code" getwindowname
   ```
3. Try using `window_class` instead of `window_title`:
   ```bash
   xdotool search --class "Code" getwindowname
   ```

### Custom Command Not Working

1. Check if the script is executable:
   ```bash
   chmod +x /path/to/script.sh
   ```
2. Test the script manually:
   ```bash
   echo '{"cwd":"/test"}' | /path/to/script.sh
   ```
3. Check logs in `~/.config/claude-notify-gtk/focus-errors.log`
