ARG IMAGE=python:3.12.0-slim-bullseye

##############################################################
###             Stage : Source Copy                        ###
##############################################################
FROM ${IMAGE} AS product

## Labelling
LABEL company="Mobigen" \
        team="mobigen-platform-team" \
        email="irisdev@mobigen.com"

COPY ./src /app/src
COPY ./requirements.txt /app
COPY ./config_templates/config-dev.yml /app/config_templates/config-dev.yml

WORKDIR /app

RUN apt-get update -y \
    && apt-get install -y \
    libpq-dev \
    build-essential

RUN pip3 install --upgrade pip \
    && pip3 install --no-cache-dir -r requirements.txt

ENTRYPOINT ["python", "src/main.py"]

