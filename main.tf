###########################################
# IDC Lambda Configs
###########################################
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

resource "aws_iam_role" "iam_role" {
  name = "${var.lambda_function_name}_Role3"

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
  name   = "LambdaFunctionPolicy3"
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

  # Enable CloudWatch logging
  tracing_config {
    mode = "Active"
  }
}

# Create an HTTP API Gateway
resource "aws_apigatewayv2_api" "example" {
  name          = "IDC-API"
  protocol_type = "HTTP"
}

# Define an HTTP integration for the Lambda function
resource "aws_apigatewayv2_integration" "example" {
  api_id          = aws_apigatewayv2_api.example.id
  integration_type = "AWS_PROXY"
  integration_uri  = aws_lambda_function.function.invoke_arn
  integration_method = "POST"
  connection_type  = "INTERNET"
  timeout_milliseconds = 29000
}

resource "aws_apigatewayv2_route" "custom_route" {
  api_id    = aws_apigatewayv2_api.example.id
  route_key = "GET /newendpoint"  # You can specify the HTTP method you want to use (e.g., GET, POST, ANY)
  target    = "integrations/${aws_apigatewayv2_integration.example.id}"

}

output "api_gateway_url" {
  description = "URL of the created API Gateway endpoint"
  value       = aws_apigatewayv2_api.example.api_endpoint
}
