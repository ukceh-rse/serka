provider "aws" {
  region = "eu-west-2"
}

data "aws_ami" "ubuntu" {
  most_recent = true

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd-gp3/ubuntu-noble-24.04-amd64-server-*"]
  }

  owners = ["099720109477"] # Canonical
}

resource "aws_iam_role" "ec2_role" {
  name = "${var.instance_name}-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ec2.amazonaws.com"
        }
      },
    ]
  })

  tags = {
    Name = "${var.instance_name}-role"
  }
}

resource "aws_iam_role_policy_attachment" "ssm_managed" {
  role       = aws_iam_role.ec2_role.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

resource "aws_iam_role_policy" "bedrock_access" {
  name = "${var.instance_name}-bedrock-access"
  role = aws_iam_role.ec2_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = [
          "bedrock:InvokeModel",
          "bedrock:InvokeModelWithResponseStream",
          "bedrock:GetFoundationModel",
          "bedrock:ListFoundationModels"
        ]
        Effect   = "Allow"
        Resource = "*"
      },
    ]
  })
}

resource "aws_iam_instance_profile" "ec2_profile" {
  name = "${var.instance_name}-profile"
  role = aws_iam_role.ec2_role.name
}

resource "aws_instance" "app_server" {
  ami           = data.aws_ami.ubuntu.id
  instance_type = var.instance_type
  subnet_id = var.subnet_id
  vpc_security_group_ids = [aws_security_group.ssm_access.id]
  iam_instance_profile = aws_iam_instance_profile.ec2_profile.name

  associate_public_ip_address = true

  user_data = templatefile("${path.module}/scripts/setup.sh", {})

  tags = {
    Name = var.instance_name
  }
}

resource "aws_security_group" "ssm_access" {
  name        = "${var.instance_name}-ssm-access"
  description = "Allow HTTP/HTTPS inbound; SSM managed, no SSH"
  vpc_id      = var.vpc_id   # Existing VPC

  ingress {
    description = "HTTP from specified CIDR blocks"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = [var.connect_ip]
  }

  ingress {
    description = "HTTPS from specified CIDR blocks"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = [var.connect_ip]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${var.instance_name}-ssm-access"
  }
}
