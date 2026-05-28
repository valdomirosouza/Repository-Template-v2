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
