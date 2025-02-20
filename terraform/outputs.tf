output "application_url" {
  value       = "http://${aws_alb.application_load_balancer.dns_name}"
  description = "URL to access the FastAPI application"
}

output "alb_dns" {
  value = aws_alb.application_load_balancer.dns_name
}

output "repository_url" {
  value = aws_ecr_repository.app_repo.repository_url
}