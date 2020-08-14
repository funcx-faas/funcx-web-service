#!/bin/bash

if [[ $(psql -h $POSTGRES_HOST public funcx -c "\dt" | wc | awk '{print $1}') -eq 20 ]]
  then
    echo "Existing database found";
  else
    psql -h $POSTGRES_HOST public funcx -f funcx-schema.sql;
fi
