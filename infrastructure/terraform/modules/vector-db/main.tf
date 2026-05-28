# Vector-DB module — Amazon OpenSearch Serverless collection for AI/RAG.
#
# Spec: specs/ai/agent-design.md (Reason phase — retrieval augmentation)
# ADR:  ADR-0010 (Agent Framework Selection)
#
# Used for semantic search over documents and knowledge bases.
# The collection is encrypted at rest with an AWS-managed key.

resource "aws_opensearchserverless_security_policy" "encryption" {
  name        = "${var.name_prefix}-enc"
  type        = "encryption"
  description = "Encryption policy for ${var.name_prefix} vector collection"

  policy = jsonencode({
    Rules = [{
      ResourceType = "collection"
      Resource     = ["collection/${var.name_prefix}-vectors"]
    }]
    AWSOwnedKey = true
  })
}

resource "aws_opensearchserverless_security_policy" "network" {
  name        = "${var.name_prefix}-net"
  type        = "network"
  description = "Network policy for ${var.name_prefix} vector collection"

  policy = jsonencode([{
    Description = "VPC access for ${var.name_prefix}"
    Rules = [
      {
        ResourceType = "collection"
        Resource     = ["collection/${var.name_prefix}-vectors"]
      },
      {
        ResourceType = "dashboard"
        Resource     = ["collection/${var.name_prefix}-vectors"]
      },
    ]
    AllowFromPublic = false
  }])
}

resource "aws_opensearchserverless_access_policy" "main" {
  name        = "${var.name_prefix}-access"
  type        = "data"
  description = "Data access policy for ${var.name_prefix} vector collection"

  policy = jsonencode([{
    Rules = [
      {
        ResourceType = "index"
        Resource     = ["index/${var.name_prefix}-vectors/*"]
        Permission   = ["aoss:CreateIndex", "aoss:DeleteIndex", "aoss:UpdateIndex", "aoss:DescribeIndex", "aoss:ReadDocument", "aoss:WriteDocument"]
      },
      {
        ResourceType = "collection"
        Resource     = ["collection/${var.name_prefix}-vectors"]
        Permission   = ["aoss:CreateCollectionItems", "aoss:DeleteCollectionItems", "aoss:UpdateCollectionItems", "aoss:DescribeCollectionItems"]
      },
    ]
    Principal = var.allowed_principal_arns
  }])
}

resource "aws_opensearchserverless_collection" "vectors" {
  name        = "${var.name_prefix}-vectors"
  type        = "VECTORSEARCH"
  description = "Vector store for AI/RAG semantic search"

  depends_on = [
    aws_opensearchserverless_security_policy.encryption,
    aws_opensearchserverless_security_policy.network,
  ]

  tags = var.tags
}
