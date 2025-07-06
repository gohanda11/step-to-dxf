FROM ubuntu:22.04

WORKDIR /app

# 環境変数設定
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

# システム依存関係とOpenCASCADEをインストール
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-dev \
    build-essential \
    cmake \
    git \
    wget \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    # OpenCASCADE dependencies
    libopencascade-dev \
    libopencascade-foundation-7.6 \
    libopencascade-modeling-algorithms-7.6 \
    libopencascade-modeling-data-7.6 \
    libopencascade-ocaf-7.6 \
    libopencascade-visualization-7.6 \
    && rm -rf /var/lib/apt/lists/*

# Python3をデフォルトのpythonとして設定
RUN update-alternatives --install /usr/bin/python python /usr/bin/python3 1

# pipを最新に更新
RUN python -m pip install --upgrade pip

# 基本的なPython依存関係をインストール
RUN pip install --no-cache-dir \
    numpy \
    flask==2.3.3 \
    Werkzeug==2.3.7 \
    ezdxf>=1.0.0 \
    svgwrite \
    gunicorn \
    matplotlib

# pythonocc-coreをpipから直接インストール（最新版を試す）
RUN pip install --no-cache-dir pythonocc-core==7.7.2

# インストール確認
RUN python -c "from OCC.Core.STEPControl import STEPControl_Reader; print('✅ pythonocc-core successfully installed')" || \
    (echo "❌ pythonocc-core import failed" && exit 1)

# 最終依存関係確認
RUN python -c "import ezdxf; import svgwrite; from OCC.Core.STEPControl import STEPControl_Reader; print('✅ All dependencies successfully verified')"

# アプリケーションコードをコピー
COPY . .

# ポート5000を公開
EXPOSE 5000

# 環境変数を設定
ENV FLASK_ENV=production
ENV PYTHONUNBUFFERED=1

# アプリケーションを起動
CMD ["python", "app.py"]
