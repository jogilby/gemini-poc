terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 4.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

# --- ECR Repository ---
resource "aws_ecr_repository" "app_repo" {
  name                 = var.ecr_repository_name
  image_tag_mutability = "MUTABLE"
}

# --- IAM Roles and Policies ---
resource "aws_iam_role" "ecs_task_execution_role" {
  name = "ecs-task-execution-role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Principal = {
          Service = "ecs-tasks.amazonaws.com"
        }
        Effect = "Allow"
      },
    ]
  })
}

resource "aws_iam_policy" "ecs_task_execution_policy" {
  name        = "ecs-task-execution-policy"
  description = "Policy for ECS task execution role"
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = [
          "ecr:GetAuthorizationToken",
          "ecr:BatchCheckLayerAvailability",
          "ecr:GetDownloadUrlForLayer",
          "ecr:BatchGetImage",
          "logs:CreateLogStream",
          "logs:PutLogEvents",
          "elasticloadbalancing:RegisterTargets", 
          "elasticloadbalancing:DeregisterTargets", 
          "elasticloadbalancing:DescribeTargetGroups", 
          "elasticloadbalancing:DescribeTargetHealth",
          "s3:GetObject",
          "s3:PutObject",
          "s3:ListBucket"
        ],
        Effect   = "Allow",
        Resource = "*"
      },
      {
        Action = [
          "secretsmanager:GetSecretValue"  # Added for Secrets Manager access
        ],
        Effect   = "Allow",
        Resource = "*" # Grant access to your specific secret
      },
    ]
  })
}

resource "aws_iam_role_policy_attachment" "ecs_task_execution_policy_attachment" {
  role       = aws_iam_role.ecs_task_execution_role.name
  policy_arn = aws_iam_policy.ecs_task_execution_policy.arn
}

# --- CloudWatch ----
# Create CloudWatch Log Group
resource "aws_cloudwatch_log_group" "ecs_logs" {
  name              = var.cloudwatch_log_group_name 
  retention_in_days = 30  # Adjust retention period as needed
}

# --- Secrets Manager ---
#resource "aws_secretsmanager_secret" "google_service_account_key" {
#    name = "google-service-account-key-prod" # Or a dynamic name using variables      
#    force_overwrite_replica_secret = true
#    recovery_window_in_days        = 0
#    description = "Google Service Account key for production"
#}

#resource "aws_secretsmanager_secret_version" "google_service_account_key_version" {
#      secret_id     = aws_secretsmanager_secret.google_service_account_key.id
#      secret_string = file("~/Documents/Next/Keys/sa-gemini-poc-0939-key.json")       
#}

# --- Security Groups ---
resource "aws_security_group" "alb_sg" {
  name        = "alb-sg"
  description = "Security group for Application Load Balancer"
  vpc_id      = var.vpc_id

  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_security_group" "ecs_tasks_sg" {
  name        = "ecs-tasks-sg"
  description = "Security group for ECS tasks"
  vpc_id      = var.vpc_id

  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    security_groups = [aws_security_group.alb_sg.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

# --- ALB Module (moved to this file for simplicity, can be kept as a separate module if preferred) ---
resource "aws_alb" "application_load_balancer" {
  name               = var.alb_name
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb_sg.id]
  subnets            = var.public_subnet_ids

  enable_deletion_protection = false
}

resource "aws_alb_listener" "http_listener" {
  load_balancer_arn = aws_alb.application_load_balancer.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_alb_target_group.app_target_group.arn
  }
}

resource "aws_alb_target_group" "app_target_group" {
  name                 = var.alb_target_group_name
  port                 = 80
  protocol             = "HTTP"
  vpc_id               = var.vpc_id
  target_type          = "ip"

  health_check {
    path                 = "/"
    protocol             = "HTTP"
    matcher              = "200"
    healthy_threshold    = 2
    unhealthy_threshold  = 5
    interval             = 30
    timeout              = 5
  }
}
# --- End ALB Module ---


# --- ECS Module (moved to this file for simplicity, can be kept as a separate module if preferred) ---
resource "aws_ecs_cluster" "app_cluster" {
  name = var.ecs_cluster_name
}

resource "aws_ecs_task_definition" "app_task_definition" {
  family             = var.ecs_task_family
  requires_compatibilities = ["FARGATE"]
  network_mode       = "awsvpc"
  cpu                = var.fargate_cpu
  memory             = var.fargate_memory
  execution_role_arn = aws_iam_role.ecs_task_execution_role.arn
  task_role_arn      = "" # Removed task role for simplicity, add back if needed

  container_definitions = jsonencode([
    {
      name      = "app-container",
      image     = "${aws_ecr_repository.app_repo.repository_url}:latest",
      portMappings = [
        {
          containerPort = 80
          hostPort      = 80
        }
      ],
      environment = [
        { name = "AWS_ACCESS_KEY_ID", value = var.aws_access_key_id },
        { name = "AWS_SECRET_ACCESS_KEY", value = var.aws_secret_access_key },
        { name = "AWS_REGION_NAME", value = var.aws_region },
        { name = "S3_BUCKET_NAME", value = var.s3_bucket_name },
        { name = "GEMINI_API_KEY", value = var.gemini_api_key },
        { name = "GOOGLE_CLOUD_PROJECT_ID", value = var.google_cloud_project_id },
        { name = "GOOGLE_DOCUMENT_AI_PROCESSOR_ID", value = var.google_document_ai_processor_id },
        { name = "GOOGLE_DOCUMENT_AI_PROCESSOR_LOCATION", value = var.google_document_ai_processor_location },
        { name = "GOOGLE_SERVICE_ACCOUNT_SECRET_NAME", value = var.google_service_account_secret_name }
      ],
      logConfiguration = { 
        logDriver = "awslogs"
        options = {
          awslogs-group         = var.cloudwatch_log_group_name # Use variable for log group name
          awslogs-region        = var.aws_region
          awslogs-stream-prefix = "ecs" # Prefix for log streams
        }
      }
    }
  ])
}

resource "aws_ecs_service" "app_service" {
  name            = var.service_name
  cluster         = aws_ecs_cluster.app_cluster.id
  task_definition = aws_ecs_task_definition.app_task_definition.arn
  desired_count   = var.desired_task_count
  launch_type     = "FARGATE"
  network_configuration {
    assign_public_ip = true
    subnets          = var.private_subnet_ids
    security_groups = [aws_security_group.ecs_tasks_sg.id]
  }
  load_balancer {
    target_group_arn = aws_alb_target_group.app_target_group.arn
    container_name   = "app-container"
    container_port   = 80
  }
  depends_on = [aws_alb_target_group.app_target_group]
}
# --- End ECS Module ---
