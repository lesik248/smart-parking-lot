# находим уже существующую default VPC
data "aws_vpc" "default" {
  default = true
}

resource "aws_security_group" "k8s" {
  name        = "${var.project}-sg"
  description = "Kubernetes lab cluster"
  vpc_id      = data.aws_vpc.default.id

  ingress {
    description = "SSH"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = [var.my_ip]
  }

  ingress {
    description = "Kubernetes API"
    from_port   = 6443
    to_port     = 6443
    protocol    = "tcp"
    cidr_blocks = [var.my_ip]
  }

  # сервисы кластера (API парковок, MLflow) — только с вашего IP
  ingress {
    description = "NodePort services"
    from_port   = 30000
    to_port     = 32767
    protocol    = "tcp"
    cidr_blocks = [var.my_ip]
  }

  # ноды кластера могут свободно общаться между собой
  ingress {
    description = "Node-to-node"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    self        = true
  }

  # выход в интернет (скачивать пакеты, образы из GHCR) — разрешён
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_key_pair" "k8s" {
  key_name   = "${var.project}-key"
  public_key = file(pathexpand(var.ssh_public_key_path))
}