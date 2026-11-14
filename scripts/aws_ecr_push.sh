#!/bin/sh
# Build the Pair 03 images, create the ECR repositories (if missing) and push them with tag lab2.
# Prints no credentials and hides the account id. Result: aws_ecr_output.txt
#   sh scripts/aws_ecr_push.sh
OUT=aws_ecr_output.txt
REGION=us-east-1
TAG=lab2
IMAGES="application-service assistant-service company-service event-service frontend job-service student-service worker"
hide() { sed 's/[0-9]\{12\}/ACCOUNT/g'; }
{
  echo "== date"; date
  ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
  REG="$ACCOUNT.dkr.ecr.$REGION.amazonaws.com"
  echo "== build the images (docker compose)"
  docker compose --env-file .env.compose build 2>&1 | tail -3 | hide
  echo "== log in to ECR"
  aws ecr get-login-password --region $REGION | docker login --username AWS --password-stdin "$REG" 2>&1 | hide
  for i in $IMAGES; do
    echo "== p03-$i"
    aws ecr describe-repositories --repository-names p03-$i --region $REGION >/dev/null 2>&1 \
      || aws ecr create-repository --repository-name p03-$i --region $REGION --image-scanning-configuration scanOnPush=true --query "repository.repositoryName" --output text | hide
    docker tag p03-$i:dev "$REG/p03-$i:$TAG"
    for attempt in 1 2 3 4; do
      docker push "$REG/p03-$i:$TAG" > /tmp/p03_push.log 2>&1 && { tail -1 /tmp/p03_push.log | hide; break; }
      echo "  push attempt $attempt failed, retrying"; tail -1 /tmp/p03_push.log | cut -c1-120 | hide; sleep 5
    done
  done
  echo "== pushed images"
  for i in $IMAGES; do
    printf "p03-%s: " $i
    aws ecr describe-images --repository-name p03-$i --region $REGION --query "imageDetails[].imageTags" --output text | hide
  done
} > "$OUT" 2>&1
echo "done: results are in $OUT"
