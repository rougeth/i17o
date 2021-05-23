FROM python:slim

RUN apt update && apt install -y --no-install-recommends gcc
RUN pip install --no-cache-dir pipenv

WORKDIR /usr/src/app
COPY Pipfile Pipfile.lock .
RUN pipenv install --system --deploy

COPY . .
CMD [ "python", "docs.py" ]
