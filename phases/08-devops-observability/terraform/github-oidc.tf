# GitHub Actions が OIDC トークンで AWS の一時認証情報を受け取るための信頼関係。長期のアクセスキーは作らない。
# 検証は AWS 側の信頼済み CA で行われるため、thumbprint は指定しない。
resource "aws_iam_openid_connect_provider" "github" {
  count = var.create_github_oidc_provider ? 1 : 0

  url            = "https://${local.github_oidc_url}"
  client_id_list = ["sts.amazonaws.com"]
}

data "aws_iam_openid_connect_provider" "github" {
  count = var.create_github_oidc_provider ? 0 : 1

  url = "https://${local.github_oidc_url}"
}

locals {
  oidc_provider_arn = var.create_github_oidc_provider ? aws_iam_openid_connect_provider.github[0].arn : data.aws_iam_openid_connect_provider.github[0].arn
}

# 引き受けられるのは、指定したリポジトリの、指定した environment のジョブだけ。
# environment の承認（required reviewers）を通ったジョブだけが、この sub を持つトークンを得る。
data "aws_iam_policy_document" "cd_assume" {
  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [local.oidc_provider_arn]
    }

    condition {
      test     = "StringEquals"
      variable = "${local.github_oidc_url}:aud"
      values   = ["sts.amazonaws.com"]
    }

    condition {
      test     = "StringEquals"
      variable = "${local.github_oidc_url}:sub"
      values   = ["repo:${var.github_repository}:environment:${var.github_environment}"]
    }
  }
}

resource "aws_iam_role" "cd" {
  name                 = "${var.cluster_name}-github-cd"
  assume_role_policy   = data.aws_iam_policy_document.cd_assume.json
  max_session_duration = 3600
}

data "aws_iam_policy_document" "cd" {
  statement {
    sid       = "EcrLogin"
    actions   = ["ecr:GetAuthorizationToken"]
    resources = ["*"]
  }

  statement {
    sid = "EcrPush"
    actions = [
      "ecr:BatchCheckLayerAvailability",
      "ecr:InitiateLayerUpload",
      "ecr:UploadLayerPart",
      "ecr:CompleteLayerUpload",
      "ecr:PutImage",
    ]
    resources = [for name in local.ecr_repositories : "arn:aws:ecr:${var.region}:${data.aws_caller_identity.current.account_id}:repository/${name}"]
  }

  statement {
    sid       = "EksKubeconfig"
    actions   = ["eks:DescribeCluster"]
    resources = ["arn:aws:eks:${var.region}:${data.aws_caller_identity.current.account_id}:cluster/${var.cluster_name}"]
  }

  dynamic "statement" {
    for_each = var.db_master_secret_arn == "" ? [] : [var.db_master_secret_arn]

    content {
      sid       = "DbPasswordRead"
      actions   = ["secretsmanager:GetSecretValue"]
      resources = [statement.value]
    }
  }
}

resource "aws_iam_role_policy" "cd" {
  name   = "cd"
  role   = aws_iam_role.cd.id
  policy = data.aws_iam_policy_document.cd.json
}

# IAM の権限とは別に、Kubernetes 側の認可が必要。workboard namespace の編集だけを許す（クラスター全体の管理権限は与えない）。
resource "aws_eks_access_entry" "cd" {
  cluster_name  = var.cluster_name
  principal_arn = aws_iam_role.cd.arn
  type          = "STANDARD"
}

resource "aws_eks_access_policy_association" "cd" {
  cluster_name  = var.cluster_name
  principal_arn = aws_eks_access_entry.cd.principal_arn
  policy_arn    = "arn:aws:eks::aws:cluster-access-policy/AmazonEKSEditPolicy"

  access_scope {
    type       = "namespace"
    namespaces = [var.namespace]
  }
}
