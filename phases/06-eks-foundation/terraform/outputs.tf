output "region" {
  value = var.region
}

output "cluster_name" {
  value = aws_eks_cluster.this.name
}

output "cluster_endpoint" {
  value = aws_eks_cluster.this.endpoint
}

output "vpc_id" {
  value = aws_vpc.this.id
}

output "nat_public_ips" {
  description = "NAT Gateway の EIP。ノードの外向き通信の送信元。"
  value       = aws_eip.nat[*].public_ip
}

output "ecr_repository_urls" {
  value = { for name, repository in aws_ecr_repository.app : name => repository.repository_url }
}
