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
| Overlay | `aws/overlay/`: points the images at ECR, gives `p03-frontend` an AWS load balancer, gp3 StorageClass `p03-gp3`, keeps the Company and Application services on one node (they share the resume volume), adds the in-cluster Ollama model server for the Assistant (`ollama.yaml`) and a 300 s load balancer idle timeout |
| Public endpoint | the `p03-frontend` LoadBalancer, port 9036 (`kubectl -n p03 get svc p03-frontend`) |

## Commands (in order)

    sh scripts/aws_preflight.sh                 # read-only checks of the account
    sh scripts/aws_ecr_push.sh                  # build, create repositories, push tag lab2
    eksctl create cluster -f aws/eks-cluster.yaml
    sh scripts/aws_ebs_csi.sh                   # EBS disk driver (needed for the database volumes)
    sh scripts/aws_deploy.sh                    # secret, manifests, seed data, public address
    sh scripts/aws_verify.sh                    # end-to-end request, kubectl output, Kafka flow
    sh scripts/aws_ollama.sh                    # Ollama (qwen3:8b) for the Assistant, applies the overlay

Pause to save credit (nodes stop; cluster, volumes, images and manifests stay) and resume:

    sh scripts/aws_pause.sh down
    sh scripts/aws_pause.sh up

After `up`, wait about 5 minutes for both nodes to be Ready (`kubectl get nodes`) and the pods to start
(`kubectl -n p03 get pods`); the load balancer address does not change. The workers need a few more
minutes before Kafka events flow normally (see Problems). After `down`, run `kubectl get nodes` until it
says "No resources found".

## Verified (2026-11-13)

All 16 pods Running; seed (SEED=3) loaded 300 jobs, 100 events, 1,500 applications, 600 registrations.
Through the public address: gateway health 200, student sign-in 200, job search 200, and
`scripts/check_kafka_flow.sh` PASS (p03.application.created, p03.application.updated and
p03.event.registration_created each +1, unprefixed topics unchanged, event and application workers
processed their events).

## Assistant on AWS (2026-11-14)

Ollama runs in the cluster (`p03-ollama`, image `ollama/ollama`, version 0.40.16 in the pod) with the
model `qwen3:8b` (5.2 GB) on its own 30 GB EBS volume, so a pause does not download it again. The
Assistant pod reaches it at `http://p03-ollama:11434` (set by the overlay). The nodes have no GPU.

Measured on the 2 x m6g.xlarge nodes (Ollama log): generation about 4.7 tokens per second; the first
model call of a question (choosing the `search_jobs` tool) took 1 min; the second call (writing the
answer) did not finish within the Assistant client's 240 s and failed with a 500 after 4 min. The model
selected the right tool and the Assistant reached Ollama, so the chain works; the first test question
did not return a final answer on this hardware. Mitigation agreed with the Assistant owner: an optional
`OLLAMA_NUM_PREDICT` cap in the Assistant client (unset by default, so local behaviour is unchanged),
set to 256 only in `aws/overlay/kustomization.yaml`.

Result with the cap (2026-11-14): the Assistant completes the whole flow on AWS (login, tool call
`search_jobs`, final answer; assistant log `run_complete exit="normal" tool_calls=1`, HTTP 200). The
second model call dropped from a 4-minute failure to about 1m50s. One question takes about 150 to 175
seconds in total (149 s warm, 175 s cold), so the gateway limit in `frontend/nginx.conf` was raised from
120 s to 280 s (below the 300 s load balancer idle timeout). After that the answer reached the browser
(`docs/screenshots/aws/aws_07_assistant_answer.png`, kept locally). This is CPU-only inference
(about 4.7 tokens per second on m6g.xlarge): it is correct but slow, and it is the first bottleneck on AWS.

Kafka flow check (`scripts/check_kafka_flow.sh`): PASS through the public address, including the exact
registration and application documents in MongoDB and their `processed_events` entries. One earlier run
right after a resume failed its wait: the application worker applied `application.updated` about 3
minutes after it was published (the final document was correct, nothing lost). A second run was clean.

## Problems met and fixed

| Problem | Cause | Fix |
|---|---|---|
| Node group stayed in CREATING for 25 minutes, no instance started | The account was on the AWS Free plan, which rejects every instance type that is not free-tier eligible ("The specified instance type is not eligible for Free Tier", in the Auto Scaling activity log) | Upgraded the account plan, recreated the node group |
| First `kubectl apply -k` failed | A Kustomize overlay cannot live inside the directory it builds on (cycle) | Overlay moved to `aws/overlay/` |
| MySQL, Mongo, Kafka and uploads volumes stayed Pending | The EBS CSI driver add-on and the cluster's OIDC provider were never created because the first cluster run stopped at the node group | `scripts/aws_ebs_csi.sh` creates the OIDC provider, an IAM role and the add-on |
| Assistant page showed "Unable to reach the assistant" | The Classic Load Balancer closes idle connections after 60 s, and a CPU answer takes longer | `service.beta.kubernetes.io/aws-load-balancer-connection-idle-timeout: "300"` on `p03-frontend` (in the overlay) |
| After scaling to 0 one node stayed `Ready,SchedulingDisabled` for over 10 minutes | The node drain never finished | With min and desired size at 0, the instance was terminated by hand (EC2 console or `aws ec2 terminate-instances`) and the Node object then disappeared; no replacement starts |
| After the cap the browser showed "Unable to complete the assistant request" although the Assistant log showed HTTP 200 | One answer takes about 150 to 175 s; nginx in the frontend gateway gave up at 120 s | `proxy_read_timeout` in `frontend/nginx.conf` raised to 280 s; the overlay sets `imagePullPolicy: Always` for the frontend and the Assistant, because the tag `lab2` is reused |
| Some image pushes failed with connection errors | Large layers over a home connection, while the cluster was also being created | Push script retries each image up to 4 times |

## Cost notes

Running: about $0.45 per hour (two m6g.xlarge nodes, EKS control plane, load balancer, NAT gateway, EBS).
Paused (nodes at 0): about $4 per day. A budget alert is set in AWS Billing. Never delete the cluster before the demo.
