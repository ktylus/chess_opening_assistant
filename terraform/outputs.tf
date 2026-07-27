output "ecr_repository_url" {
  description = "Image name to push to, without a tag."
  value       = aws_ecr_repository.app.repository_url
}

output "github_actions_role_arn" {
  description = "Set this as the AWS_ROLE_ARN secret on the GitHub repository."
  value       = aws_iam_role.github_actions.arn
}

output "service_url" {
  description = "The live site."
  value       = "https://${aws_apprunner_service.app.service_url}"
}

output "service_arn" {
  description = "Set this as the AWS_APPRUNNER_SERVICE_ARN secret on the GitHub repository."
  value       = aws_apprunner_service.app.arn
}

output "apprunner_access_role_arn" {
  description = "Set this as the AWS_APPRUNNER_ACCESS_ROLE_ARN secret on the GitHub repository."
  value       = aws_iam_role.apprunner_access.arn
}

output "service_id" {
  description = "Second path component of the CloudWatch log group names; see logs.tf."
  value       = aws_apprunner_service.app.service_id
}
