cp /run/secrets/web_cert /usr/local/share/ca-certificates/
update-ca-certificates

[ -d "/funcx" ] && pip install -q -e /funcx

mkdir /root/.funcx
mkdir /root/.funcx/credentials
cp /run/secrets/funcx_sdk_tokens /root/.funcx/credentials/funcx_sdk_tokens.json
cp /run/secrets/funcx_config /root/.funcx/config.py

sh /data/wait-for.sh forwarder:8080

[ ! -e /root/.funcx/default ] && funcx-endpoint configure default
funcx-endpoint stop default
funcx-endpoint -d start default --endpoint_uuid 88888888-4444-4444-4444-cccccccccccc

jupyter notebook --port=8888 --no-browser --ip=0.0.0.0 --allow-root
#CMD ["jupyter", "notebook", "--port=8888", "--no-browser", "--ip=0.0.0.0"]
