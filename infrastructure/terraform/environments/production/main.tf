# Production environment — wires networking, kubernetes, and cache modules.
# Apply: terraform -chdir=infrastructure/terraform/environments/production apply
# ADR:   ADR-0006 (Deployment Strategy), ADR-0008 (Secrets Management)

terraform {
  required_version = ">= 1.9"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
  backend "s3" {
    bucket         = "your-org-terraform-state"
    key            = "monorepo/production/terraform.tfstate"
    region         = "us-east-1"
    encrypt        = true
    dynamodb_table = "terraform-state-lock"
  }
}

provider "aws" {
  region = var.aws_region
  default_tags {
    tags = {
      Project     = "monorepo"
      Environment = "production"
      ManagedBy   = "terraform"
    }
  }
}

variable "aws_region" {
  default = "us-east-1"
}

module "networking" {
  source      = "../../modules/networking"
  environment = "production"
  vpc_cidr    = "10.0.0.0/16"
  public_subnet_cidrs  = ["10.0.1.0/24", "10.0.2.0/24", "10.0.3.0/24"]
  private_subnet_cidrs = ["10.0.11.0/24", "10.0.12.0/24", "10.0.13.0/24"]
  availability_zones   = ["${var.aws_region}a", "${var.aws_region}b", "${var.aws_region}c"]
}

module "kubernetes" {
  source             = "../../modules/kubernetes"
  environment        = "production"
  cluster_name       = "monorepo-production"
  vpc_id             = module.networking.vpc_id
  private_subnet_ids = module.networking.private_subnet_ids
  node_instance_types = ["m6i.xlarge"]
  node_desired_size  = 3
  node_min_size      = 3
  node_max_size      = 20
}

module "cache" {
  source             = "../../modules/cache"
  environment        = "production"
  cluster_id         = "monorepo-production-redis"
  vpc_id             = module.networking.vpc_id
  subnet_ids         = module.networking.private_subnet_ids
  security_group_ids = [module.networking.sg_data_id]
  node_type          = "cache.r7g.large"
  num_cache_nodes    = 3
}

module "api_gateway" {
  source = "../../modules/api-gateway"

  environment          = "production"
  cluster_name         = module.kubernetes.cluster_name
  oidc_provider_arn    = module.kubernetes.oidc_provider_arn
  oidc_provider_url    = module.kubernetes.oidc_provider_url
  aws_account_id       = data.aws_caller_identity.current.account_id
  aws_region           = var.aws_region
  helm_values_file     = "infrastructure/helm/api-gateway/values-production.yaml"
  image_tag            = var.image_tag
}

module "domain_service" {
  source = "../../modules/domain-service"

  environment          = "production"
  oidc_provider_arn    = module.kubernetes.oidc_provider_arn
  oidc_provider_url    = module.kubernetes.oidc_provider_url
  aws_account_id       = data.aws_caller_identity.current.account_id
  aws_region           = var.aws_region
  db_secret_arn        = var.db_secret_arn
  helm_values_file     = "infrastructure/helm/domain-service/values-production.yaml"
  image_tag            = var.image_tag
}

module "event_worker" {
  source = "../../modules/event-worker"

  environment          = "production"
  oidc_provider_arn    = module.kubernetes.oidc_provider_arn
  oidc_provider_url    = module.kubernetes.oidc_provider_url
  aws_account_id       = data.aws_caller_identity.current.account_id
  aws_region           = var.aws_region
  helm_values_file     = "infrastructure/helm/event-worker/values-production.yaml"
  image_tag            = var.image_tag
}

module "frontend" {
  source = "../../modules/frontend"

  environment          = "production"
  oidc_provider_arn    = module.kubernetes.oidc_provider_arn
  oidc_provider_url    = module.kubernetes.oidc_provider_url
  aws_account_id       = data.aws_caller_identity.current.account_id
  aws_region           = var.aws_region
  helm_values_file     = "infrastructure/helm/frontend/values-production.yaml"
  image_tag            = var.image_tag
}

data "aws_caller_identity" "current" {}

variable "db_secret_arn" {
  description = "Secrets Manager ARN for the production PostgreSQL credentials"
  type        = string
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
