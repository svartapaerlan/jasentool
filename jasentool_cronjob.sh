#!/bin/bash

if [ "$1" == "missing" ]; then
  current_date=$(date +"%y%m%d")
  conda run -n jasentool jasentool missing --db_name cgviz --db_collection sample --analysis_dir /fs1/results_dev/jasen/saureus/analysis_result/ --restore_dir /fs1/ryan/pipelines/jasen/reruns/seqdata/ --restore_file /data/bnf/dev/ryan/pipelines/jasen/reruns/saureus_${current_date}.sh -o /data/bnf/dev/ryan/pipelines/jasen/reruns/saureus_${current_date}.csv
  seqrunid=$(head -2 /data/tmp/multi_microbiology.csv | tail -1 | cut -d',' -f7 | cut -d'/' -f5)
  conda run -n jasentool jasentool fix --csv_file /data/bnf/dev/ryan/pipelines/jasen/reruns/saureus_${current_date}.csv --sh_file /data/bnf/dev/ryan/pipelines/jasen/reruns/saureus_${current_date}.sh -o ${seqrunid}_jasen.csv --remote_dir /fs1/ryan/pipelines/jasen/bjorn/ --remote --auto-start
else
  seqrunid=$(head -2 /data/tmp/multi_microbiology.csv | tail -1 | cut -d',' -f7 | cut -d'/' -f5)
  conda run -n jasentool jasentool fix --csv_file /data/tmp/multi_microbiology.csv --sh_file /data/tmp/multi_microbiology.sh -o ${seqrunid}_jasen.csv --remote_dir /fs1/ryan/pipelines/jasen/bjorn/ --remote --auto-start
fi
