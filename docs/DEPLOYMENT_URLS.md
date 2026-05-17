# Deployment URLs

Cloud Run is **not** running by default (tear down after demos to avoid charges). Redeploy with [DEPLOY_GCP.md](DEPLOY_GCP.md), then:

```bash
export URL=$(gcloud run services describe fieldops-agent-fabric \
  --region=us-central1 --format='value(status.url)')
echo "$URL/docs"    # Swagger UI
echo "$URL/health"  # Health check (/healthz is reserved on Cloud Run)
```

| Endpoint | Path |
|----------|------|
| API docs | `${URL}/docs` |
| Health | `${URL}/health` |
| Support API | `POST ${URL}/v1/support` |
