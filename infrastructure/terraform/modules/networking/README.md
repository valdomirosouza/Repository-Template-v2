# `networking`

Provisions the AWS network foundation: a VPC with public/private subnets across the given AZs, an internet
gateway, one NAT gateway per public subnet, route tables, and three layered security groups (ingress → app → data).

## Resources

- `aws_vpc.main`, `aws_internet_gateway.main`
- `aws_subnet.public` / `aws_subnet.private` (one per CIDR)
- `aws_eip.nat`, `aws_nat_gateway.main` (one per public subnet)
- `aws_route_table.public` / `aws_route_table.private` + associations
- `aws_security_group.ingress` (HTTP/HTTPS from internet)
- `aws_security_group.app` (port 8000 from ingress SG)
- `aws_security_group.data` (Postgres 5432 / Redis TLS 6380 / Kafka 9092 from app SG)

Locals: `name = "monorepo-${var.environment}"`, `common_tags`.

## Inputs

| Name                   | Type           | Default                                          | Description                                                  |
| ---------------------- | -------------- | ------------------------------------------------ | ------------------------------------------------------------ |
| `environment`          | `string`       | _required_                                       | Deployment environment (`dev` \| `staging` \| `production`). |
| `vpc_cidr`             | `string`       | `"10.0.0.0/16"`                                  | CIDR block for the VPC.                                      |
| `public_subnet_cidrs`  | `list(string)` | `["10.0.1.0/24","10.0.2.0/24","10.0.3.0/24"]`    | Public subnet CIDRs (one per AZ).                            |
| `private_subnet_cidrs` | `list(string)` | `["10.0.11.0/24","10.0.12.0/24","10.0.13.0/24"]` | Private subnet CIDRs (one per AZ).                           |
| `availability_zones`   | `list(string)` | _required_                                       | AZs to deploy into.                                          |
| `tags`                 | `map(string)`  | `{}`                                             | Additional tags applied to all resources.                    |

## Outputs

| Name                 | Description                                                    |
| -------------------- | -------------------------------------------------------------- |
| `vpc_id`             | ID of the VPC.                                                 |
| `public_subnet_ids`  | IDs of the public subnets.                                     |
| `private_subnet_ids` | IDs of the private subnets.                                    |
| `sg_ingress_id`      | Security group ID for the ingress layer.                       |
| `sg_app_id`          | Security group ID for application pods.                        |
| `sg_data_id`         | Security group ID for the data layer (Postgres, Redis, Kafka). |

## Usage

```hcl
module "networking" {
  source = "../../modules/networking"

  environment          = "production"
  vpc_cidr             = "10.0.0.0/16"
  public_subnet_cidrs  = ["10.0.1.0/24", "10.0.2.0/24", "10.0.3.0/24"]
  private_subnet_cidrs = ["10.0.11.0/24", "10.0.12.0/24", "10.0.13.0/24"]
  availability_zones   = ["us-east-1a", "us-east-1b", "us-east-1c"]
}
```
