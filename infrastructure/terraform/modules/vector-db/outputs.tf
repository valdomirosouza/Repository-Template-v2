output "collection_endpoint" {
  description = "OpenSearch Serverless collection endpoint for vector search operations."
  value       = aws_opensearchserverless_collection.vectors.collection_endpoint
}

output "collection_arn" {
  description = "ARN of the OpenSearch Serverless collection."
  value       = aws_opensearchserverless_collection.vectors.arn
}

output "dashboard_endpoint" {
  description = "OpenSearch Dashboards endpoint."
  value       = aws_opensearchserverless_collection.vectors.dashboard_endpoint
}
