output "security_group_id" {
  value = aws_security_group.k8s.id
}

output "nodes" {
  value = {
    for name, inst in aws_instance.node : name => {
      public_ip  = inst.public_ip
      private_ip = inst.private_ip
    }
  }
}

output "mlflow_bucket" {
  value = aws_s3_bucket.mlflow.bucket
}