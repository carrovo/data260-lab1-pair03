#!/bin/sh
# Installs the EBS disk driver that EKS needs for PersistentVolumeClaims (MySQL, Mongo, Kafka, uploads).
# Idempotent. Hides the account id. Result: aws_ebs_csi_output.txt
#   sh scripts/aws_ebs_csi.sh
OUT=aws_ebs_csi_output.txt
R=us-east-1
C=p03-handshake
hide() { sed 's/[0-9]\{12\}/ACCOUNT/g'; }
{
  echo "== date"; date
  ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
  echo "== 1. OIDC identity provider for the cluster"
  eksctl utils associate-iam-oidc-provider --cluster $C --region $R --approve 2>&1 | hide
  echo "== 2. IAM role for the driver (AmazonEBSCSIDriverPolicy)"
  eksctl create iamserviceaccount --name ebs-csi-controller-sa --namespace kube-system --cluster $C --region $R \
    --role-name p03-ebs-csi-role --role-only --attach-policy-arn arn:aws:iam::aws:policy/service-role/AmazonEBSCSIDriverPolicy \
    --approve --override-existing-serviceaccounts 2>&1 | hide
  echo "== 3. the driver add-on"
  if aws eks describe-addon --cluster-name $C --addon-name aws-ebs-csi-driver --region $R >/dev/null 2>&1; then
    eksctl update addon --name aws-ebs-csi-driver --cluster $C --region $R --service-account-role-arn arn:aws:iam::$ACCOUNT:role/p03-ebs-csi-role --force 2>&1 | hide
  else
    eksctl create addon --name aws-ebs-csi-driver --cluster $C --region $R --service-account-role-arn arn:aws:iam::$ACCOUNT:role/p03-ebs-csi-role --force 2>&1 | hide
  fi
  echo "== 4. wait for the driver pods"
  sleep 20
  kubectl -n kube-system get pods | grep ebs-csi
  echo "== 5. volumes (should turn Bound within a minute or two)"
  sleep 60
  kubectl -n p03 get pvc
} > "$OUT" 2>&1
tail -12 "$OUT"
