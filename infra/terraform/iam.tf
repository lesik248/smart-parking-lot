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

resource "aws_iam_role_policy" "status_dynamodb_read" {
  name = "parking-status-read"
  role = aws_iam_role.mlflow.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["dynamodb:Query"]
      Resource = "arn:aws:dynamodb:eu-north-1:${data.aws_caller_identity.current.account_id}:table/k8s-lab-occupancy-status"
    }]
  })
}

resource "aws_iam_role_policy" "grafana_cloudwatch_read" {
  name = "grafana-cloudwatch-read"
  role = aws_iam_role.mlflow.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "cloudwatch:ListMetrics",
        "cloudwatch:GetMetricData",
        "cloudwatch:GetMetricStatistics",
        "cloudwatch:DescribeAlarms",
        "cloudwatch:DescribeAlarmsForMetric",
        "ec2:DescribeInstances",
        "ec2:DescribeTags",
        "ec2:DescribeRegions",
        "tag:GetResources",
      ]
      Resource = "*"
    }]
  })
}