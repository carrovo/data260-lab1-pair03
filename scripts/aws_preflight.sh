#!/bin/sh
# Read-only AWS checks before the EKS deployment (creates nothing, prints no keys).
# The 12-digit account id is replaced with ACCOUNT. Result: aws_preflight_output.txt
#   sh scripts/aws_preflight.sh
OUT=aws_preflight_output.txt
r() { echo; echo "\$ $*"; "$@" 2>&1 | sed 's/[0-9]\{12\}/ACCOUNT/g' | head -${LINES_MAX:-25}; }
{
  echo "== date"; date
  r aws sts get-caller-identity --query Arn --output text
  echo "== region"; aws configure get region
  echo "== existing EKS clusters (an assigned one would be listed)"
  r aws eks list-clusters
  echo "== existing ECR repositories"
  r aws ecr describe-repositories --query "repositories[].repositoryName"
  echo "== this user's policies"
  r aws iam list-attached-user-policies --user-name data260-cli-user
  r aws iam list-groups-for-user --user-name data260-cli-user
  echo "== networking available"
  r aws ec2 describe-vpcs --query "Vpcs[].{id:VpcId,default:IsDefault}"
  r aws ec2 describe-availability-zones --query "AvailabilityZones[].ZoneName"
  echo "== tools"
  r kubectl version --client
  r eksctl version
  r docker version --format "{{.Server.Os}}/{{.Server.Arch}}"
  r aws --version
  echo "== kubectl contexts (no secrets)"
  r kubectl config get-contexts -o name
} > "$OUT" 2>&1
echo "done: results are in $OUT"
