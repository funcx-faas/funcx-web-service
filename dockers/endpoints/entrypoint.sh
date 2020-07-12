cp /run/secrets/web_cert /usr/local/share/ca-certificates/
update-ca-certificates
tail -f /dev/null
#funcx-endpoint init
#funcx-endpoint configure default
#funcx-endpoint start default --endpoint_uuid 88888888-4444-4444-4444-cccccccccccc