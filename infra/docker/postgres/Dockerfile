FROM postgis/postgis:16-3.4

RUN set -eux; \
  apt-get update; \
  apt-get install -y --no-install-recommends \
    ca-certificates git build-essential postgresql-server-dev-16 \
    clang llvm; \
  ln -sf "$(command -v clang)" /usr/bin/clang-13; \
  mkdir -p /usr/lib/llvm-13/bin; \
  ln -sf "$(command -v llvm-lto)" /usr/lib/llvm-13/bin/llvm-lto; \
  rm -rf /var/lib/apt/lists/*

RUN set -eux; \
  git clone --depth 1 https://github.com/pgvector/pgvector.git /tmp/pgvector; \
  make -C /tmp/pgvector; \
  make -C /tmp/pgvector install; \
  rm -rf /tmp/pgvector
