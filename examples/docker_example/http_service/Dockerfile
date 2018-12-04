FROM kalaspuff/python-nginx-proxy:1.2.3

WORKDIR /

ADD requirements.txt .
RUN apt-get -y update \
    && apt-get install -y build-essential=12.3 \
    && pip install -r requirements.txt \
    && rm -f requirements.txt \
    && apt-get purge -y --auto-remove build-essential \
    && apt-get clean autoclean \
    && apt-get autoremove -y \
    && rm -rf /var/lib/{apt,dpkg,cache,log}/

WORKDIR /app
ADD app /app/

CMD tomodachi run service.py --production
