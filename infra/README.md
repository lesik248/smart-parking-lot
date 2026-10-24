# Infrastructure

Deploys smart-parking-lot to a 3-node Kubernetes cluster on AWS (`eu-north-1`) using **Terraform**, **Ansible** and **kubeadm**.

## Architecture

| Node | EC2 type | Runs |
|---|---|---|
| `master` | t3.small | Kubernetes control plane |
| `worker-app` | c7i-flex.large | `parking-api` (2 replicas), `mlflow` |
| `worker-db` | t3.small | `postgres` (persistent volume) |

- **parking-api** is exposed via NodePort `30080`.
- **MLflow** stores metadata in PostgreSQL and model artifacts in S3. It reaches S3 through an IAM role attached to `worker-app`, so no AWS keys are stored in the cluster. It is not exposed publicly; use `kubectl port-forward`.
- Workloads are pinned to nodes with node labels (`role=app` / `role=db`) and `nodeSelector`.
- SSH, the Kubernetes API and NodePorts are reachable only from the IP set in `terraform.tfvars`.

```
infra/
├── terraform/   # EC2 instances, security group, SSH key, S3 bucket, IAM role
├── ansible/     # node setup, kubeadm init/join, node labels, storage
└── k8s/         # Kubernetes manifests
```

## Prerequisites

```bash
brew tap hashicorp/tap
brew install hashicorp/tap/terraform ansible awscli kubectl
aws configure                                   # region: eu-north-1
ssh-keygen -t ed25519 -f ~/.ssh/k8s-lab -N ""
```

Set your public IP:

```bash
cd infra/terraform
cp terraform.tfvars.example terraform.tfvars
curl -s https://checkip.amazonaws.com           # put it in terraform.tfvars as "x.x.x.x/32"
```

If you use a different AWS account, update `MLFLOW_BUCKET` in `k8s/20-mlflow.yaml` with the value of `terraform output mlflow_bucket`.

## Deploy

All commands are run from `infra/`.

```bash
# 1. Infrastructure
cd terraform
terraform init
terraform apply

# 2. Cluster (wait ~1 min for instances to boot)
cd ../ansible
ansible-playbook playbook.yml
export KUBECONFIG=$PWD/kubeconfig
kubectl get nodes -L role

# 3. Applications
cd ..
kubectl apply -f k8s/00-namespace.yaml
kubectl create secret generic postgres-credentials -n parking \
  --from-literal=POSTGRES_USER=mlflow \
  --from-literal=POSTGRES_DB=mlflow \
  --from-literal=POSTGRES_PASSWORD="$(openssl rand -base64 18 | tr -d '/+=')"
kubectl apply -f k8s/
kubectl get pods -n parking -o wide
```

Access:

- **API:** `http://<public_ip of any node>:30080/docs` (IPs: `terraform output nodes`)
- **MLflow:** `kubectl port-forward -n parking svc/mlflow 5001:5000`, then open `http://localhost:5001`

To pick up a new image after CI pushes `latest`:

```bash
kubectl rollout restart deployment/parking-api -n parking
```

## Stop

Stops the instances. The cluster and its data are kept; only storage is billed.

```bash
aws ec2 stop-instances --instance-ids $(aws ec2 describe-instances \
  --filters "Name=tag:Project,Values=k8s-lab" "Name=instance-state-name,Values=running" \
  --query "Reservations[].Instances[].InstanceId" --output text)
```

## Start again

```bash
# 1. If your public IP changed, update terraform/terraform.tfvars

# 2. Start the instances
aws ec2 start-instances --instance-ids $(aws ec2 describe-instances \
  --filters "Name=tag:Project,Values=k8s-lab" "Name=instance-state-name,Values=stopped" \
  --query "Reservations[].Instances[].InstanceId" --output text)

# 3. Public IPs change after a restart: refresh the inventory and kubeconfig
cd terraform && terraform apply
cd ../ansible && ansible-playbook playbook.yml
export KUBECONFIG=$PWD/kubeconfig

# 4. Pods come back on their own within a few minutes
kubectl get pods -n parking -o wide
```

## Destroy

Removes all AWS resources, including the S3 bucket with model artifacts.

```bash
cd terraform
terraform destroy
rm -f ../ansible/kubeconfig
```

## Not committed to git

`terraform.tfstate*`, `terraform.tfvars`, `.terraform/`, `ansible/inventory.ini`, `ansible/kubeconfig`.