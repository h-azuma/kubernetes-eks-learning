variable "region" {
  description = "AWS リージョン。料金・AZ 数・遅延で選ぶ（decisions/0011）。"
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
  description = "EKS クラスター名。Phase 7 がこの名前でクラスターを探す。"
  type        = string
  default     = "workboard-learning"
}

variable "kubernetes_version" {
  description = "EKS の Kubernetes バージョン（標準サポート中のもの）。"
  type        = string
  default     = "1.35"
}

variable "admin_principal_arn" {
  description = "クラスター管理権限（AmazonEKSClusterAdminPolicy）を与える IAM ユーザーまたはロールの ARN。assumed-role のセッション ARN ではなくロール自体の ARN を指定する。"
  type        = string

  validation {
    condition     = can(regex("^arn:aws:iam::[0-9]{12}:(user|role)/", var.admin_principal_arn))
    error_message = "arn:aws:iam::<アカウント ID>:user/... または role/... の形式で指定してください。"
  }
}

variable "public_access_cidrs" {
  description = "EKS API エンドポイント（public）へ接続してよい CIDR。自分のグローバル IP の /32 だけを指定する。"
  type        = list(string)

  validation {
    condition     = length(var.public_access_cidrs) > 0 && !contains(var.public_access_cidrs, "0.0.0.0/0")
    error_message = "1 件以上の CIDR を指定し、0.0.0.0/0（全世界に公開）は指定しないでください。"
  }
}

variable "vpc_cidr" {
  description = "学習用 VPC の CIDR。"
  type        = string
  default     = "10.20.0.0/16"
}

variable "single_nat_gateway" {
  description = "true: NAT Gateway を 1 つだけ作る（安い、AZ 障害で private subnet の外向き通信が止まる）。false: AZ ごとに作る。"
  type        = bool
  default     = true
}

variable "node_instance_types" {
  description = "Managed Node Group のインスタンスタイプ。Windows でビルドした x86_64 のイメージを動かすため x86_64 を選ぶ。"
  type        = list(string)
  default     = ["t3.medium"]
}

variable "node_ami_type" {
  description = "Managed Node Group の AMI タイプ。"
  type        = string
  default     = "AL2023_x86_64_STANDARD"
}

variable "node_desired_size" {
  type    = number
  default = 2
}

variable "node_min_size" {
  type    = number
  default = 1
}

variable "node_max_size" {
  type    = number
  default = 3
}

variable "node_disk_size_gb" {
  type    = number
  default = 20
}

variable "cluster_log_types" {
  description = "CloudWatch Logs へ送るコントロールプレーンログ（api, audit, authenticator, controllerManager, scheduler）。既定は無効（ログ料金を避ける）。"
  type        = list(string)
  default     = []
}

variable "log_retention_days" {
  type    = number
  default = 7
}

variable "ecr_force_delete" {
  description = "true にすると、イメージが残っていても ECR リポジトリを削除する。"
  type        = bool
  default     = false
}
