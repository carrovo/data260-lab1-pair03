#!/bin/sh
# Read-only: why did the node group launch no instances? Result: aws_diag2_output.txt
OUT=aws_diag2_output.txt
R=us-east-1
hide() { sed 's/[0-9]\{12\}/ACCOUNT/g'; }
{
  echo "== date"; date
  ASG=$(aws autoscaling describe-auto-scaling-groups --region $R --query "AutoScalingGroups[?contains(AutoScalingGroupName,'p03')].AutoScalingGroupName" --output text)
  echo "== auto scaling group: $ASG" | hide
  echo "== scaling activities (the reason a launch failed is here)"
  aws autoscaling describe-scaling-activities --region $R --auto-scaling-group-name "$ASG" --max-items 5 \
    --query "Activities[].[StatusCode,StatusMessage,Description]" --output text 2>&1 | cut -c1-700 | hide
  echo "== group size"
  aws autoscaling describe-auto-scaling-groups --region $R --auto-scaling-group-names "$ASG" --query "AutoScalingGroups[].[MinSize,DesiredCapacity,MaxSize,length(Instances)]" --output text | hide
  echo "== account plan hints"
  aws ec2 describe-instance-type-offerings --region $R --location-type availability-zone --filters Name=instance-type,Values=m6g.xlarge,t4g.large,t4g.xlarge --query "InstanceTypeOfferings[?Location=='us-east-1a'].InstanceType" --output text
} > "$OUT" 2>&1
echo "done: results are in $OUT"
