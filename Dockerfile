# Backend image with every toolchain the code executor supports:
# python (base), node, JDK, gcc/g++, php-cli, ruby, go, .NET SDK.
# Deploy on Render as a Docker web service (root dir: backend).

FROM python:3.14-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    DOTNET_CLI_TELEMETRY_OPTOUT=1 \
    DOTNET_SKIP_FIRST_TIME_EXPERIENCE=1 \
    DOTNET_NOLOGO=1

# System toolchains from Debian repos.
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl ca-certificates \
        gcc g++ \
        openjdk-17-jdk-headless \
        nodejs \
        php-cli \
        ruby \
        golang-go \
    && rm -rf /var/lib/apt/lists/*

# .NET SDK 8 — no apt package on plain Debian, use the official script.
RUN curl -sSL https://dot.net/v1/dotnet-install.sh -o /tmp/dotnet-install.sh \
    && bash /tmp/dotnet-install.sh --channel 8.0 --install-dir /usr/share/dotnet \
    && ln -s /usr/share/dotnet/dotnet /usr/local/bin/dotnet \
    && rm /tmp/dotnet-install.sh

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

# Render injects PORT; 8000 is the local default.
EXPOSE 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
