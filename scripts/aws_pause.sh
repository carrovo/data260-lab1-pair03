#!/bin/sh
# Pause (down) or resume (up) the EKS nodes to save credit. Volumes, images, manifests and the
# cluster stay; only the worker nodes stop (the control plane still costs about $2.4 per day).
#   sh scripts/aws_pause.sh down      sh scripts/aws_pause.sh up
case "$1" in
  down) eksctl scale nodegroup --cluster p03-handshake --region us-east-1 --name p03-nodes --nodes 0 --nodes-min 0 ;;
  up)   eksctl scale nodegroup --cluster p03-handshake --region us-east-1 --name p03-nodes --nodes 2 --nodes-min 0 --nodes-max 3
        echo "After the nodes are Ready (kubectl get nodes) the pods restart by themselves; check: kubectl -n p03 get pods" ;;
  *) echo "usage: sh scripts/aws_pause.sh down|up"; exit 1 ;;
esac
