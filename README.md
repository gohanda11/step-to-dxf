# STEP to DXF/SVG Converter

A web-based application that converts STEP files to DXF or SVG format with an interactive 3D viewer for face selection.

## Features

- 📁 Upload STEP files (.step, .stp)
- 🎯 Interactive 3D viewer with face selection
- 💡 Hover highlighting and click selection
- 📥 Export individual faces to DXF or SVG format
- 🎮 3D navigation controls (rotate, zoom, pan)
- 📱 Responsive web interface

## Usage

1. Upload a STEP file using the file selector
2. View the 3D model in the interactive viewer
3. Hover over faces to see them highlighted in yellow
4. Click on faces to select them (highlighted in red)
5. Use the "Export" button to download the selected face as DXF or SVG

## 3D Viewer Controls

- **Rotate**: Left-click and drag
- **Zoom**: Mouse wheel
- **Pan**: Right-click and drag

## Technology Stack

- **Backend**: Python Flask
- **3D Processing**: OpenCASCADE (PythonOCC)
- **CAD Export**: ezdxf, svgwrite
- **Frontend**: Three.js for 3D visualization
- **Deployment**: Docker-ready for cloud platforms

## Local Development

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Run the application:
   ```bash
   python app.py
   ```

3. Open your browser and navigate to `http://localhost:5000`

## Deployment

This application is configured for deployment on Render.com and other cloud platforms using Docker.

## License

MIT License