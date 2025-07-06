FROM continuumio/miniconda3:latest

WORKDIR /app

# システム依存関係をインストール
RUN apt-get update && apt-get install -y \
    build-essential \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# conda環境をセットアップ
RUN conda config --add channels conda-forge && \
    conda config --set channel_priority strict

# Python 3.9を明示的にインストールしてからpythonocc-coreをインストール
RUN conda install -y -c conda-forge python=3.9 && \
    conda install -y -c conda-forge \
    pythonocc-core \
    flask=2.3.3 \
    numpy \
    matplotlib \
    && conda clean --all -f -y

# インストール確認
RUN python -c "from OCC.Core.STEPControl import STEPControl_Reader; print('pythonocc-core successfully installed')"

# pip経由でその他の依存関係をインストール
RUN pip install --no-cache-dir \
    ezdxf>=1.0.0 \
    Werkzeug==2.3.7 \
    svgwrite \
    gunicorn

# アプリケーションコードをコピー
COPY . .

# ポート5000を公開
EXPOSE 5000

# 環境変数を設定
ENV FLASK_ENV=production
ENV PYTHONUNBUFFERED=1

# アプリケーションを起動
CMD ["python", "app.py"]
