FROM python:3.8-slim

COPY requirements.txt ./
RUN pip install -r requirements.txt && rm -f requirements.txt

COPY app /app
WORKDIR /app

ENV PYTHONUNBUFFERED=1

CMD ["tomodachi", "run", "service.py", "--production"]
