output "region" {
  value = var.region
}

output "cluster_name" {
  value = var.cluster_name
}

output "vpc_id" {
  value = local.vpc_id
}

output "db_endpoint_address" {
  description = "API の POSTGRES_HOST に設定するホスト名。"
  value       = aws_db_instance.this.address
}

output "db_master_secret_arn" {
  description = "Secrets Manager 上のマスターパスワードの ARN（値は含まれない）。"
  value       = aws_db_instance.this.master_user_secret[0].secret_arn
}

output "lbc_role_arn" {
  value = aws_iam_role.lbc.arn
}
