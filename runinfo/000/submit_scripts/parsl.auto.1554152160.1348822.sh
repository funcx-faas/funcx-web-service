
export CORES=$(getconf _NPROCESSORS_ONLN)
echo "Found cores : $CORES"
WORKERCOUNT=1

CMD ( ) {
process_worker_pool.py --debug --max_workers=1 -c 1 --poll 10 --task_url=tcp://127.0.0.1:54041 --result_url=tcp://127.0.0.1:54826 --logdir=/home/ubuntu/aps-pilot/aps_pilot/runinfo/000/htex_local --hb_period=30 --hb_threshold=120 --mode=singularity_reuse --container_image=/home/ubuntu/sing-run/sing-run.simg 
}
for COUNT in $(seq 1 1 $WORKERCOUNT)
do
    echo "Launching worker: $COUNT"
    CMD &
done
wait
echo "All workers done"
