# AWS deployment (Pair 03, Lab 2 part 1.4 to 1.6)

One combined deployment of the whole platform (student, company, job, application, event and
assistant services, four Kafka workers, Kafka, MongoDB, MySQL, frontend gateway) on Amazon EKS,
with the images in Amazon ECR. Region `us-east-1`, cluster `p03-handshake`, namespace `p03`.
No account id, key or password is committed: scripts read the account from the AWS CLI session,
hide it in their output, and create the Kubernetes Secret from the git-ignored `.env.compose`.

| Piece | What |
|---|---|
| ECR | 8 repositories `p03-<service>` (application-service, assistant-service, company-service, event-service, frontend, job-service, student-service, worker), tag `lab2`, built for arm64 |
| EKS | `aws/eks-cluster.yaml`: Kubernetes 1.34, managed node group `p03-nodes`, 2 x m6g.xlarge (Graviton), one availability zone so the EBS volumes reach every node |
| Overlay | `aws/overlay/`: points the images at ECR, gives `p03-frontend` an AWS load balancer, gp3 StorageClass `p03-gp3`, keeps the Company and Application services on one node (they share the resume volume) |
| Public endpoint | the `p03-frontend` LoadBalancer, port 9036 (`kubectl -n p03 get svc p03-frontend`) |

## Commands (in order)

    sh scripts/aws_preflight.sh                 # read-only checks of the account
    sh scripts/aws_ecr_push.sh                  # build, create repositories, push tag lab2
    eksctl create cluster -f aws/eks-cluster.yaml
    sh scripts/aws_ebs_csi.sh                   # EBS disk driver (needed for the database volumes)
    sh scripts/aws_deploy.sh                    # secret, manifests, seed data, public address
    sh scripts/aws_verify.sh                    # end-to-end request, kubectl output, Kafka flow

Pause to save credit (nodes stop; cluster, volumes, images and manifests stay) and resume:

    sh scripts/aws_pause.sh down
    sh scripts/aws_pause.sh up

## Verified (2026-11-13)

All 16 pods Running; seed (SEED=3) loaded 300 jobs, 100 events, 1,500 applications, 600 registrations.
Through the public address: gateway health 200, student sign-in 200, job search 200, and
`scripts/check_kafka_flow.sh` PASS (p03.application.created, p03.application.updated and
p03.event.registration_created each +1, unprefixed topics unchanged, event and application workers
processed their events).

## Problems met and fixed

| Problem | Cause | Fix |
|---|---|---|
| Node group stayed in CREATING for 25 minutes, no instance started | The account was on the AWS Free plan, which rejects every instance type that is not free-tier eligible ("The specified instance type is not eligible for Free Tier", in the Auto Scaling activity log) | Upgraded the account plan, recreated the node group |
| First `kubectl apply -k` failed | A Kustomize overlay cannot live inside the directory it builds on (cycle) | Overlay moved to `aws/overlay/` |
| MySQL, Mongo, Kafka and uploads volumes stayed Pending | The EBS CSI driver add-on and the cluster's OIDC provider were never created because the first cluster run stopped at the node group | `scripts/aws_ebs_csi.sh` creates the OIDC provider, an IAM role and the add-on |
| Some image pushes failed with connection errors | Large layers over a home connection, while the cluster was also being created | Push script retries each image up to 4 times |

## Cost notes

Running: about $0.45 per hour (two m6g.xlarge nodes, EKS control plane, load balancer, NAT gateway, EBS).
Paused (nodes at 0): about $4 per day. A budget alert is set in AWS Billing. Never delete the cluster before the demo.
