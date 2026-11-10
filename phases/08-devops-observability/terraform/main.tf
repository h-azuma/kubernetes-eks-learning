locals {
  common_tags = {
    Project   = "workboard-learning"
    Phase     = "08-devops-observability"
    ManagedBy = "terraform"
  }

  github_oidc_url  = "token.actions.githubusercontent.com"
  ecr_repositories = ["workboard-api", "workboard-web"]
}

data "aws_caller_identity" "current" {}
