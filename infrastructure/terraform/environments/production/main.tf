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

output "cluster_endpoint"  { value = module.kubernetes.cluster_endpoint }
output "redis_url"         { value = module.cache.redis_url; sensitive = true }
