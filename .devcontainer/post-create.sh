#!/bin/bash

# Post-create script for UEIL Data Store dev container
echo "🚀 Setting up UEIL Data Store development environment..."

# Make scripts executable
chmod +x /workspace/scripts/*.py 2>/dev/null || true

# Install Python client library in development mode
if [ -d "/workspace/clients/python" ]; then
    echo "📦 Installing Python client library..."
    pip install -e /workspace/clients/python
fi

# Set up git (if not already configured)
if [ -z "$(git config --global user.name)" ]; then
    echo "⚠️  Git not configured. Please run:"
    echo "   git config --global user.name 'Your Name'"
    echo "   git config --global user.email 'your.email@example.com'"
fi

# Create environment file if it doesn't exist
if [ ! -f "/workspace/.env" ]; then
    echo "📝 Creating .env file from template..."
    cp /workspace/env.template /workspace/.env
    echo "✅ Created .env file. Please edit with your settings."
fi

# Test Python installation
echo "🐍 Testing Python installation..."
python --version
pip list | grep -E "(fastapi|streamlit|requests|pyyaml)" || echo "⚠️  Some packages may need installation"

# Display helpful information
echo ""
echo "🎉 Development environment ready!"
echo ""
echo "📋 Available services:"
echo "   • PostgreSQL: localhost:5432"
echo "   • MinIO API: localhost:9000"  
echo "   • MinIO Console: localhost:9001"
echo "   • FastAPI Backend: localhost:8001"
echo "   • Streamlit Frontend: localhost:8501"
echo ""
echo "🔧 Useful commands:"
echo "   • Test setup: python scripts/test_setup.py"
echo "   • Start services: docker-compose up"
echo "   • View logs: docker-compose logs"
echo ""
echo "📚 Documentation:"
echo "   • Setup guide: docs/setup.md"
echo "   • API docs: docs/api.md"
echo "   • Main README: README.md"
echo ""
echo "Happy coding! 🚀"
