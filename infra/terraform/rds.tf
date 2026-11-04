resource "aws_security_group" "rds" {
  name   = "${var.project}-rds-sg"
  vpc_id = data.aws_vpc.default.id

  ingress {
    description     = "PostgreSQL from cluster nodes"
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.k8s.id]
  }
}

resource "aws_db_instance" "predictions" {
  identifier     = "${var.project}-predictions"
  engine         = "postgres"
  engine_version = "17"
  instance_class = "db.t3.micro"

  allocated_storage = 20
  storage_type      = "gp2"

  db_name  = "parking"
  username = "parking_admin"
  password = var.db_password

  vpc_security_group_ids = [aws_security_group.rds.id]
  publicly_accessible    = false

  backup_retention_period = 1
  skip_final_snapshot     = true
  deletion_protection     = false
}

output "rds_endpoint" {
  value = aws_db_instance.predictions.address
}