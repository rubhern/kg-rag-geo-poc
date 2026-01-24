import boto3


def put_raw_json(
    *,
    endpoint_url: str,
    access_key: str,
    secret_key: str,
    bucket: str,
    key: str,
    body: bytes,
    content_type: str,
) -> str:
    s3 = boto3.client(
        "s3",
        endpoint_url=endpoint_url,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name="us-east-1",
    )

    s3.put_object(
        Bucket=bucket,
        Key=key,
        Body=body,
        ContentType=content_type,
    )

    return f"s3://{bucket}/{key}"
