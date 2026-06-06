# MILODO Docker Runtime

## Usage

Build and start the runtime:

```powershell
docker-compose build --no-cache
docker-compose up -d
```

Check containers:

```powershell
docker ps --filter "name=milodo"
```

Check API health:

```powershell
curl http://localhost:8520/health
```

## ⚠️ Queue Architecture Important

### Current limitation

The MILODO queue system uses Python queue.Queue().

This queue is:
- in-memory only
- process-local
- not shared across containers

### Current state

```txt
milodo-api
├── HTTP API port 8520
├── Queue runtime
└── Worker thread built-in

milodo-worker
└── Standby mode future infra target
```

### What this means

- async jobs POST /jobs/autocorrect work correctly
- GET /jobs/{id} returns live status
- GET /jobs/metrics shows real metrics
- milodo-worker container is currently standby only
- scaling workers has no effect yet

### Future PHASE 8.4+

```txt
milodo-api
↓
Redis / Valkey
↓
milodo-worker-1
milodo-worker-2
milodo-worker-3
```

When a distributed queue backend is added, milodo-worker containers will consume jobs from Redis/Valkey, enabling true horizontal scaling.

## Scaling future

```powershell
docker-compose up -d --scale milodo-worker=3
```

NOTE:
Scaling workers has no effect until a distributed queue backend Redis/Valkey is implemented.
Currently all async processing runs inside milodo-api.

## Async job test

```powershell
$body = @{
    html = "<html><head><title>Test</title></head><body><h1>Produit</h1></body></html>"
} | ConvertTo-Json

$response = Invoke-RestMethod `
-Method POST `
-Uri http://localhost:8520/jobs/autocorrect `
-ContentType "application/json" `
-Body $body

$response

Invoke-RestMethod `
-Uri "http://localhost:8520/jobs/$($response.job_id)"
```

## Worker standby log

```powershell
docker logs milodo-worker
```

Expected:

```txt
[MILODO WORKER] Standby mode — waiting for distributed queue backend
```
