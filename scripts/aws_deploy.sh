#!/bin/sh
# Deploy Pair 03 to the EKS cluster. Refuses to run unless kubectl points at p03-handshake.
#   sh scripts/aws_deploy.sh        Result: aws_deploy_output.txt
OUT=aws_deploy_output.txt
REGION=us-east-1
hide() { sed 's/[0-9]\{12\}/ACCOUNT/g'; }
CTX=$(kubectl config current-context)
case "$CTX" in *p03-handshake*) ;; *) echo "kubectl context is '$CTX', not the EKS cluster. Run: aws eks update-kubeconfig --name p03-handshake --region $REGION" ; exit 1;; esac
{
  echo "== date"; date
  echo "== context"; echo "$CTX" | hide
  ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
  rm -rf .aws_build && mkdir .aws_build && cp -R k8s .aws_build/k8s && cp -R aws .aws_build/aws
  sed -i.bak "s/ACCOUNT_ID/$ACCOUNT/g" .aws_build/aws/overlay/kustomization.yaml && rm .aws_build/aws/overlay/kustomization.yaml.bak
  echo "== only one default StorageClass (gp2 off, p03-gp3 on)"
  kubectl annotate sc gp2 storageclass.kubernetes.io/is-default-class- 2>&1 | tail -1
  echo "== namespace and Secret (from .env.compose, never committed)"
  kubectl apply -f k8s/namespace.yaml
  kubectl -n p03 create secret generic p03-secrets --from-env-file=.env.compose --dry-run=client -o yaml | kubectl apply -f - | hide
  echo "== apply"
  kubectl delete job -n p03 p03-db-init p03-kafka-init p03-seed --ignore-not-found
  kubectl apply -k .aws_build/aws/overlay 2>&1 | hide
  echo "== wait for the data stores, then the jobs, then the services"
  kubectl -n p03 rollout status statefulset/p03-mysql --timeout=600s
  kubectl -n p03 rollout status statefulset/p03-mongo --timeout=600s
  kubectl -n p03 rollout status statefulset/p03-kafka --timeout=600s
  kubectl -n p03 wait --for=condition=complete job/p03-db-init job/p03-kafka-init --timeout=600s
  for d in $(kubectl -n p03 get deploy -o name); do kubectl -n p03 rollout status $d --timeout=600s; done
  echo "== seed the demo data (SEED=3)"
  sed "s#image: p03-company-service:dev#image: $ACCOUNT.dkr.ecr.$REGION.amazonaws.com/p03-company-service:lab2#" k8s/optional/seed-job.yaml | kubectl apply -f - | hide
  kubectl -n p03 wait --for=condition=complete job/p03-seed --timeout=600s
  kubectl -n p03 logs job/p03-seed | tail -8
  echo "== pods"; kubectl -n p03 get pods -o wide | hide
  echo "== services"; kubectl -n p03 get svc
  echo "== frontend load balancer (can take 2-3 minutes to appear)"
  for i in 1 2 3 4 5 6 7 8 9 10 11 12; do
    H=$(kubectl -n p03 get svc p03-frontend -o jsonpath='{.status.loadBalancer.ingress[0].hostname}')
    [ -n "$H" ] && break; sleep 15
  done
  echo "$H"
} > "$OUT" 2>&1
echo "done: results are in $OUT"
