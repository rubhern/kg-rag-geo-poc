FROM apache/hive:standalone-metastore-4.2.0

USER root

# --- JDBC (PostgreSQL) for the metastore DB ---
WORKDIR /opt/hive/lib
ADD lib/postgresql.jar .

# --- S3A libs (Hadoop AWS + AWS SDK bundle) ---
# These are commonly required so Hive/Hadoop can resolve s3a:// (MinIO is S3-compatible).
# If versions mismatch, we'll align them to the Hadoop version inside the image.

ADD lib/hadoop-aws-3.4.1.jar /opt/hadoop/share/hadoop/common/lib/
ADD lib/bundle-2.24.6.jar /opt/hadoop/share/hadoop/common/lib/

# Copy Hadoop config for S3A
COPY core-site.xml /opt/hive/conf/core-site.xml

USER hive
