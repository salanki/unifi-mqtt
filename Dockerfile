FROM python:2.7 
MAINTAINER Peter Salanki <peter@salanki.st>

RUN apt-get update && apt-get install -y -q --no-install-recommends zip libsasl2-dev python-dev libldap2-dev libssl-dev

RUN mkdir -p /app
ADD requirements.txt /app
WORKDIR /app

RUN pip install -r requirements.txt

ADD . /app

CMD python unifi.py
