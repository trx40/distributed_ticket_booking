#!/bin/bash
# Fix relative imports in generated gRPC files

echo "Fixing imports in generated gRPC files..."

# Fix imports in src/client/
for file in src/client/*_pb2_grpc.py; do
    if [ -f "$file" ]; then
        sed -i 's/from \. import \(.*\)_pb2/import \1_pb2/' "$file"
        echo "Fixed: $file"
    fi
done

# Fix imports in src/servers/
for file in src/servers/*_pb2_grpc.py; do
    if [ -f "$file" ]; then
        sed -i 's/from \. import \(.*\)_pb2/import \1_pb2/' "$file"
        echo "Fixed: $file"
    fi
done

# Fix imports in src/raft/
for file in src/raft/*_pb2_grpc.py; do
    if [ -f "$file" ]; then
        sed -i 's/from \. import \(.*\)_pb2/import \1_pb2/' "$file"
        echo "Fixed: $file"
    fi
done

echo "✓ Import fixes complete!"

# Alternative: Make the directories proper Python packages
touch src/__init__.py
touch src/client/__init__.py
touch src/servers/__init__.py
touch src/raft/__init__.py
touch src/utils/__init__.py
