# Networking module — VPC, public/private subnets, NAT gateway, security groups.
# Spec: specs/system/architecture.md (Infrastructure)
# ADR:  ADR-0006 (Deployment Strategy), ADR-0019 (Redis TLS)

locals {
  name = "monorepo-${var.environment}"
  common_tags = merge(var.tags, {
    Environment = var.environment
    ManagedBy   = "terraform"
    Module      = "networking"
  })

  # One NAT gateway per AZ for HA (default), or a single shared NAT for non-prod cost
  # savings when var.single_nat_gateway = true.
  nat_gateway_count = var.single_nat_gateway ? 1 : length(var.public_subnet_cidrs)
}

data "aws_region" "current" {}

resource "aws_vpc" "main" {
  cidr_block           = var.vpc_cidr
  enable_dns_support   = true
  enable_dns_hostnames = true

  tags = merge(local.common_tags, { Name = "${local.name}-vpc" })
}

resource "aws_internet_gateway" "main" {
  vpc_id = aws_vpc.main.id
  tags   = merge(local.common_tags, { Name = "${local.name}-igw" })
}

# Public subnets — load balancers, NAT gateways
resource "aws_subnet" "public" {
  count                   = length(var.public_subnet_cidrs)
  vpc_id                  = aws_vpc.main.id
  cidr_block              = var.public_subnet_cidrs[count.index]
  availability_zone       = var.availability_zones[count.index]
  map_public_ip_on_launch = true

  tags = merge(local.common_tags, {
    Name                     = "${local.name}-public-${count.index + 1}"
    "kubernetes.io/role/elb" = "1"
  })
}

# Private subnets — application pods, databases, cache
resource "aws_subnet" "private" {
  count             = length(var.private_subnet_cidrs)
  vpc_id            = aws_vpc.main.id
  cidr_block        = var.private_subnet_cidrs[count.index]
  availability_zone = var.availability_zones[count.index]

  tags = merge(local.common_tags, {
    Name                              = "${local.name}-private-${count.index + 1}"
    "kubernetes.io/role/internal-elb" = "1"
  })
}

# NAT gateway — egress for private subnets.
# One per AZ for HA (default), or a single shared NAT when var.single_nat_gateway = true.
resource "aws_eip" "nat" {
  count  = local.nat_gateway_count
  domain = "vpc"
  tags   = merge(local.common_tags, { Name = "${local.name}-nat-eip-${count.index + 1}" })
}

resource "aws_nat_gateway" "main" {
  count         = local.nat_gateway_count
  allocation_id = aws_eip.nat[count.index].id
  subnet_id     = aws_subnet.public[count.index].id
  tags          = merge(local.common_tags, { Name = "${local.name}-nat-${count.index + 1}" })
  depends_on    = [aws_internet_gateway.main]
}

# Route tables
resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id
  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.main.id
  }
  tags = merge(local.common_tags, { Name = "${local.name}-rt-public" })
}

resource "aws_route_table" "private" {
  count  = length(var.private_subnet_cidrs)
  vpc_id = aws_vpc.main.id
  route {
    cidr_block = "0.0.0.0/0"
    # With a single shared NAT, every private subnet routes through nat[0];
    # otherwise each private subnet uses the NAT in its own AZ.
    nat_gateway_id = var.single_nat_gateway ? aws_nat_gateway.main[0].id : aws_nat_gateway.main[count.index].id
  }
  tags = merge(local.common_tags, { Name = "${local.name}-rt-private-${count.index + 1}" })
}

resource "aws_route_table_association" "public" {
  count          = length(var.public_subnet_cidrs)
  subnet_id      = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.public.id
}

resource "aws_route_table_association" "private" {
  count          = length(var.private_subnet_cidrs)
  subnet_id      = aws_subnet.private[count.index].id
  route_table_id = aws_route_table.private[count.index].id
}

# Security groups
resource "aws_security_group" "ingress" {
  name        = "${local.name}-sg-ingress"
  description = "Allow HTTPS inbound from internet"
  vpc_id      = aws_vpc.main.id

  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
    description = "HTTPS from internet"
  }
  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
    description = "HTTP redirect only"
  }
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
    description = "Allow all egress"
  }
  tags = merge(local.common_tags, { Name = "${local.name}-sg-ingress" })
}

resource "aws_security_group" "app" {
  name        = "${local.name}-sg-app"
  description = "Application pods — allow traffic from ingress SG only"
  vpc_id      = aws_vpc.main.id

  ingress {
    from_port       = 8000
    to_port         = 8000
    protocol        = "tcp"
    security_groups = [aws_security_group.ingress.id]
    description     = "API traffic from ingress"
  }
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
    description = "Allow all egress"
  }
  tags = merge(local.common_tags, { Name = "${local.name}-sg-app" })
}

resource "aws_security_group" "data" {
  name        = "${local.name}-sg-data"
  description = "Databases and cache — allow traffic from app SG only"
  vpc_id      = aws_vpc.main.id

  ingress {
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.app.id]
    description     = "PostgreSQL from app"
  }
  ingress {
    from_port       = 6380
    to_port         = 6380
    protocol        = "tcp"
    security_groups = [aws_security_group.app.id]
    description     = "Redis TLS from app (ADR-0019)"
  }
  ingress {
    from_port       = 9092
    to_port         = 9092
    protocol        = "tcp"
    security_groups = [aws_security_group.app.id]
    description     = "Kafka from app"
  }
  tags = merge(local.common_tags, { Name = "${local.name}-sg-data" })
}

# ── VPC endpoints (INFRA-6a) ──────────────────────────────────────────────────
# Route EKS image pulls and secret fetches off the NAT gateway and keep that
# traffic on the AWS private network: S3 + ECR (api/dkr) for container pulls,
# Secrets Manager for credential fetches, STS for IRSA AssumeRoleWithWebIdentity.
# Spec: SPEC-INFRA-001 FR-01/§15 · ADR-0063 (extend networking in place).

# Security group for interface endpoints — accept HTTPS from inside the VPC only.
resource "aws_security_group" "vpc_endpoints" {
  name        = "${local.name}-sg-vpce"
  description = "Allow HTTPS to interface VPC endpoints from within the VPC"
  vpc_id      = aws_vpc.main.id

  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = [aws_vpc.main.cidr_block]
    description = "HTTPS from within the VPC to interface endpoints"
  }
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
    description = "Allow all egress"
  }
  tags = merge(local.common_tags, { Name = "${local.name}-sg-vpce" })
}

# Gateway endpoint — S3 (free; attached to the private route tables, no ENI).
resource "aws_vpc_endpoint" "s3" {
  vpc_id            = aws_vpc.main.id
  service_name      = "com.amazonaws.${data.aws_region.current.name}.s3"
  vpc_endpoint_type = "Gateway"
  route_table_ids   = aws_route_table.private[*].id
  tags              = merge(local.common_tags, { Name = "${local.name}-vpce-s3" })
}

# Interface endpoints — ECR (api + dkr), Secrets Manager, STS. One ENI per AZ
# in the private subnets; private DNS lets the AWS SDKs resolve the regional
# endpoint to the VPCE automatically.
locals {
  interface_endpoints = {
    ecr_api        = "com.amazonaws.${data.aws_region.current.name}.ecr.api"
    ecr_dkr        = "com.amazonaws.${data.aws_region.current.name}.ecr.dkr"
    secretsmanager = "com.amazonaws.${data.aws_region.current.name}.secretsmanager"
    sts            = "com.amazonaws.${data.aws_region.current.name}.sts"
  }
}

resource "aws_vpc_endpoint" "interface" {
  for_each = local.interface_endpoints

  vpc_id              = aws_vpc.main.id
  service_name        = each.value
  vpc_endpoint_type   = "Interface"
  subnet_ids          = aws_subnet.private[*].id
  security_group_ids  = [aws_security_group.vpc_endpoints.id]
  private_dns_enabled = true

  tags = merge(local.common_tags, { Name = "${local.name}-vpce-${each.key}" })
}
