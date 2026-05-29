# Runbook: Redis High Availability (Sentinel)

**Topic:** Redis HA activation and failover procedure
**Severity:** Operational — complete before first production deployment
**Owner:** SRE Lead

---

## Overview

By default the application connects to a single Redis instance. A single Redis is a
single point of failure for the HITL store, request store, and session memory. This
runbook describes how to activate Redis Sentinel for automatic primary election and
client failover.

---

## Prerequisites

- Redis 7+ Sentinel cluster (minimum 3 Sentinel nodes for quorum)
- Network connectivity from all app pods to all Sentinel nodes
- `REDIS_SENTINEL_ENABLED=true` in your environment

---

## Configuration

Set the following in your environment (`.env` or secrets manager):

```bash
# Enable Sentinel — disables direct redis_url connection on startup
REDIS_SENTINEL_ENABLED=true

# Must match sentinel.conf `sentinel monitor <name> ...` on all nodes
REDIS_SENTINEL_MASTER_NAME=mymaster

# All Sentinel node addresses (comma-separated)
REDIS_SENTINEL_HOSTS=sentinel-0.redis.svc:26379,sentinel-1.redis.svc:26379,sentinel-2.redis.svc:26379

# Keep redis_url as fallback during migration; not used when Sentinel is active
REDIS_URL=rediss://:password@redis-primary.svc:6379/0

# TLS is required in production (ADR-0019)
REDIS_TLS_ENABLED=true
```

> **Note:** The application currently uses `redis.asyncio.from_url()`. Sentinel mode
> requires `redis.asyncio.Sentinel` instead. Wire this in `src/api/rest/main.py` when
> `settings.redis_sentinel_enabled=True`. See the wiring example below.

---

## Wiring example (add to `src/api/rest/main.py`)

```python
if settings.redis_sentinel_enabled:
    sentinel_hosts = [
        tuple(h.split(":")) for h in settings.redis_sentinel_hosts.split(",")
    ]
    sentinel = redis_async.Sentinel(
        [(host, int(port)) for host, port in sentinel_hosts],
        sentinel_kwargs={"password": "<sentinel-password>"},
    )
    _redis_client = sentinel.master_for(
        settings.redis_sentinel_master_name,
        redis_class=redis_async.Redis,
        password="<redis-password>",
        ssl=settings.redis_tls_enabled,
        max_connections=settings.redis_max_connections,
        decode_responses=True,
    )
else:
    _redis_client = redis_async.from_url(settings.redis_url, **_redis_kwargs)
```

---

## Kubernetes / Helm deployment

Use the Bitnami Redis chart with Sentinel mode:

```bash
helm install redis bitnami/redis \
  --set architecture=replication \
  --set sentinel.enabled=true \
  --set sentinel.quorum=2 \
  --set auth.password=<your-password> \
  --set tls.enabled=true \
  --set tls.certFilename=tls.crt \
  --set tls.certKeyFilename=tls.key \
  --set tls.existingSecret=redis-tls-secret
```

---

## Failover verification

After a controlled failover (`redis-cli DEBUG sleep 30` on the primary):

```bash
# 1. Confirm Sentinel elected a new primary
redis-cli -p 26379 SENTINEL masters

# 2. Confirm app reconnected (check logs for "Redis client creation failed" — should not appear)
kubectl logs -l app=api-gateway | grep -i redis | tail -20

# 3. Confirm readiness probe is green
kubectl get pods -l app=api-gateway
curl http://localhost:8000/ready
```

---

## Runbook for Redis connection failure

If the primary is unreachable and Sentinel has not yet elected a replacement:

- The readiness probe (`GET /ready`) returns `503` — the load balancer removes the pod from rotation
- Requests that need Redis (HITL decisions, request state) fail with 503
- Requests that don't need Redis (health check, some read endpoints) continue

Recovery is automatic once Sentinel elects a new primary (typically < 30 s).

If Sentinel itself is unavailable (all 3 nodes unreachable), escalate to P0:

1. Check network connectivity between app pods and Sentinel nodes
2. Check Sentinel node process health: `redis-cli -p 26379 ping`
3. If all nodes are down, manually promote a replica: `redis-cli -h <replica> REPLICAOF NO ONE`
4. Update `REDIS_URL` to point to the manually-promoted primary

See also: `docs/sre/runbooks/redis-connection-failure.md`
