FROM python:3.10-bullseye

ENV PYTHONUNBUFFERED=1
ENV TZ=UTC

RUN pip install tomodachi

COPY app /app
WORKDIR /app

CMD ["tomodachi", "run", "service.py", "--production"]
