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

# Persistent infrastructure resources will be defined here

# --- ECR Repository ---
resource "aws_ecr_repository" "app_repo" {
  name                 = var.ecr_repository_name
  image_tag_mutability = "MUTABLE"
}

# --- Secrets Manager ---
resource "aws_secretsmanager_secret" "google_service_account_key" {
    name = "google-service-account-key-prod" # Or a dynamic name using variables      
    force_overwrite_replica_secret = true
    recovery_window_in_days        = 0
    description = "Google Service Account key for production"
}

resource "aws_secretsmanager_secret_version" "google_service_account_key_version" {
      secret_id     = aws_secretsmanager_secret.google_service_account_key.id
      secret_string = file("~/Documents/Next/Keys/sa-gemini-poc-0939-key.json")       
}

# --- Relational Postgres DB ---
resource "aws_db_subnet_group" "postgres_subnet_group" {
  name       = "postgres-subnet-group"
  subnet_ids = var.private_subnet_ids

  tags = {
    Name = "Postgres DB Subnet Group"
  }
}

resource "aws_db_instance" "postgres" {
  identifier             = "my-postgres-db"
  engine                = "postgres"
  engine_version        = "15"
  instance_class        = "db.t3.micro"
  allocated_storage     = 20
  max_allocated_storage = 100
  storage_type          = "gp2"
  publicly_accessible   = false

  db_name               = var.rds_db_name
  username              = var.rds_db_user
  password              = var.rds_db_password
  parameter_group_name  = "default.postgres15"

  vpc_security_group_ids = [aws_security_group.postgres_sg.id]
  db_subnet_group_name   = aws_db_subnet_group.postgres_subnet_group.name
  skip_final_snapshot   = true
}

resource "aws_security_group" "postgres_sg" {
  name        = "postgres-security-group"
  description = "Allow inbound PostgreSQL access"
  vpc_id      = var.vpc_id

  ingress {
    from_port   = 5432
    to_port     = 5432
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"] # Change this to restrict access
  }
}
