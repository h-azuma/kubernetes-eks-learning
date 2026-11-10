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
  description = "既存の EKS クラスター名（Phase 6 で作成したもの）。VPC・サブネット・セキュリティグループはここから探す。"
  type        = string
  default     = "workboard-learning"
}

variable "db_instance_class" {
  description = "RDS のインスタンスクラス。料金は cost-estimate.md を参照。"
  type        = string
  default     = "db.t4g.micro"
}

variable "db_allocated_storage_gb" {
  type    = number
  default = 20
}

variable "db_multi_az" {
  description = "true にすると Multi-AZ（待機系を持つ。費用がおよそ倍になる）。"
  type        = bool
  default     = false
}

variable "db_backup_retention_days" {
  description = "自動バックアップの保持日数。0 にすると自動バックアップと PITR が無効になる。"
  type        = number
  default     = 7
}

variable "db_deletion_protection" {
  description = "true にすると、この値を false に更新するまで RDS を削除できない。"
  type        = bool
  default     = false
}

variable "db_skip_final_snapshot" {
  description = "false: 削除時に最終スナップショットを取る（残ると保管料金がかかる）。true: 取らずに削除する（データは戻せない）。"
  type        = bool
  default     = false
}
