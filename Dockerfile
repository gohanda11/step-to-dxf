FROM python:3.9-slim

WORKDIR /app

# システム依存関係をインストール
RUN apt-get update && apt-get install -y \
    build-essential \
    cmake \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Python依存関係をインストール
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# アプリケーションコードをコピー
COPY . .

# ポート5000を公開
EXPOSE 5000

# 環境変数を設定
ENV FLASK_ENV=production
ENV PYTHONUNBUFFERED=1

# アプリケーションを起動
CMD ["python", "app.py"]