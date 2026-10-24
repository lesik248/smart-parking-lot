locals {
  nodes = {
    "master"     = { role = "master", type = "t3.small" }
    "worker-app" = { role = "app",    type = "c7i-flex.large" }
    "worker-db"  = { role = "db",     type = "t3.small" }
  }
}

data "aws_ami" "ubuntu" {
  most_recent = true
  owners      = ["099720109477"] # аккаунт Canonical

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd-gp3/ubuntu-noble-24.04-amd64-server-*"]
  }
}

resource "aws_instance" "node" {
  for_each = local.nodes

  ami                    = data.aws_ami.ubuntu.id
  instance_type          = each.value.type
  key_name               = aws_key_pair.k8s.key_name
  vpc_security_group_ids = [aws_security_group.k8s.id]

  iam_instance_profile = each.value.role == "app" ? aws_iam_instance_profile.mlflow.name : null

  root_block_device {
    volume_size = 20
    volume_type = "gp3"
  }

  metadata_options {
    http_tokens                 = "required"
    http_put_response_hop_limit = 2
  }

  tags = {
    Name = "${var.project}-${each.key}"
    Role = each.value.role
  }
}