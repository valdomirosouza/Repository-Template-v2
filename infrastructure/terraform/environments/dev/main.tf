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
  }
  # Local backend — no remote state needed for dev.
  # Switch to an S3 backend when sharing state across a team.
  backend "local" {}
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

variable "aws_region" {
  default = "us-east-1"
}

# ── Networking ──────────────────────────────────────────────────────────────
# Single AZ to cut NAT-gateway costs. Expand to multi-AZ before staging.
module "networking" {
  source      = "../../modules/networking"
  environment = "dev"
  vpc_cidr    = "10.2.0.0/16"
  public_subnet_cidrs  = ["10.2.1.0/24"]
  private_subnet_cidrs = ["10.2.11.0/24"]
  availability_zones   = ["${var.aws_region}a"]
}

# ── Kubernetes ──────────────────────────────────────────────────────────────
# Single t3.medium node — enough for all services in dev.
module "kubernetes" {
  source             = "../../modules/kubernetes"
  environment        = "dev"
  cluster_name       = "monorepo-dev"
  vpc_id             = module.networking.vpc_id
  private_subnet_ids = module.networking.private_subnet_ids
  node_instance_types = ["t3.medium"]
  node_desired_size  = 1
  node_min_size      = 1
  node_max_size      = 2
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

  environment          = "dev"
  cluster_name         = module.kubernetes.cluster_name
  oidc_provider_arn    = module.kubernetes.oidc_provider_arn
  oidc_provider_url    = module.kubernetes.oidc_provider_url
  aws_account_id       = data.aws_caller_identity.current.account_id
  aws_region           = var.aws_region
  helm_values_file     = "infrastructure/helm/api-gateway/values-dev.yaml"
  image_tag            = var.image_tag
}

# ── Domain Service ───────────────────────────────────────────────────────────
module "domain_service" {
  source = "../../modules/domain-service"

  environment          = "dev"
  oidc_provider_arn    = module.kubernetes.oidc_provider_arn
  oidc_provider_url    = module.kubernetes.oidc_provider_url
  aws_account_id       = data.aws_caller_identity.current.account_id
  aws_region           = var.aws_region
  db_secret_arn        = var.db_secret_arn
  helm_values_file     = "infrastructure/helm/domain-service/values-dev.yaml"
  image_tag            = var.image_tag
}

# ── Event Worker ─────────────────────────────────────────────────────────────
module "event_worker" {
  source = "../../modules/event-worker"

  environment          = "dev"
  oidc_provider_arn    = module.kubernetes.oidc_provider_arn
  oidc_provider_url    = module.kubernetes.oidc_provider_url
  aws_account_id       = data.aws_caller_identity.current.account_id
  aws_region           = var.aws_region
  helm_values_file     = "infrastructure/helm/event-worker/values-dev.yaml"
  image_tag            = var.image_tag
}

# ── Frontend ──────────────────────────────────────────────────────────────────
module "frontend" {
  source = "../../modules/frontend"

  environment          = "dev"
  oidc_provider_arn    = module.kubernetes.oidc_provider_arn
  oidc_provider_url    = module.kubernetes.oidc_provider_url
  aws_account_id       = data.aws_caller_identity.current.account_id
  aws_region           = var.aws_region
  helm_values_file     = "infrastructure/helm/frontend/values-dev.yaml"
  image_tag            = var.image_tag
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

output "cluster_endpoint"             { value = module.kubernetes.cluster_endpoint }
output "redis_url"                    { value = module.cache.redis_url; sensitive = true }
output "api_gateway_irsa_role_arn"    { value = module.api_gateway.irsa_role_arn }
output "domain_service_irsa_role_arn" { value = module.domain_service.irsa_role_arn }
output "event_worker_irsa_role_arn"   { value = module.event_worker.irsa_role_arn }
output "frontend_irsa_role_arn"       { value = module.frontend.irsa_role_arn }
