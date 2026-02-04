FROM python:3.12-slim

WORKDIR /usr/app

RUN apt-get update \
  && apt-get install -y --no-install-recommends git ca-certificates \
  && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir dbt-core dbt-trino

ENTRYPOINT ["dbt"]
