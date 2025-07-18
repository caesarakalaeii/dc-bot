#!/bin/sh
set -e

# Decode base64-encoded whitelist and blacklist env vars
mkdir -p /app/persistence

if [ -n "$WHITE_LIST" ]; then
    echo "$WHITE_LIST" | base64 -d > /app/persistence/whitelist_${BOT_NAME}.json
    echo "Whitelist for ${BOT_NAME} loaded:\n"
    cat /app/persistence/whitelist_${BOT_NAME}.json
    echo "\n"
fi

if [ -n "$BLACK_LIST" ]; then
    echo "$BLACK_LIST" | base64 -d > /app/persistence/blacklist_${BOT_NAME}.json
    echo "Blacklist for ${BOT_NAME} loaded:\n"
    cat /app/persistence/blacklist_${BOT_NAME}.json
    echo "\n"
fi

exec python bot_start.py

