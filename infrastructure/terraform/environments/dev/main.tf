# Dev environment — single-AZ, cost-optimised, local state.
# Apply: terraform -chdir=infrastructure/terraform/environments/dev apply
# ADR:   ADR-0006 (Deployment Strategy), ADR-0008 (Secrets Management)
#
# NOTE: Dev uses a local backend so no state bucket is required. Commit
# terraform.tfstate to .gitignore (already excluded by the root .gitignore).

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
  # Local backend — no remote state needed for dev.
  # Switch to an S3 backend when sharing state across a team.
  backend "local" {}
}

locals {
  cluster_name = "monorepo-dev"
}

provider "aws" {
  region = var.aws_region
  default_tags {
    tags = {
      Project     = "monorepo"
      Environment = "dev"
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

# ── Networking ──────────────────────────────────────────────────────────────
# Single AZ to cut NAT-gateway costs. Expand to multi-AZ before staging.
module "networking" {
  source               = "../../modules/networking"
  environment          = "dev"
  vpc_cidr             = "10.2.0.0/16"
  public_subnet_cidrs  = ["10.2.1.0/24"]
  private_subnet_cidrs = ["10.2.11.0/24"]
  availability_zones   = ["${var.aws_region}a"]
}

# ── Kubernetes ──────────────────────────────────────────────────────────────
# Single t3.medium node — enough for all services in dev.
module "kubernetes" {
  source              = "../../modules/kubernetes"
  environment         = "dev"
  cluster_name        = "monorepo-dev"
  vpc_id              = module.networking.vpc_id
  private_subnet_ids  = module.networking.private_subnet_ids
  node_instance_types = ["t3.medium"]
  node_desired_size   = 1
  node_min_size       = 1
  node_max_size       = 2
}

# ── Cache ────────────────────────────────────────────────────────────────────
# Smallest Redis node; TLS/encryption still enforced (ADR-0019).
module "cache" {
  source             = "../../modules/cache"
  environment        = "dev"
  cluster_id         = "monorepo-dev-redis"
  vpc_id             = module.networking.vpc_id
  subnet_ids         = module.networking.private_subnet_ids
  security_group_ids = [module.networking.sg_data_id]
  node_type          = "cache.t4g.micro"
  num_cache_nodes    = 1
}

# ── API Gateway ──────────────────────────────────────────────────────────────
module "api_gateway" {
  source = "../../modules/api-gateway"

  environment       = "dev"
  cluster_name      = module.kubernetes.cluster_name
  oidc_provider_arn = module.kubernetes.oidc_provider_arn
  oidc_provider_url = module.kubernetes.oidc_provider_url
  aws_account_id    = data.aws_caller_identity.current.account_id
  aws_region        = var.aws_region
  helm_values_file  = "infrastructure/helm/api-gateway/values-dev.yaml"
  image_tag         = var.image_tag
}

# ── Domain Service ───────────────────────────────────────────────────────────
module "domain_service" {
  source = "../../modules/domain-service"

  environment       = "dev"
  oidc_provider_arn = module.kubernetes.oidc_provider_arn
  oidc_provider_url = module.kubernetes.oidc_provider_url
  aws_account_id    = data.aws_caller_identity.current.account_id
  aws_region        = var.aws_region
  db_secret_arn     = var.db_secret_arn
  helm_values_file  = "infrastructure/helm/domain-service/values-dev.yaml"
  image_tag         = var.image_tag
}

# ── Event Worker ─────────────────────────────────────────────────────────────
module "event_worker" {
  source = "../../modules/event-worker"

  environment       = "dev"
  oidc_provider_arn = module.kubernetes.oidc_provider_arn
  oidc_provider_url = module.kubernetes.oidc_provider_url
  aws_account_id    = data.aws_caller_identity.current.account_id
  aws_region        = var.aws_region
  helm_values_file  = "infrastructure/helm/event-worker/values-dev.yaml"
  image_tag         = var.image_tag
}

# ── Frontend ──────────────────────────────────────────────────────────────────
module "frontend" {
  source = "../../modules/frontend"

  environment       = "dev"
  oidc_provider_arn = module.kubernetes.oidc_provider_arn
  oidc_provider_url = module.kubernetes.oidc_provider_url
  aws_account_id    = data.aws_caller_identity.current.account_id
  aws_region        = var.aws_region
  helm_values_file  = "infrastructure/helm/frontend/values-dev.yaml"
  image_tag         = var.image_tag
}

# ── Observability ─────────────────────────────────────────────────────────────
# One instance per service: log groups + Golden Signal alarms.
# Thresholds are loosened for dev (5% error rate, 1s P99) to reduce noise.

locals {
  obs_tags = { Project = "monorepo", Environment = "dev", ManagedBy = "terraform" }
}

module "obs_api_gateway" {
  source                   = "../../modules/observability"
  name_prefix              = "monorepo-dev"
  service_name             = "api-gateway"
  log_retention_days       = 7
  error_rate_threshold     = 5.0
  p99_latency_threshold_ms = 1000
  tags                     = local.obs_tags
}

module "obs_domain_service" {
  source                   = "../../modules/observability"
  name_prefix              = "monorepo-dev"
  service_name             = "domain-service"
  log_retention_days       = 7
  error_rate_threshold     = 5.0
  p99_latency_threshold_ms = 1000
  tags                     = local.obs_tags
}

module "obs_event_worker" {
  source                   = "../../modules/observability"
  name_prefix              = "monorepo-dev"
  service_name             = "event-worker"
  log_retention_days       = 7
  error_rate_threshold     = 5.0
  p99_latency_threshold_ms = 1000
  tags                     = local.obs_tags
}

module "obs_frontend" {
  source                   = "../../modules/observability"
  name_prefix              = "monorepo-dev"
  service_name             = "frontend"
  log_retention_days       = 7
  error_rate_threshold     = 5.0
  p99_latency_threshold_ms = 1000
  tags                     = local.obs_tags
}

# ── Vector DB ─────────────────────────────────────────────────────────────────
# OpenSearch Serverless — opt-in AI Agents Module component (ADR-0010).
# Access granted to api-gateway and domain-service IRSA roles.
module "vector_db" {
  source      = "../../modules/vector-db"
  name_prefix = "monorepo-dev"
  allowed_principal_arns = [
    module.api_gateway.irsa_role_arn,
    module.domain_service.irsa_role_arn,
  ]
  tags = { Project = "monorepo", Environment = "dev", ManagedBy = "terraform" }
}

data "aws_caller_identity" "current" {}

variable "db_secret_arn" {
  description = "Secrets Manager ARN for the dev PostgreSQL credentials"
  type        = string
  default     = ""
}

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
