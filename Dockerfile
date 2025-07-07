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

# Python 3.10と必要な依存関係をインストール
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
    # OpenCASCADE dependencies
    libopencascade-dev \
    libopencascade-foundation-7.6 \
    libopencascade-modeling-algorithms-7.6 \
    libopencascade-modeling-data-7.6 \
    libopencascade-ocaf-7.6 \
    libopencascade-visualization-7.6 \
    && rm -rf /var/lib/apt/lists/*

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

# Install Miniconda for Python 3.10
RUN wget https://repo.anaconda.com/miniconda/Miniconda3-py310_24.1.2-0-Linux-x86_64.sh -O /tmp/miniconda.sh && \
    bash /tmp/miniconda.sh -b -p /opt/conda && \
    rm /tmp/miniconda.sh

# Update PATH to use conda
ENV PATH="/opt/conda/bin:$PATH"

# Create conda environment with Python 3.10 and install pythonocc-core
RUN conda create -n step-env python=3.10 -y && \
    conda install -n step-env -c conda-forge pythonocc-core=7.7.2 numpy flask werkzeug matplotlib -y && \
    /opt/conda/envs/step-env/bin/pip install ezdxf svgwrite gunicorn

# Activate environment permanently
ENV CONDA_DEFAULT_ENV=step-env
ENV PATH="/opt/conda/envs/step-env/bin:$PATH"

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
