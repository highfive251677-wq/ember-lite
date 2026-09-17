#!/data/data/com.termux/files/usr/bin/bash

echo "==================================="
echo "  Lumafoundry Database Setup       "
echo "==================================="
echo ""

if ! command -v sqlite3 &> /dev/null; then
    echo "📦 Installing SQLite..."
    pkg install sqlite -y
fi

if ! command -v jq &> /dev/null; then
    echo "📦 Installing jq..."
    pkg install jq -y
fi

DB_PATH="data/lumafoundry.db"
mkdir -p data

echo "🗄️  Creating database at $DB_PATH..."

sqlite3 "$DB_PATH" << 'SQL'
CREATE TABLE IF NOT EXISTS sources (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    category TEXT NOT NULL,
    type TEXT NOT NULL,
    url TEXT,
    purpose TEXT,
    layer TEXT,
    relevance TEXT,
    status TEXT,
    notes TEXT
);
SQL

if [ ! -f "data/sources.json" ]; then
    echo "❌ Error: data/sources.json not found!"
    exit 1
fi

echo "📥 Importing data from JSON..."

jq -r '.sources[] | [.id, .name, .category, .type, (.url // ""), (.purpose // ""), (.layer // ""), (.relevance // ""), (.status // ""), (.notes // "")] | @tsv' data/sources.json | while IFS=$'\t' read -r id name cat type url purpose layer rel status notes; do
    esc() { echo "$1" | sed "s/'/''/g"; }
    sqlite3 "$DB_PATH" "INSERT OR REPLACE INTO sources VALUES ('$(esc "$id")','$(esc "$name")','$(esc "$cat")','$(esc "$type")','$(esc "$url")','$(esc "$purpose")','$(esc "$layer")','$(esc "$rel")','$(esc "$status")','$(esc "$notes")');"
done

echo ""
echo "✅ Database created: $DB_PATH"
echo ""
echo "📊 Total sources:"
sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM sources;"
echo ""
echo "📊 By category:"
sqlite3 -header -column "$DB_PATH" "SELECT category, COUNT(*) FROM sources GROUP BY category;"
