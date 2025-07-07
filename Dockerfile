FROM ubuntu:22.04

WORKDIR /app

# 環境変数設定
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

# PPAを追加してPython 3.10をインストール（pythonocc-coreと互換性があるバージョン）
RUN apt-get update && apt-get install -y \
    software-properties-common \
    && add-apt-repository ppa:deadsnakes/ppa \
    && apt-get update

# Python 3.10と必要な依存関係をインストール（OpenCASCADEは除く）
RUN apt-get install -y \
    python3.10 \
    python3.10-dev \
    python3.10-distutils \
    python3.10-venv \
    build-essential \
    cmake \
    git \
    wget \
    curl \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Try to install OpenCASCADE if available (optional)
RUN apt-get update && apt-get install -y \
    libopencascade-dev \
    && rm -rf /var/lib/apt/lists/* \
    || echo "OpenCASCADE not available via apt, will use conda version"

# Python 3.10をデフォルトのpythonとして設定
RUN update-alternatives --install /usr/bin/python python /usr/bin/python3.10 1
RUN update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.10 1

# pipをインストール
RUN curl https://bootstrap.pypa.io/get-pip.py | python3.10

# Pythonバージョンの確認
RUN python --version && python3 --version

# 基本的なPython依存関係をインストール
RUN pip install --no-cache-dir \
    numpy \
    flask==2.3.3 \
    Werkzeug==2.3.7 \
    ezdxf>=1.0.0 \
    svgwrite \
    gunicorn \
    matplotlib

# Install Miniconda
RUN wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh -O /tmp/miniconda.sh && \
    bash /tmp/miniconda.sh -b -p /opt/conda && \
    rm /tmp/miniconda.sh

# Update PATH to use conda
ENV PATH="/opt/conda/bin:$PATH"

# Install pythonocc-core and dependencies via conda
RUN conda install -c conda-forge python=3.10 pythonocc-core numpy flask werkzeug matplotlib -y && \
    pip install ezdxf svgwrite gunicorn

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
