data "aws_availability_zones" "available" {
  state = "available"
}

locals {
  common_tags = {
    Project   = "workboard-learning"
    Phase     = "06-eks-foundation"
    ManagedBy = "terraform"
  }

  azs = slice(data.aws_availability_zones.available.names, 0, 2)

  # /16 を /20 に分割: public は 0,1 番目、private は 2,3 番目。
  public_subnet_cidrs  = [for i in range(2) : cidrsubnet(var.vpc_cidr, 4, i)]
  private_subnet_cidrs = [for i in range(2) : cidrsubnet(var.vpc_cidr, 4, i + 2)]

  nat_count = var.single_nat_gateway ? 1 : 2
}
