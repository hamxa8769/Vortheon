#!/bin/bash
# NULLAI CORE — ONE-CLICK SETUP
# Run this after cloning the repo

echo "🛡️  NullAI Core Setup"
echo "====================="

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 not found. Install it first."
    exit 1
fi

# Create virtual environment
echo "📦 Creating virtual environment..."
python3 -m venv venv
source venv/bin/activate

# Install dependencies
echo "📦 Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Check Docker
if ! command -v docker &> /dev/null; then
    echo "⚠️  Docker not found. Install Docker Desktop for container orchestration."
else
    echo "✅ Docker found"
fi

# Check Ollama
if ! command -v ollama &> /dev/null; then
    echo "⚠️  Ollama not found. Install from ollama.com for local model serving."
    echo "   curl -fsSL https://ollama.com/install.sh | sh"
else
    echo "✅ Ollama found"
    echo "📥 Pulling llama3.2 (3B model, runs on CPU)..."
    ollama pull llama3.2
fi

echo ""
echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo "  1. Start Redis:  docker run -d --name nullai-redis -p 6379:6379 redis:7-alpine redis-server --save "" --appendonly no"
echo "  2. Start API:     uvicorn platform.api_gateway:app --host 0.0.0.0 --port 8000 --reload"
echo "  3. Test:          curl http://localhost:8000/health"
echo ""
echo "🚀 Build the empire."
