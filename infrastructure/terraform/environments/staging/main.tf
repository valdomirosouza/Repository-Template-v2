# Staging environment — wires networking, kubernetes, and cache modules.
# Apply: terraform -chdir=infrastructure/terraform/environments/staging apply
# ADR:   ADR-0006 (Deployment Strategy), ADR-0008 (Secrets Management)

terraform {
  required_version = ">= 1.9"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    helm = {
      source  = "hashicorp/helm"
      version = "~> 2.13"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.30"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
    tls = {
      source  = "hashicorp/tls"
      version = "~> 4.0"
    }
  }
  backend "s3" {
    # Replace with your state bucket before first apply:
    bucket         = "your-org-terraform-state"
    key            = "monorepo/staging/terraform.tfstate"
    region         = "us-east-1"
    encrypt        = true
    dynamodb_table = "terraform-state-lock"
  }
}

locals {
  cluster_name = "monorepo-staging"
}

provider "aws" {
  region = var.aws_region
  default_tags {
    tags = {
      Project     = "monorepo"
      Environment = "staging"
      ManagedBy   = "terraform"
    }
  }
}

# NOTE: helm and kubernetes providers require the EKS cluster to exist.
# On first apply, run: terraform apply -target=module.kubernetes
# then: terraform apply
data "aws_eks_cluster" "main" {
  name = local.cluster_name
}

data "aws_eks_cluster_auth" "main" {
  name = local.cluster_name
}

provider "helm" {
  kubernetes {
    host                   = data.aws_eks_cluster.main.endpoint
    cluster_ca_certificate = base64decode(data.aws_eks_cluster.main.certificate_authority[0].data)
    token                  = data.aws_eks_cluster_auth.main.token
  }
}

provider "kubernetes" {
  host                   = data.aws_eks_cluster.main.endpoint
  cluster_ca_certificate = base64decode(data.aws_eks_cluster.main.certificate_authority[0].data)
  token                  = data.aws_eks_cluster_auth.main.token
}

variable "aws_region" {
  default = "us-east-1"
}

module "networking" {
  source               = "../../modules/networking"
  environment          = "staging"
  vpc_cidr             = "10.1.0.0/16"
  public_subnet_cidrs  = ["10.1.1.0/24", "10.1.2.0/24"]
  private_subnet_cidrs = ["10.1.11.0/24", "10.1.12.0/24"]
  availability_zones   = ["${var.aws_region}a", "${var.aws_region}b"]
}

module "kubernetes" {
  source              = "../../modules/kubernetes"
  environment         = "staging"
  cluster_name        = "monorepo-staging"
  vpc_id              = module.networking.vpc_id
  private_subnet_ids  = module.networking.private_subnet_ids
  node_instance_types = ["m6i.large"]
  node_desired_size   = 2
  node_min_size       = 1
  node_max_size       = 5
}

module "cache" {
  source             = "../../modules/cache"
  environment        = "staging"
  cluster_id         = "monorepo-staging-redis"
  vpc_id             = module.networking.vpc_id
  subnet_ids         = module.networking.private_subnet_ids
  security_group_ids = [module.networking.sg_data_id]
  node_type          = "cache.t4g.small"
  num_cache_nodes    = 1
}

# ── Database ──────────────────────────────────────────────────────────────────
module "database" {
  source = "../../modules/database"

  name_prefix                = "monorepo-staging"
  vpc_id                     = module.networking.vpc_id
  subnet_ids                 = module.networking.private_subnet_ids
  allowed_security_group_ids = [module.networking.sg_app_id]
  instance_class             = "db.t3.medium"
  # 1 writer + 1 reader, one instance per AZ across both staging AZs (FR-02).
  availability_zones    = ["${var.aws_region}a", "${var.aws_region}b"]
  reader_count          = 1
  deletion_protection   = false
  backup_retention_days = 7
  tags                  = { Project = "monorepo", Environment = "staging", ManagedBy = "terraform" }
}

module "api_gateway" {
  source = "../../modules/api-gateway"

  environment       = "staging"
  cluster_name      = module.kubernetes.cluster_name
  oidc_provider_arn = module.kubernetes.oidc_provider_arn
  oidc_provider_url = module.kubernetes.oidc_provider_url
  aws_account_id    = data.aws_caller_identity.current.account_id
  aws_region        = var.aws_region
  helm_values_file  = "infrastructure/helm/api-gateway/values-staging.yaml"
  image_tag         = var.image_tag
}

module "domain_service" {
  source = "../../modules/domain-service"

  environment       = "staging"
  oidc_provider_arn = module.kubernetes.oidc_provider_arn
  oidc_provider_url = module.kubernetes.oidc_provider_url
  aws_account_id    = data.aws_caller_identity.current.account_id
  aws_region        = var.aws_region
  db_secret_arn     = module.database.secret_arn
  helm_values_file  = "infrastructure/helm/domain-service/values-staging.yaml"
  image_tag         = var.image_tag
}

# ── Message Broker ───────────────────────────────────────────────────────────
# 2-broker cluster (one per AZ). Replication factor set to 2 to match broker count.
module "message_broker" {
  source = "../../modules/message-broker"

  name_prefix                = "monorepo-staging"
  vpc_id                     = module.networking.vpc_id
  subnet_ids                 = module.networking.private_subnet_ids
  allowed_security_group_ids = [module.networking.sg_app_id]
  broker_instance_type       = "kafka.m5.large"
  broker_volume_size_gb      = 100
  default_replication_factor = 2
  min_insync_replicas        = 1
  tags                       = { Project = "monorepo", Environment = "staging", ManagedBy = "terraform" }
}

module "event_worker" {
  source = "../../modules/event-worker"

  environment       = "staging"
  oidc_provider_arn = module.kubernetes.oidc_provider_arn
  oidc_provider_url = module.kubernetes.oidc_provider_url
  aws_account_id    = data.aws_caller_identity.current.account_id
  aws_region        = var.aws_region
  msk_cluster_arn   = module.message_broker.cluster_arn
  dlq_sqs_arn       = ""
  helm_values_file  = "infrastructure/helm/event-worker/values-staging.yaml"
  image_tag         = var.image_tag
}

module "frontend" {
  source = "../../modules/frontend"

  environment       = "staging"
  oidc_provider_arn = module.kubernetes.oidc_provider_arn
  oidc_provider_url = module.kubernetes.oidc_provider_url
  aws_account_id    = data.aws_caller_identity.current.account_id
  aws_region        = var.aws_region
  helm_values_file  = "infrastructure/helm/frontend/values-staging.yaml"
  image_tag         = var.image_tag
}

# ── Observability ─────────────────────────────────────────────────────────────

locals {
  obs_tags = { Project = "monorepo", Environment = "staging", ManagedBy = "terraform" }
}

module "obs_api_gateway" {
  source                   = "../../modules/observability"
  name_prefix              = "monorepo-staging"
  service_name             = "api-gateway"
  log_retention_days       = 30
  error_rate_threshold     = 1.0
  p99_latency_threshold_ms = 500
  tags                     = local.obs_tags
}

module "obs_domain_service" {
  source                   = "../../modules/observability"
  name_prefix              = "monorepo-staging"
  service_name             = "domain-service"
  log_retention_days       = 30
  error_rate_threshold     = 1.0
  p99_latency_threshold_ms = 500
  tags                     = local.obs_tags
}

module "obs_event_worker" {
  source                   = "../../modules/observability"
  name_prefix              = "monorepo-staging"
  service_name             = "event-worker"
  log_retention_days       = 30
  error_rate_threshold     = 1.0
  p99_latency_threshold_ms = 500
  tags                     = local.obs_tags
}

module "obs_frontend" {
  source                   = "../../modules/observability"
  name_prefix              = "monorepo-staging"
  service_name             = "frontend"
  log_retention_days       = 30
  error_rate_threshold     = 1.0
  p99_latency_threshold_ms = 500
  tags                     = local.obs_tags
}

# ── Vector DB ─────────────────────────────────────────────────────────────────
module "vector_db" {
  source      = "../../modules/vector-db"
  name_prefix = "monorepo-staging"
  allowed_principal_arns = [
    module.api_gateway.irsa_role_arn,
    module.domain_service.irsa_role_arn,
  ]
  tags = { Project = "monorepo", Environment = "staging", ManagedBy = "terraform" }
}

data "aws_caller_identity" "current" {}

variable "image_tag" {
  description = "Container image tag to deploy for all services"
  type        = string
  default     = "latest"
}

output "cluster_endpoint" { value = module.kubernetes.cluster_endpoint }
output "redis_url" {
  value     = module.cache.redis_url
  sensitive = true
}
output "db_endpoint" { value = module.database.endpoint }
output "db_secret_arn" { value = module.database.secret_arn }
output "kafka_bootstrap_brokers" {
  value     = module.message_broker.bootstrap_brokers_sasl_iam
  sensitive = true
}
output "kafka_client_iam_policy_arn" { value = module.message_broker.kafka_client_iam_policy_arn }
output "vector_db_endpoint" { value = module.vector_db.collection_endpoint }
output "vector_db_arn" { value = module.vector_db.collection_arn }
output "api_gateway_irsa_role_arn" { value = module.api_gateway.irsa_role_arn }
output "domain_service_irsa_role_arn" { value = module.domain_service.irsa_role_arn }
output "event_worker_irsa_role_arn" { value = module.event_worker.irsa_role_arn }
output "frontend_irsa_role_arn" { value = module.frontend.irsa_role_arn }
output "obs_api_gateway_sns_arn" { value = module.obs_api_gateway.sns_topic_arn }
output "obs_domain_service_sns_arn" { value = module.obs_domain_service.sns_topic_arn }
output "obs_event_worker_sns_arn" { value = module.obs_event_worker.sns_topic_arn }
output "obs_frontend_sns_arn" { value = module.obs_frontend.sns_topic_arn }
