#!/bin/bash

# STEP to DXF Web Application Launcher

echo "=== STEP to DXF Web Application ==="
echo "Starting web application server..."

# Conda環境をアクティベート（存在する場合）
if [ -f ~/miniconda3/bin/activate ]; then
    source ~/miniconda3/bin/activate
    if conda env list | grep -q "cad-env"; then
        conda activate cad-env
        echo "Activated conda environment: cad-env"
    else
        echo "Warning: cad-env not found, using default python"
    fi
else
    echo "Using system python3"
fi

# Webアプリディレクトリに移動
cd "/mnt/c/Users/sou16/Desktop/step to dxf"

# テンプレートディレクトリが存在しない場合の確認
if [ ! -d "templates" ]; then
    echo "Creating templates directory..."
    mkdir -p templates
fi

if [ ! -f "templates/index.html" ]; then
    echo "Error: templates/index.html not found!"
    echo "Please ensure the HTML template file exists."
    exit 1
fi

echo "Environment ready. Starting Flask web server..."
echo ""
echo "Web Application Features:"
echo "- Drag & drop STEP file upload"
echo "- Interactive 3D viewer with Three.js"
echo "- Hover for yellow highlight"
echo "- Click for red selection"
echo "- One-click DXF export"
echo "- Responsive web interface"
echo ""
echo "Access the application at:"
echo "  Local:    http://localhost:5000"
echo "  Network:  http://$(hostname -I | awk '{print $1}'):5000"
echo ""
echo "Press Ctrl+C to stop the server"
echo ""

# Flaskアプリケーション実行
export FLASK_APP=app.py
export FLASK_ENV=development

# Python3を使用してアプリケーションを実行
if command -v python3 &> /dev/null; then
    python3 app.py
elif command -v python &> /dev/null; then
    python app.py
else
    echo "Error: Python not found!"
    exit 1
fi