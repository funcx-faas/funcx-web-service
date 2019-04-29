source activate funcx

NAME="FuncX"
FLASKDIR=/home/ubuntu/funcx-web-service/
SOCKFILE=/home/ubuntu/funcx-web-service/funcx.sock
USER=ubuntu
GROUP=ubuntu
NUM_WORKERS=3
echo "Starting $NAME"

# Create the run directory if it doesn't exist
RUNDIR=$(dirname $SOCKFILE)
test -d $RUNDIR || mkdir -p $RUNDIR

# Start your gunicorn
#exec gunicorn run:app -b 0.0.0.0:443 \
exec gunicorn app:app -b 0.0.0.0:8080 \
  --name $NAME \
  --workers $NUM_WORKERS \
  --user=$USER --group=$GROUP \
  --bind=unix:$SOCKFILE \
  --log-level DEBUG \
  --log-file /home/ubuntu/funcx-web-service/funcx.log \
  --timeout 600

