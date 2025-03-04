variable "aws_region" {
  type        = string
  description = "AWS Region to deploy to"
  default     = "us-east-1"
}

variable "vpc_id" {
  type        = string
  description = "VPC ID to deploy resources into"
}

variable "public_subnet_ids" {
  type        = list(string)
  description = "List of public subnet IDs for ALB"
}

variable "private_subnet_ids" {
  type        = list(string)
  description = "List of private subnet IDs for ECS tasks"
}

variable "ecs_cluster_name" {
  type        = string
  description = "Name for the ECS cluster"
  default     = "fastapi-app-cluster"
}

variable "ecs_task_family" {
  type        = string
  description = "Family name for the ECS task definition"
  default     = "fastapi-app-task"
}

variable "ecr_application_image_url" {
  type = string
  description = "ECR repository URL for application image"
}

variable "alb_name" {
  type        = string
  description = "Name for the Application Load Balancer"
  default     = "fastapi-app-alb"
}

variable "alb_target_group_name" {
  type        = string
  description = "Name for the ALB Target Group"
  default     = "fastapi-app-tg"
}

# Environment Variables
variable "aws_access_key_id" {
  type = string
  description = "AWS Access Key ID"
  sensitive = true
}

variable "aws_secret_access_key" {
  type = string
  description = "AWS Secret Access Key"
  sensitive = true
}

variable "s3_bucket_name" {
  type = string
  description = "S3 Bucket Name"
}

variable "gemini_api_key" {
  type = string
  description = "Gemini API Key"
  sensitive = true
}

variable "google_cloud_project_id" {
  type = string
  description = "Google Cloud Project ID"
}

variable "google_document_ai_processor_id" {
  type = string
  description = "Google Document AI Processor ID"
}

variable "google_document_ai_processor_location" {
  type = string
  description = "Google Document AI Processor Location"
}

variable "google_service_account_secret_name" {
  type = string
  description = "Google Service Account AWS Secret Name"
}

variable "service_name" {
  type        = string
  description = "Name for the ECS Service"
  default     = "fastapi-app-service"
}

variable "desired_task_count" {
  type        = number
  description = "Desired number of ECS tasks"
  default     = 1
}

variable "fargate_cpu" {
  type        = number
  description = "CPU units for Fargate task"
  default     = 1024 # 1 - 0.25 vCPU
}

variable "fargate_memory" {
  type        = number
  description = "Memory in MB for Fargate task"
  default     = 4096 # 4 - 0.5 GB
}

variable "cloudwatch_log_group_name" {
  type        = string
  description = "Name of the CloudWatch Log Group for ECS Task logs"
  default     = "gemini-poc-app" # Default log group name
} 

# --- RDS DB Environment Variables ---
variable "rds_db_host" {
  type        = string
  description = "RDS db host (from rds_endpoint output)"  
}

variable "rds_db_name" {
  type        = string
  description = "RDS database name"  
}

variable "rds_db_user" {
  type        = string
  description = "RDS admin user name"
  default     = "admin"
}

variable "rds_db_password" {
  type        = string
  description = "RDS admin user password"  
}

variable "rds_db_port" {
  type        = string
  description = "RDS db port (from rds_endpoint output)"  
}