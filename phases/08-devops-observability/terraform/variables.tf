variable "region" {
  description = "既存の EKS クラスターがある AWS リージョン。"
  type        = string
  default     = "ap-northeast-1"
}

variable "allowed_account_id" {
  description = "操作してよい AWS アカウント ID（12 桁）。違うアカウントの認証情報では実行できない。"
  type        = string

  validation {
    condition     = can(regex("^[0-9]{12}$", var.allowed_account_id))
    error_message = "12 桁の数字で指定してください。"
  }
}

variable "cluster_name" {
  description = "既存の EKS クラスター名（Phase 6 で作成したもの）。"
  type        = string
  default     = "workboard-learning"
}

variable "github_repository" {
  description = "ロールを引き受けてよい GitHub リポジトリ（owner/name）。fork を使う場合は自分のものにする。"
  type        = string

  validation {
    condition     = can(regex("^[A-Za-z0-9-]+/[A-Za-z0-9._-]+$", var.github_repository))
    error_message = "owner/name の形式で指定してください。"
  }
}

variable "github_environment" {
  description = "ロールを引き受けてよい GitHub の environment 名。cd.yaml の environment と同じにする。"
  type        = string
  default     = "lab"
}

variable "namespace" {
  description = "CD に書き込みを許す Kubernetes の namespace（Phase 7 が作ったもの）。"
  type        = string
  default     = "workboard"
}

variable "create_github_oidc_provider" {
  description = "false にすると、アカウントに既にある GitHub の OIDC プロバイダーを使う（同じ URL のプロバイダーは 1 つしか作れない）。"
  type        = bool
  default     = true
}

variable "db_master_secret_arn" {
  description = "RDS の管理パスワードを持つ Secrets Manager の ARN（Phase 7 の terraform output db_master_secret_arn）。空なら CD に読み取りを許さない。"
  type        = string
  default     = ""
}
