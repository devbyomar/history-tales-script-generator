#!/bin/bash
# ============================================================
# History Tales — Deployment Script
# ============================================================
# This script helps deploy both services:
#   - API (FastAPI) → Fly.io
#   - Web (Next.js) → Vercel
# ============================================================

set -e

echo "🎬 History Tales Deployment"
echo "=========================="
echo ""

# --- Pre-flight checks ---
command -v flyctl >/dev/null 2>&1 || {
    echo "❌ flyctl not found. Install it:"
    echo "   curl -L https://fly.io/install.sh | sh"
    echo ""
    echo "Or on macOS:"
    echo "   brew install flyctl"
    exit 1
}

# --- Deploy API to Fly.io ---
echo "🚀 Deploying API to Fly.io..."
echo ""

# Set secrets (only needed first time)
if [ "$1" == "--set-secrets" ]; then
    echo "Setting secrets..."
    read -p "Enter OPENAI_API_KEY: " api_key
    flyctl secrets set OPENAI_API_KEY="$api_key"
    
    read -p "Enter OPENAI_MODEL (default: gpt-4o): " model
    model=${model:-gpt-4o}
    flyctl secrets set OPENAI_MODEL="$model"
    
    read -p "Enter OPENAI_FAST_MODEL (default: gpt-4o-mini): " fast_model
    fast_model=${fast_model:-gpt-4o-mini}
    flyctl secrets set OPENAI_FAST_MODEL="$fast_model"
    
    read -p "Enter your Vercel frontend URL (e.g., https://history-tales.vercel.app): " frontend_url
    flyctl secrets set CORS_ORIGINS="$frontend_url,http://localhost:3000"
    
    echo "✅ Secrets set."
    echo ""
fi

flyctl deploy

echo ""
echo "✅ API deployed!"
echo ""

API_URL=$(flyctl info --json 2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin).get('Hostname',''))" 2>/dev/null || echo "your-app.fly.dev")
echo "📡 API URL: https://${API_URL}"
echo ""
echo "=================================================="
echo ""
echo "🌐 Next: Deploy the frontend to Vercel"
echo ""
echo "1. Go to https://vercel.com/new"
echo "2. Import your GitHub repo: devbyomar/history-tales-script-generator"
echo "3. Set Root Directory to: web"
echo "4. Add environment variable:"
echo "   NEXT_PUBLIC_API_URL = https://${API_URL}"
echo "5. Click Deploy"
echo ""
echo "✅ Done! Your full-stack app will be live."
echo "=================================================="
