FROM python:alpine

RUN pip install --no-cache-dir poetry

COPY pyproject.toml poetry.lock ./
RUN poetry config settings.virtualenvs.create false
RUN poetry install --no-dev --no-interaction

COPY . .
CMD [ "poetry" "run" "python", "./stats.py" ]