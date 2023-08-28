provider "aws" {
  region = "eu-central-1"
}

variable "lambda_function_name" {
  description = "Name of the Lambda function"
  default     = "newFunctionTerraform"
}

variable "python_code_path" {
  description = "Path to the Python code directory"
  default     = "python/"
}

data "archive_file" "zip_the_python_code" {
  type        = "zip"
  source_dir  = var.python_code_path
  output_path = "${path.module}/lambda_function_code.zip"
}

resource "aws_iam_role" "iam_role" {
  name = "${var.lambda_function_name}_Role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Action = "sts:AssumeRole",
        Principal = {
          Service = "lambda.amazonaws.com"
        },
        Effect = "Allow",
        Sid    = ""
      }
    ]
  })
}

resource "aws_iam_policy" "iam_policy" {
  name   = "LambdaFunctionPolicy"
  path   = "/"
  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Action   = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"],
        Resource = "arn:aws:logs:*:*:*",
        Effect   = "Allow"
      }
    ]
  })
}

resource "aws_iam_policy_attachment" "attach_policy" {
  name       = "LambdaFunctionPolicyAttachment"
  roles      = [aws_iam_role.iam_role.name]
  policy_arn = aws_iam_policy.iam_policy.arn
}

resource "aws_lambda_function" "function" {
  filename      = data.archive_file.zip_the_python_code.output_path
  function_name = var.lambda_function_name
  role          = aws_iam_role.iam_role.arn
  handler       = "index.lambda_handler"
  runtime       = "python3.8"

  depends_on = [aws_iam_policy_attachment.attach_policy]
  layers = ["arn:aws:lambda:eu-central-1:017000801446:layer:AWSLambdaPowertoolsPythonV2:40"]
    environment {
    variables = {
      key1 = "value1",
      key2 = "value2"
    }
  }

}

output "lambda_function_arn" {
  description = "ARN of the created Lambda function"
  value       = aws_lambda_function.function.arn
}