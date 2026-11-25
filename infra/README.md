# AWS Deployment with Terraform
Deploys Serka to a single EC2 instance in [AWS](https://aws.amazon.com/) with [Terraform](https://developer.hashicorp.com/terraform). The instance runs every container from `compose.yaml` with Docker and has an IAM role that lets it call Bedrock.

## Requirements
- [Terraform](https://developer.hashicorp.com/terraform/install)
- [AWS CLI](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html), logged in to the account (e.g. `aws configure sso`, then `export AWS_PROFILE=<PROFILE_NAME>`)
- Bedrock model access enabled in `eu-west-2` for the models in `.env.example`
- To prepare the data locally: [Docker](https://docs.docker.com/engine/install/), [uv](https://docs.astral.sh/uv/) and a checkout of [NERC-CEH/legilo](https://github.com/NERC-CEH/legilo) on the `supporting-docs-md` branch

## Deployments
There are two deployments, chosen with the `deployment` variable:

| `deployment` | Instance | Redis data |
|---|---|---|
| `test` | `serka-test`, `t3.medium` (4 GB) | `infra/dump-100.rdb`: the 100-dataset bundle |
| `full` | `serka-full`, `r7i.large` (16 GB) | `infra/dump-full.rdb`: the full bundle (about 4.2 GB in Redis) |

## Prepare the Redis data
Each instance starts from a Redis snapshot (`dump.rdb`) made locally, so it does not have to download, convert or embed anything. Build both snapshots on your machine before deploying. The [Ingest Data](../README.md#ingest-data) section of the main README has the details of each stage.

### 1. Set up
From the repository root, with AWS credentials for Bedrock (`aws sso login`):
```
cp .env.example .env    # set LEGILO_SRC to your legilo checkout (supporting-docs-md branch)
uv sync
docker compose up -d redis
docker compose --profile ingest up -d legilo
```
Loading needs only Redis, which the `redis` service publishes on `localhost:6379`. Legilo converts supporting documents during the build.

### 2. Download and build the bundles
```
uv run scripts/download.py all
uv run scripts/build-bundle.py 100
uv run scripts/build-bundle.py all
```
This writes `bundles/100` and `bundles/full`. The 100 datasets are the first 100 of the full collection. Downloading and converting everything takes hours the first time; both steps skip work already done, so they can be resumed. Skip this step if both bundles already exist.

### 3. Load each bundle and save its snapshot
The local Redis holds one bundle at a time, and each load replaces the previous one, so load and copy them in turn:
```
uv run scripts/load-bundle.py bundles/100
docker compose exec redis redis-cli SAVE
docker compose cp redis:/data/dump.rdb infra/dump-100.rdb

uv run scripts/load-bundle.py bundles/full
docker compose exec redis redis-cli SAVE
docker compose cp redis:/data/dump.rdb infra/dump-full.rdb
```
Embeddings are cached in `.cache/embeddings`, so only chunks never embedded before call Bedrock: the first full load takes several hours, later ones minutes. Each load clears the answer cache, so the snapshots carry no cached answers. The `.rdb` files are ignored by git.

To check a snapshot before deploying, start the whole stack (`docker compose up -d`) and search at `http://localhost:8080`. It serves whichever bundle was loaded last.

## Configure
Create `infra/terraform.tfvars`:
```
connect_ip = "<CIDR allowed to reach the UI, e.g. 203.0.113.4/32>"
vpc_id     = "<VPC_ID>"
subnet_id  = "<SUBNET_ID>"
# Optional
# git_ref                = "main"
# ssm_security_group_ids = ["<SG_ID>"]
```
If the VPC reaches Session Manager through VPC endpoints whose security group only allows listed groups, set `ssm_security_group_ids` to one of those groups so the instance can register with SSM. Find them with:
```
aws ec2 describe-vpc-endpoints --filters Name=vpc-id,Values=<VPC_ID> Name=service-name,Values=com.amazonaws.eu-west-2.ssm --query 'VpcEndpoints[].Groups[].GroupId'
aws ec2 describe-security-groups --group-ids <ENDPOINT_SG_ID> --query 'SecurityGroups[].IpPermissions[].UserIdGroupPairs[].GroupId'
```

## Deploy
From `infra/`, each deployment in its own workspace so they can run side by side:
```
terraform init
terraform workspace new test     # or: terraform workspace select test
terraform apply -var deployment=test
```
For the full deployment use `full` in both places. Run `terraform workspace show` to check which one you are working on.

`apply` uploads the dump to a new S3 bucket, then creates the instance. On first boot `scripts/setup.sh` installs Docker, downloads the dump into Redis's data directory, clones the repository at `git_ref` and runs `docker compose up -d --build`; this takes several minutes. Redis then rebuilds its search indexes from the loaded data, so search may be incomplete for a few more minutes (longer for `full`). The setup log is `/var/log/serka-setup.log` on the instance. The UI is then at the `instance_url` output (port 8080).

`setup.sh` only runs on first boot. Changing it or `git_ref` replaces the instance on the next `apply`, but a new dump only re-uploads it; to load it, replace the instance too:
```
terraform apply -var deployment=test -replace=aws_instance.app_server
```

## Connect
Open a shell with [Session Manager](https://docs.aws.amazon.com/systems-manager/latest/userguide/install-plugin-debian-and-ubuntu.html). The instance registers with SSM a few minutes after boot; if it never appears in `aws ssm describe-instance-information`, check `ssm_security_group_ids`:
```
aws ssm start-session --target <instance_id>
```
If the subnet has no public IP, forward the UI port instead and open `http://localhost:8080`:
```
aws ssm start-session --target <instance_id> \
  --document-name AWS-StartPortForwardingSession \
  --parameters '{"portNumber":["8080"],"localPortNumber":["8080"]}'
```

## Teardown
In the deployment's workspace:
```
terraform destroy -var deployment=test
```
