locals {
  common_tags = {
    Project   = "workboard-learning"
    Phase     = "07-aws-integration"
    ManagedBy = "terraform"
  }
}

# Phase 6 が作った既存のクラスター・VPC・サブネットを、名前とタグで見つける（Phase 6 のディレクトリや state は参照しない）。
data "aws_eks_cluster" "this" {
  name = var.cluster_name
}

locals {
  vpc_id = data.aws_eks_cluster.this.vpc_config[0].vpc_id

  # Managed Node Group のノードは、既定でクラスターのセキュリティグループを使う。
  node_security_group_id = data.aws_eks_cluster.this.vpc_config[0].cluster_security_group_id
}

# Phase 6 が kubernetes.io/role/internal-elb=1 を付けた private subnet。
data "aws_subnets" "private" {
  filter {
    name   = "vpc-id"
    values = [local.vpc_id]
  }

  tags = {
    "kubernetes.io/role/internal-elb" = "1"
  }
}
