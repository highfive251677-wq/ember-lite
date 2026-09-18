#!/data/data/com.termux/files/usr/bin/bash
# Validate documentation structure

echo "=========================================="
echo "  Documentation Validation"
echo "=========================================="
echo ""

ERRORS=0
REQUIRED=(
    "AGENTS.md"
    "README.md"
    "docs/architecture/OVERVIEW.md"
    "docs/architecture/LAYERS.md"
    "docs/design-docs/DECISIONS.md"
    "docs/design-docs/PRINCIPLES.md"
    "docs/guides/QUICKSTART.md"
    "docs/guides/COMMANDS.md"
    "docs/references/INDUSTRY.md"
)

echo "Checking required files..."
for f in "${REQUIRED[@]}"; do
    if [ -f "$f" ]; then
        LINES=$(wc -l < "$f")
        echo "  OK  $f ($LINES lines)"
    else
        echo "  MISSING: $f"
        ERRORS=$((ERRORS + 1))
    fi
done

echo ""
echo "=========================================="
if [ $ERRORS -eq 0 ]; then
    echo "  All docs valid!"
else
    echo "  $ERRORS issue(s) found"
fi
echo "=========================================="
exit $ERRORS
