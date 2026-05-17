# Deploy FieldOps Agent Fabric on Google Cloud

Target: **Cloud Run** + **Vertex AI (Gemini)** + **Artifact Registry**.

## Prerequisites

- Google Cloud account with billing enabled
- [gcloud CLI](https://cloud.google.com/sdk/docs/install) installed
- Python 3.11+ locally (for optional local checks)
- Project ID (example: `my-fieldops-demo`)

## 1. One-time GCP setup

```bash
export PROJECT_ID="your-gcp-project-id"
export REGION="us-central1"

gcloud config set project "$PROJECT_ID"

gcloud services enable \
  run.googleapis.com \
  artifactregistry.googleapis.com \
  cloudbuild.googleapis.com \
  aiplatform.googleapis.com \
  cloudtrace.googleapis.com
```

## 2. Create Artifact Registry repository

```bash
gcloud artifacts repositories create fieldops-agent-fabric \
  --repository-format=docker \
  --location="$REGION" \
  --description="FieldOps Agent Fabric images"
```

## 3. Build and push the container image

From the repo root:

```bash
export IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/fieldops-agent-fabric/api:latest"

gcloud auth configure-docker "${REGION}-docker.pkg.dev" --quiet

gcloud builds submit --tag "$IMAGE"
```

`cloudbuild` uses the repo `Dockerfile`, which installs `.[gcp]` for Vertex support.

## 4. Deploy to Cloud Run

Create a dedicated runtime service account:

```bash
export SA="fieldops-run@${PROJECT_ID}.iam.gserviceaccount.com"

gcloud iam service-accounts create fieldops-run \
  --display-name="FieldOps Cloud Run runtime" || true

gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${SA}" \
  --role="roles/aiplatform.user"

gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${SA}" \
  --role="roles/cloudtrace.agent"
```

Deploy:

```bash
gcloud run deploy fieldops-agent-fabric \
  --image="$IMAGE" \
  --region="$REGION" \
  --platform=managed \
  --allow-unauthenticated \
  --service-account="$SA" \
  --port=8080 \
  --memory=2Gi \
  --cpu=2 \
  --timeout=300 \
  --set-env-vars="LLM_PROVIDER=vertex,GOOGLE_CLOUD_PROJECT=${PROJECT_ID},GOOGLE_CLOUD_REGION=${REGION},VERTEX_MODEL=gemini-2.5-flash,OTEL_EXPORT_GCP=true"
```

Notes:

- `--allow-unauthenticated` is fine for a **portfolio demo**; use IAM or Identity-Aware Proxy for anything real.
- Knowledge base files are baked into the image; RAG index is built on container startup.

## 5. Test the deployment

```bash
export URL=$(gcloud run services describe fieldops-agent-fabric \
  --region="$REGION" --format='value(status.url)')

# Cloud Run reserves /healthz at the edge — use /health after deploy
curl -s "${URL}/health" | jq

curl -s -X POST "${URL}/v1/support" \
  -H 'Content-Type: application/json' \
  -d '{"query":"Customer wants a $2000 refund for duplicate charge","customer_id":"cust-1001"}' | jq
```

Open API docs: `${URL}/docs`

## 6. Optional: Terraform

Terraform in `infra/terraform/` provisions Artifact Registry + Cloud Run. **Push the Docker image first** (steps 2–3), then:

```bash
cd infra/terraform
terraform init
terraform apply -var="project_id=${PROJECT_ID}" -var="region=${REGION}"
```

## 7. Cost control (important for demos)

- Cloud Run scales to zero (`min instances = 0` in Terraform).
- Delete when not interviewing:

```bash
gcloud run services delete fieldops-agent-fabric --region="$REGION" --quiet
```

- Set a [billing budget alert](https://cloud.google.com/billing/docs/how-to/budgets) in the console.

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `Install GCP extras` error | Rebuild image; Dockerfile must use `pip install ".[gcp]"` |
| Vertex permission denied | Grant `roles/aiplatform.user` to the Cloud Run service account |
| Wrong LLM (mock responses) | Set env `LLM_PROVIDER=vertex`, not `FIELDOPS_LLM_PROVIDER` |
| Cold start slow | Expected; Chroma ingest runs on startup |
| 503 timeout | Increase `--timeout`; multi-agent calls can take 30–60s |
