# узнаём ID своего аккаунта
data "aws_caller_identity" "current" {}

resource "aws_s3_bucket" "mlflow" {
  bucket        = "${var.project}-mlflow-${data.aws_caller_identity.current.account_id}"
  force_destroy = true
}