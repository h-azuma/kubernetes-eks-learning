terraform {
  required_version = "~> 1.17.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.72"
    }
  }

  # state はローカルファイル（terraform.tfstate）。Phase 6 の state とは別で、Phase 6 のディレクトリも参照しない。
  # 既存のクラスターは変数 cluster_name と data source で見つける（decisions/0013）。
}

provider "aws" {
  region = var.region

  # 接続先の取り違えを防ぐ。別のアカウントの認証情報では plan/apply が失敗する。
  allowed_account_ids = [var.allowed_account_id]

  default_tags {
    tags = local.common_tags
  }
}
