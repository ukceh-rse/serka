# AWS Deployment with Terraform
This folder contains configuration files needed to deploy the Serka application to [AWS](https://aws.amazon.com/) using [Terraform](https://developer.hashicorp.com/terraform).

## Setup
To deploy you will need to install:
- [Terraform](https://developer.hashicorp.com/terraform/install)
- [AWS CLI](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html)

You will also need an AWS account set up with appropriate permissions for [Bedrock](https://aws.amazon.com/bedrock/) and [EC2](https://aws.amazon.com/ec2/) (check infromation on [IAM](https://docs.aws.amazon.com/IAM/latest/UserGuide/introduction.html) roles to set up).

## Configure
Once you have got everything above installed and setup you need to initialize terraform which will install the appropriate providers based on `main.tf`. Run the following command from the `terraform/` directory:
```
terraform init
```
Next you will need to create a new file to hold values for a few variables. Create a file called `terraform/terraform.tfvars` and populate it with the following:
```
ssh_key_name = <SSH_KEY_NAME>
connect_ip = <YOUR_IP_ADDRESS>
instance_type = <INSTANCE_TYPE>
```
These variables are defined in the `terraform/variables.tf`. `<SSH_KEY_NAME>` is the name of an SSH key that you have already created in your AWS account so that you can SSH into the EC2 instance once it is created. `<YOUR_IP_ADDRESS>` is to secure the EC2 instance so that only you can connect. `<INSTANCE_TYPE>` is the type of EC2 instance to deploy (recommended option are `t3.micro` or `t3.small`).
## Deploy
Once you have configured everything you can deploy with the command:
```
terraform apply
```
This will create a deployment plan and will ask you to confirm deployment by typing `yes`.
The initial deployment of the resources defined in the terraform setup should be fairly quick (less the 30 seconds) and should provide you with the IP address of the deployed EC2 instance e.g.
```
instance_url = "http://<EC2_IP>"
```
Deployment of the Serka application on the EC2 instance may take several minutes (makes use of `terraforms/scripts/setup.sh`) so connecting to the application may not be possible immediately.
> **Note**: The basic deployment will only import a small sample set of data from the EIDC for testing (10 datasets).

To tear down the deployment simply use:
```
tf destroy
```
