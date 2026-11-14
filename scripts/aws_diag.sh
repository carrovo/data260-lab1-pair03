#!/bin/sh
# Read-only: why did the EKS stack or node group fail? Result: aws_diag_output.txt
#   sh scripts/aws_diag.sh
OUT=aws_diag_output.txt
R=us-east-1
hide() { sed 's/[0-9]\{12\}/ACCOUNT/g'; }
{
  echo "== date"; date
  echo "== stacks"
  aws cloudformation list-stacks --region $R --query "StackSummaries[?contains(StackName,'p03')].[StackName,StackStatus]" --output text | hide
  echo "== failed events of the node group stack"
  aws cloudformation describe-stack-events --region $R --stack-name eksctl-p03-handshake-nodegroup-p03-nodes \
    --query "StackEvents[?contains(ResourceStatus,'FAILED')].[LogicalResourceId,ResourceStatus,ResourceStatusReason]" --output text 2>&1 | cut -c1-400 | hide
  echo "== cluster"
  aws eks describe-cluster --name p03-handshake --region $R --query "cluster.[status,version]" --output text 2>&1 | hide
  echo "== node group"
  aws eks list-nodegroups --cluster-name p03-handshake --region $R --output text 2>&1 | hide
  aws eks describe-nodegroup --cluster-name p03-handshake --nodegroup-name p03-nodes --region $R --query "nodegroup.[status,health.issues]" --output json 2>&1 | cut -c1-600 | hide
  echo "== instances of the node group"
  aws ec2 describe-instances --region $R --filters "Name=tag:eks:cluster-name,Values=p03-handshake" --query "Reservations[].Instances[].[InstanceId,InstanceType,State.Name,StateReason.Message]" --output text 2>&1 | hide
  echo "== on-demand vCPU quota (Standard instances)"
  aws service-quotas get-service-quota --service-code ec2 --quota-code L-1216C47A --region $R --query "Quota.Value" --output text 2>&1 | hide
} > "$OUT" 2>&1
echo "done: results are in $OUT"
