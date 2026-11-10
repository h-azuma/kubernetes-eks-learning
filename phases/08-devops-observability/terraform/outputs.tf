output "cd_role_arn" {
  description = "GitHub の repository variable AWS_ROLE_ARN に設定する値。"
  value       = aws_iam_role.cd.arn
}

output "github_subject" {
  description = "ロールを引き受けられる OIDC トークンの sub。"
  value       = "repo:${var.github_repository}:environment:${var.github_environment}"
}
