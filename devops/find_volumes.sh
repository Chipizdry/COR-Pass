#!/bin/bash

set -e
TIMESTAMP=$(date +%Y%m%d%H%M)
_jq() {
  echo ${row} | base64 --decode | jq -r ${1}
}

for i in $(docker ps -a -q); do
  echo $i;
  volumes=$(docker container inspect $i | jq ".[].Mounts[] | select(.Type==\"volume\")");
  if [[ -z $volumes ]]; then
    echo -e "Volume not found. Skipping...\n\n\n"
    continue;
  else
    echo -e "\n\nVolume found!"
    echo $volumes | jq;
    for row in $(echo "${volumes}" | jq -r '. | @base64'); do
      docker run --rm --volume $(_jq .Name):$(_jq .Destination) -v $HOME/volumes_backup:/volume_backup ubuntu tar cf /volume_backup/$TIMESTAMP"_"$i"_"$(_jq .Name)_backup.tar $(_jq .Destination);
    done
    # echo $volumes | jq ". | .Name,.Source,.Destination";
  fi
done
