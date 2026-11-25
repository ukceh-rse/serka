provider "aws" {
  region = "eu-west-2"
}

locals {
  name = "serka-${var.deployment}"

  # test: a small instance with the 100-dataset bundle; full: the whole catalogue, which needs
  # about 4.2 GB in Redis, so 16 GB of memory
  settings = {
    test = { instance_type = "t3.medium", redis_dump = "dump-100.rdb" }
    full = { instance_type = "r7i.large", redis_dump = "dump-full.rdb" }
  }[var.deployment]
  redis_dump_path = "${path.module}/${local.settings.redis_dump}"
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
  name = "${local.name}-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "ec2.amazonaws.com" }
    }]
  })
}

# Shell access through Session Manager, no SSH key needed
resource "aws_iam_role_policy_attachment" "ssm_managed" {
  role       = aws_iam_role.ec2_role.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

resource "aws_iam_role_policy" "bedrock_access" {
  name = "${local.name}-bedrock-access"
  role = aws_iam_role.ec2_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = [
        "bedrock:InvokeModel",
        "bedrock:InvokeModelWithResponseStream",
      ]
      Effect   = "Allow"
      Resource = "*"
    }]
  })
}

# Redis snapshot (dump.rdb) the instance loads on first boot, so it starts with the full index
resource "aws_s3_bucket" "data" {
  bucket_prefix = "${local.name}-data-"
  force_destroy = true
}

resource "aws_s3_object" "redis_dump" {
  bucket      = aws_s3_bucket.data.id
  key         = "dump.rdb"
  source      = local.redis_dump_path
  source_hash = filemd5(local.redis_dump_path)
}

resource "aws_iam_role_policy" "redis_dump_read" {
  name = "${local.name}-redis-dump-read"
  role = aws_iam_role.ec2_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action   = ["s3:GetObject"]
      Effect   = "Allow"
      Resource = "${aws_s3_bucket.data.arn}/${aws_s3_object.redis_dump.key}"
    }]
  })
}

resource "aws_iam_instance_profile" "ec2_profile" {
  name = "${local.name}-profile"
  role = aws_iam_role.ec2_role.name
}

resource "aws_security_group" "app" {
  name   = "${local.name}-app"
  vpc_id = var.vpc_id

  ingress {
    description = "Serka UI"
    from_port   = 8080
    to_port     = 8080
    protocol    = "tcp"
    cidr_blocks = [var.connect_ip]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_instance" "app_server" {
  ami                    = data.aws_ami.ubuntu.id
  instance_type          = local.settings.instance_type
  subnet_id              = var.subnet_id
  vpc_security_group_ids = concat([aws_security_group.app.id], var.ssm_security_group_ids)
  iam_instance_profile   = aws_iam_instance_profile.ec2_profile.name

  root_block_device {
    volume_size = 50
    volume_type = "gp3"
  }

  # Containers reach the instance role through IMDSv2, which needs a second network hop
  metadata_options {
    http_tokens                 = "required"
    http_put_response_hop_limit = 2
  }

  user_data = templatefile("${path.module}/scripts/setup.sh", {
    git_ref    = var.git_ref
    redis_dump = "s3://${aws_s3_bucket.data.id}/${aws_s3_object.redis_dump.key}"
  })
  user_data_replace_on_change = true

  # setup.sh downloads the dump on first boot, so it must be uploaded first
  depends_on = [aws_s3_object.redis_dump]

  tags = {
    Name = local.name
  }
}
