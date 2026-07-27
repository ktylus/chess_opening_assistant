output "ecr_repository_url" {
  description = "Image name to push to, without a tag."
  value       = aws_ecr_repository.app.repository_url
}

output "github_actions_role_arn" {
  description = "Set this as the AWS_ROLE_ARN secret on the GitHub repository."
  value       = aws_iam_role.github_actions.arn
}
