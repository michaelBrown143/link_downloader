FROM python:3.12-slim

ENV AM_I_IN_A_DOCKER_CONTAINER=Yes
ENV FLASK_APP=app.py

RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt ./

RUN python -m pip install --upgrade pip setuptools wheel && \
    python -m pip install --no-cache-dir --upgrade -r requirements.txt

COPY . .

EXPOSE 5555

CMD ["flask", "run", "--host=0.0.0.0", "--port=5555"]
