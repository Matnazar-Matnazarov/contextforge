#!/bin/sh
# Renders the S3 identity file from environment variables at container start so that no
# credentials are ever committed. Then starts master+volume+filer+S3 in one process (dev mode).
set -eu
: "${S3_ACCESS_KEY:?S3_ACCESS_KEY is required}"
: "${S3_SECRET_KEY:?S3_SECRET_KEY is required}"
cat > /tmp/s3.json <<JSON
{"identities":[{"name":"app","credentials":[{"accessKey":"${S3_ACCESS_KEY}","secretKey":"${S3_SECRET_KEY}"}],"actions":["Admin","Read","Write","List","Tagging"]}]}
JSON
exec weed server -dir=/data -master.volumeSizeLimitMB=256 -volume.max=50 -filer -s3 -s3.port=8333 -s3.config=/tmp/s3.json -ip.bind=0.0.0.0
