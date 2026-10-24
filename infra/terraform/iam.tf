resource "aws_iam_role" "mlflow" {
  name = "${var.project}-mlflow-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ec2.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy" "mlflow_s3" {
  name = "mlflow-s3-access"
  role = aws_iam_role.mlflow.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["s3:ListBucket"]
        Resource = aws_s3_bucket.mlflow.arn
      },
      {
        Effect   = "Allow"
        Action   = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"]
        Resource = "${aws_s3_bucket.mlflow.arn}/*"
      }
    ]
  })
}

resource "aws_iam_instance_profile" "mlflow" {
  name = "${var.project}-mlflow-profile"
  role = aws_iam_role.mlflow.name
}