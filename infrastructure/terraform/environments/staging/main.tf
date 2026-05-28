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

variable "aws_region" {
  default = "us-east-1"
}

module "networking" {
  source      = "../../modules/networking"
  environment = "staging"
  vpc_cidr    = "10.1.0.0/16"
  public_subnet_cidrs  = ["10.1.1.0/24", "10.1.2.0/24"]
  private_subnet_cidrs = ["10.1.11.0/24", "10.1.12.0/24"]
  availability_zones   = ["${var.aws_region}a", "${var.aws_region}b"]
}

module "kubernetes" {
  source             = "../../modules/kubernetes"
  environment        = "staging"
  cluster_name       = "monorepo-staging"
  vpc_id             = module.networking.vpc_id
  private_subnet_ids = module.networking.private_subnet_ids
  node_instance_types = ["m6i.large"]
  node_desired_size  = 2
  node_min_size      = 1
  node_max_size      = 5
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

output "cluster_endpoint"  { value = module.kubernetes.cluster_endpoint }
output "redis_url"         { value = module.cache.redis_url; sensitive = true }
