FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    poppler-utils \
    gcc \
    libffi-dev \
    libssl-dev \
    make \
    curl \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /

COPY pyproject.toml .

RUN python -c "import tomllib, subprocess; \
deps = tomllib.load(open('pyproject.toml','rb'))['project']['dependencies']; \
subprocess.check_call(['pip', 'install', '--no-cache-dir', *deps])"

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

RUN mkdir -p /documents

COPY conf/ /conf/
COPY controllers/ /controllers/
COPY models/ /models/
COPY routers/ /routers/
COPY api.py /api.py

ENTRYPOINT ["/entrypoint.sh"]
