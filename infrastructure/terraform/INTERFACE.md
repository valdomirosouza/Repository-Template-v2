# Terraform → Runtime Interface (ADR-0088)

The Helm/K8s layer (`infrastructure/helm/`, `infrastructure/k8s/`, `cd-*.yml`) is the portable
runtime contract. A provider implementation of this Terraform tree — AWS today
(`environments/`, `modules/`), GCP/Azure bring-your-own — is **complete when it emits these
outputs**. Nothing in the runtime layer may reach past this list into provider-specific
resources.

| Output | Consumed by | Notes |
| --- | --- | --- |
| `cluster_name`, `cluster_endpoint`, `cluster_ca_certificate` | `cd-staging.yml`, `cd-production.yml` (kubeconfig) | any conformant Kubernetes ≥ 1.29 |
| `kubeconfig_secret_name` | CI secret `KUBECONFIG` | written to the CI secret store, never to the repo |
| `database_url_secret`, `redis_url_secret`, `kafka_bootstrap_secret` | Helm values `secrets.*` | secret *names*; values stay in the provider's secret manager |
| `otlp_endpoint` | OTel collector Helm values | gRPC 4317 |
| `image_registry` | `IMAGE_REPOSITORY_BASE` repository variable | ghcr.io by default, overridable |
| `service_identities` (api-gateway, domain-service, event-worker, frontend) | Helm `serviceAccount.annotations` | IRSA on AWS; Workload Identity on GCP; Managed Identity on Azure |
| `feature_flag_endpoint` | flagd Helm values | ADR-0015 |

Account-, region- and cluster-specific values live in `backend.hcl` and `terraform.tfvars`
(both gitignored, examples committed) — never as literals in `.tf` files.
