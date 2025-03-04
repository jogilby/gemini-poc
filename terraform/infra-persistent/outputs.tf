# Persistent infrastructure outputs will be defined here

output "repository_url" {
  value = aws_ecr_repository.app_repo.repository_url
}

output "rds_endpoint" {
  value = aws_db_instance.postgres.endpoint
}