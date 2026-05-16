# Minimal GCP deployment sketch for Cloud Run + Artifact Registry.
# Extend with VPC-SC, Secret Manager, and Vertex AI endpoints for production narratives.

terraform {
  required_version = ">= 1.5.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

resource "google_artifact_registry_repository" "fieldops" {
  location      = var.region
  repository_id = "fieldops-agent-fabric"
  format        = "DOCKER"
}

resource "google_cloud_run_v2_service" "api" {
  name     = "fieldops-agent-fabric"
  location = var.region

  template {
    containers {
      image = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.fieldops.repository_id}/api:latest"
      ports {
        container_port = 8080
      }
      env {
        name  = "LLM_PROVIDER"
        value = "vertex"
      }
      env {
        name  = "GOOGLE_CLOUD_PROJECT"
        value = var.project_id
      }
      env {
        name  = "GOOGLE_CLOUD_REGION"
        value = var.region
      }
      env {
        name  = "OTEL_EXPORT_GCP"
        value = "true"
      }
    }
    scaling {
      min_instance_count = 0
      max_instance_count = 10
    }
  }

  ingress = "INGRESS_TRAFFIC_ALL"
}

output "cloud_run_uri" {
  value = google_cloud_run_v2_service.api.uri
}
