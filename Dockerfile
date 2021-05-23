FROM python:slim

RUN apt update && apt install -y --no-install-recommends gcc

RUN pip install --no-cache-dir pipenv
COPY Pipfile Pipfile.lock ./
RUN pipenv install --system --deploy

COPY . .
CMD [ "python", "./stats.py" ]
