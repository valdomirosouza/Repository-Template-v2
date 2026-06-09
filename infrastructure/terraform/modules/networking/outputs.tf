output "vpc_id" {
  description = "ID of the VPC"
  value       = aws_vpc.main.id
}

output "public_subnet_ids" {
  description = "IDs of public subnets"
  value       = aws_subnet.public[*].id
}

output "private_subnet_ids" {
  description = "IDs of private subnets"
  value       = aws_subnet.private[*].id
}

output "sg_ingress_id" {
  description = "Security group ID for the ingress layer"
  value       = aws_security_group.ingress.id
}

output "sg_app_id" {
  description = "Security group ID for application pods"
  value       = aws_security_group.app.id
}

output "sg_data_id" {
  description = "Security group ID for data layer (Postgres, Redis, Kafka)"
  value       = aws_security_group.data.id
}

output "sg_vpc_endpoints_id" {
  description = "Security group ID for interface VPC endpoints"
  value       = aws_security_group.vpc_endpoints.id
}

output "s3_vpc_endpoint_id" {
  description = "ID of the S3 gateway VPC endpoint"
  value       = aws_vpc_endpoint.s3.id
}

output "interface_vpc_endpoint_ids" {
  description = "Map of interface VPC endpoint name => endpoint ID (ecr_api, ecr_dkr, secretsmanager, sts)"
  value       = { for k, v in aws_vpc_endpoint.interface : k => v.id }
}
