#!/bin/bash

MOUNT_DIR=/mnt

echo "Starting the quota crawler script"
count=0
while true; do

  dirs=$(/bin/ls -d $MOUNT_DIR/*/subvol 2>/dev/null| wc -l);
  if [ $dirs -lt 1 ] ; then
    if [ $((count % 100)) -eq 0 ]; then
      echo "No PVC yet, continuing to watch..."
    fi
    sleep 10;
    count=$((count + 1));
    continue;
  fi

  # Subdir is in the form /mnt/$host-volname/subvol/NN/MM/PVCNAME
  for dir in $(find $MOUNT_DIR/*/subvol/*/* -maxdepth 1 -mindepth 1 -type d); do
    used_size=$(df -B1 ${dir}  | tail -n1 | awk '{print $3}');
    out=$(setfattr -n glusterfs.quota.total-usage -v ${used_size} $dir 2>&1);
    if ! [[ "$out" =~ "Operation not supported" ]]; then
      echo "$out"
    fi
    if [ $((count % 1000)) -eq 0 ]; then
      echo "Latest consumption on $dir : $used_size"
      echo "Empty if setfattr is successful: --$out--"
    fi
  done

  sleep 5;
  count=$((count + 1));
done

echo "Exiting the quota crawler script"
