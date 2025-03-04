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

variable "ecr_repository_name" {
  type        = string
  description = "Name for the ECR repository"
  default     = "fastapi-app-repo"
}

# --- RDS DB Configuration ---
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