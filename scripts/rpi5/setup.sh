#!/usr/bin/env bash
# Superseded by the board-aware installer (handles Pi 3B+ "lite" and Pi 4/5 "full").
exec bash "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/../pi/install.sh" "$@"
