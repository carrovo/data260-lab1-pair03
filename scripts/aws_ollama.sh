#!/bin/sh
# Add the Ollama model server (qwen3:8b) to the running EKS deployment and test it.
#   sh scripts/aws_ollama.sh        Result: aws_ollama_output.txt   (first run downloads ~5 GB: 5-15 minutes)
OUT=aws_ollama_output.txt
REGION=us-east-1
hide() { sed 's/[0-9]\{12\}/ACCOUNT/g'; }
CTX=$(kubectl config current-context)
case "$CTX" in *p03-handshake*) ;; *) echo "kubectl context is '$CTX', not the EKS cluster."; exit 1;; esac
{
  echo "== date"; date
  ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
  rm -rf .aws_build && mkdir .aws_build && cp -R k8s .aws_build/k8s && cp -R aws .aws_build/aws
  sed -i.bak "s/ACCOUNT_ID/$ACCOUNT/g" .aws_build/aws/overlay/kustomization.yaml && rm .aws_build/aws/overlay/kustomization.yaml.bak
  kubectl -n p03 delete job p03-ollama-pull --ignore-not-found
  echo "== apply"
  kubectl apply -k .aws_build/aws/overlay 2>&1 | hide
  echo "== wait for the Ollama pod"
  kubectl -n p03 rollout status deploy/p03-ollama --timeout=900s
  echo "== model download (first run is slow)"
  kubectl -n p03 wait --for=condition=complete job/p03-ollama-pull --timeout=1800s
  kubectl -n p03 logs job/p03-ollama-pull | tail -5
  echo "== assistant now points at"
  kubectl -n p03 rollout status deploy/p03-assistant-service --timeout=300s
  kubectl -n p03 get deploy p03-assistant-service -o jsonpath='{.spec.template.spec.containers[0].env[?(@.name=="OLLAMA_BASE_URL")].value}'; echo
  echo "== Ollama version in the pod"
  kubectl -n p03 exec deploy/p03-ollama -- ollama --version 2>&1 | tail -2
  echo "== one answer from the model, timed"
  S=$(date +%s)
  kubectl -n p03 exec deploy/p03-ollama -- ollama run qwen3:8b "Reply with the single word: ready" 2>&1 | tail -3
  echo "seconds: $(( $(date +%s) - S ))"
  echo "== pods"; kubectl -n p03 get pods -o wide | hide
} > "$OUT" 2>&1
echo "done: results are in $OUT"
