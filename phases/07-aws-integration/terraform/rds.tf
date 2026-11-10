resource "aws_db_subnet_group" "this" {
  name       = "${var.cluster_name}-db"
  subnet_ids = data.aws_subnets.private.ids
}

# EKS ノード（クラスターのセキュリティグループ）からの 5432 だけを許可する。インターネットや VPC 全体には開けない。
resource "aws_security_group" "db" {
  name        = "${var.cluster_name}-db"
  description = "WorkBoard RDS: allow PostgreSQL from EKS nodes only"
  vpc_id      = local.vpc_id

  tags = { Name = "${var.cluster_name}-db" }
}

resource "aws_vpc_security_group_ingress_rule" "db_from_nodes" {
  security_group_id            = aws_security_group.db.id
  referenced_security_group_id = local.node_security_group_id
  ip_protocol                  = "tcp"
  from_port                    = 5432
  to_port                      = 5432
  description                  = "PostgreSQL from EKS nodes"
}

# TLS を必須にする（PostgreSQL 15 以降の既定も 1 だが、設定として明示して観察できるようにする）。
resource "aws_db_parameter_group" "this" {
  name   = "${var.cluster_name}-postgres17"
  family = "postgres17"

  parameter {
    name  = "rds.force_ssl"
    value = "1"
  }
}

resource "aws_db_instance" "this" {
  identifier     = "${var.cluster_name}-db"
  engine         = "postgres"
  engine_version = "17"
  instance_class = var.db_instance_class

  db_name  = "workboard"
  username = "workboard"

  # マスターパスワードは RDS が生成して Secrets Manager で管理する。Terraform の state・変数・Git にパスワードを持たない。
  manage_master_user_password = true

  allocated_storage = var.db_allocated_storage_gb
  storage_type      = "gp3"
  storage_encrypted = true

  db_subnet_group_name   = aws_db_subnet_group.this.name
  vpc_security_group_ids = [aws_security_group.db.id]
  parameter_group_name   = aws_db_parameter_group.this.name
  publicly_accessible    = false
  multi_az               = var.db_multi_az

  backup_retention_period   = var.db_backup_retention_days
  copy_tags_to_snapshot     = true
  deletion_protection       = var.db_deletion_protection
  skip_final_snapshot       = var.db_skip_final_snapshot
  final_snapshot_identifier = var.db_skip_final_snapshot ? null : "${var.cluster_name}-db-final"

  auto_minor_version_upgrade = true
}
