#FROM python:3.8
#RUN pip install awscli
#COPY entrypoint.sh entrypoint.sh
#RUN chmod +x entrypoint.sh
#RUN mkdir documents
#RUN touch ./documents/document.pdf
#ENTRYPOINT ["/entrypoint.sh"]
# ADD requirements.txt .
#RUN pip install -r requirements.txt
#RUN apt-get update
#RUN apt-get install poppler-utils -y
#COPY conf/** /conf/
#COPY controllers/** /controllers/
#COPY models/** /models/
#COPY routers/** /routers/
#COPY swagger/** /swagger/
# ADD api.py .

#########################3

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

WORKDIR /app

COPY pyproject.toml .

RUN python -c "import tomllib, subprocess; \
deps = tomllib.load(open('pyproject.toml','rb'))['project']['dependencies']; \
subprocess.check_call(['pip', 'install', '--no-cache-dir', *deps])"

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

RUN mkdir -p /documents && touch /documents/document.pdf

COPY conf/ /app/conf/
COPY controllers/ /app/controllers/
COPY models/ /app/models/
COPY routers/ /app/routers/
COPY swagger/ /app/swagger/
COPY api.py /app/api.py

ENTRYPOINT ["/entrypoint.sh"]
