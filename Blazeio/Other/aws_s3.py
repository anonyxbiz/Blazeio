# Blazeio.Other.aws_s3
import Blazeio as io

class S3:
    __slots__ = ("bucket", "region", "aws_key", "aws_secret", "cond")
    def __init__(app, bucket: str, region: str, aws_key: str, aws_secret: str):
        app.bucket, app.region, app.aws_key, app.aws_secret, app.cond = bucket, region, aws_key, aws_secret, io.ioCondition()

    def sign(app, key, msg):
        return io.Scope.hmac_new(key, msg.encode('utf-8'), io.Scope.sha256).digest()

    def get_signature_key(app, key, date, region, service):
        k_date = app.sign(('AWS4' + key).encode('utf-8'), date)
        k_region = app.sign(k_date, region)
        k_service = app.sign(k_region, service)
        return app.sign(k_service, 'aws4_request')
    
    def url(app, file_path: str):
        if not file_path.startswith("/"):
            file_path = "/%s" % file_path
        return "https://%s%s" % ("%s.s3.%s.amazonaws.com" % (app.bucket, app.region), file_path)

    def s3_headers(app, file_path: str, bucket: str, region: str, aws_key: str, aws_secret: str, headers: dict, service: str = "s3", method: str = "PUT", payload_hash: str = "UNSIGNED-PAYLOAD"):
        if not file_path.startswith("/"):
            file_path = "/%s" % file_path

        host = "%s.s3.%s.amazonaws.com" % (bucket, region)
        endpoint = "https://%s%s" % (host, file_path)
        now = io.dt.now(io.UTC)
        amz_date = now.strftime('%Y%m%dT%H%M%SZ')
        date_stamp = now.strftime('%Y%m%d')
        canonical_uri = file_path
        canonical_headers = "host:%s\nx-amz-content-sha256:%s\nx-amz-date:%s\n" % (host, payload_hash, amz_date)
        signed_headers = "host;x-amz-content-sha256;x-amz-date"
        canonical_request = "%s\n%s\n\n%s\n%s\n%s" % (method, canonical_uri, canonical_headers, signed_headers, payload_hash)
        algorithm = "AWS4-HMAC-SHA256"
        credential_scope = "%s/%s/%s/aws4_request" % (date_stamp, region, service)

        headers.update({
            "x-amz-content-sha256": payload_hash,
            "Authorization": "%s Credential=%s/%s, SignedHeaders=%s, Signature=%s" % (algorithm, aws_key, credential_scope, signed_headers, io.Scope.hmac_new(app.get_signature_key(aws_secret, date_stamp, region, service), ("%s\n%s\n%s\n%s" % (algorithm, amz_date, credential_scope, io.Scope.sha256(canonical_request.encode()).hexdigest())).encode('utf-8'), io.Scope.sha256).hexdigest()),
            "x-amz-date": amz_date
        })

        return io.ddict(url=endpoint, method=method, headers=headers)

    def authorize(app, filepath: str, headers: dict = {}):
        return app.s3_headers(filepath, app.bucket, app.region, app.aws_key, app.aws_secret, headers or io.ddict(headers))

    async def aauthorize(app, *args, **kwargs):
        async with app.cond:
            return await io.to_thread(app.authorize, *args, **kwargs)

if __name__ == "__main__": ...