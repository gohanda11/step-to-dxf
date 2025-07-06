FROM mambaorg/micromamba:1.5.1

WORKDIR /app

USER root

# システム依存関係をインストール
RUN apt-get update && apt-get install -y \
    build-essential \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    wget \
    && rm -rf /var/lib/apt/lists/*

USER $MAMBA_USER

# mambaを使用してより確実にパッケージをインストール
RUN micromamba install -y -n base -c conda-forge \
    python=3.9 \
    pythonocc-core \
    flask=2.3.3 \
    numpy \
    matplotlib \
    pip \
    && micromamba clean --all --yes

# 環境をアクティベート
ARG MAMBA_DOCKERFILE_ACTIVATE=1

# インストール確認
RUN python -c "from OCC.Core.STEPControl import STEPControl_Reader; print('✅ pythonocc-core successfully installed')" || \
    (echo "❌ pythonocc-core import failed" && exit 1)

# pip経由でその他の依存関係をインストール
RUN pip install --no-cache-dir \
    ezdxf>=1.0.0 \
    Werkzeug==2.3.7 \
    svgwrite \
    gunicorn

# 最終インストール確認
RUN python -c "import ezdxf; import svgwrite; from OCC.Core.STEPControl import STEPControl_Reader; print('✅ All dependencies installed successfully')"

# アプリケーションコードをコピー
COPY --chown=$MAMBA_USER:$MAMBA_USER . .

# ポート5000を公開
EXPOSE 5000

# 環境変数を設定
ENV FLASK_ENV=production
ENV PYTHONUNBUFFERED=1
ENV PATH="/opt/conda/bin:$PATH"

# 実行権限を確保
USER $MAMBA_USER

# アプリケーションを起動
CMD ["python", "app.py"]
