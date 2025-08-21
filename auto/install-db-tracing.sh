#!/bin/bash
set -e

echo "Installing database tracing (Phase 3)..."

# 1. Create the directory structure
mkdir -p services/api/app/db_tracing
mkdir -p services/api/app/repositories

# 2. Copy the files
cp -f services/api/app/db_tracing/__init__.py services/api/app/db_tracing/
cp -f services/api/app/db_tracing/sql_tracing.py services/api/app/db_tracing/
cp -f services/api/app/repositories/__init__.py services/api/app/repositories/
cp -f services/api/app/repositories/user_repository.py services/api/app/repositories/
cp -f services/api/app/repositories/item_repository.py services/api/app/repositories/

# 3. Apply patches to existing files
echo "Applying patch to database.py..."
# Backup the original file
cp services/api/app/database.py services/api/app/database.py.bak

# Append the tracing code to database.py
cat services/api/app/database.py.patch >> services/api/app/database.py

echo "Applying patches to routers..."
# Apply patches to router files if they exist
if [ -f services/api/app/routers/users.py ]; then
    cp services/api/app/routers/users.py services/api/app/routers/users.py.bak
    cat services/api/app/routers/users.py.patch >> services/api/app/routers/users.py
fi

if [ -f services/api/app/routers/items.py ]; then
    cp services/api/app/routers/items.py services/api/app/routers/items.py.bak
    cat services/api/app/routers/items.py.patch >> services/api/app/routers/items.py
fi

echo "Database tracing installation complete!"
echo ""
echo "To activate the changes:"
echo "1. Rebuild the API container: docker-compose -f docker-compose.prod.yml build api"
echo "2. Restart the API service: docker-compose -f docker-compose.prod.yml up -d api"
echo ""
echo "Then check Jaeger UI at http://localhost:16686 to see detailed database traces!"
