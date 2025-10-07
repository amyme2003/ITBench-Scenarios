#!/usr/bin/env bash
# This script patches OpenTelemetry deployments to replace the collector with the Instana agent.
set -euo pipefail

NAMESPACE="otel-demo"
INSTANA_AGENT="instana-agent.instana-agent"

# Function to patch or add env in a deployment's single container
patch_env() {
  local deployment=$1
  local name=$2
  local value=$3

  echo "Patching $deployment -> $name=$value"

  # Get the index of the env var in the first container
  local index
  index=$(kubectl -n "$NAMESPACE" get deployment "$deployment" -o jsonpath='{.spec.template.spec.containers[0].env}' \
    | jq -r --arg NAME "$name" 'map(.name) | index($NAME)')

  if [[ "$index" == "null" ]]; then
    echo ":warning:  $name not found, adding it..."
    kubectl -n "$NAMESPACE" patch deployment "$deployment" \
      --type='json' \
      -p="[
        {
          \"op\": \"add\",
          \"path\": \"/spec/template/spec/containers/0/env/-\",
          \"value\": {\"name\": \"$name\", \"value\": \"$value\"}
        }
      ]"
  else
    kubectl -n "$NAMESPACE" patch deployment "$deployment" \
      --type='json' \
      -p="[
        {
          \"op\": \"replace\",
          \"path\": \"/spec/template/spec/containers/0/env/$index/value\",
          \"value\": \"$value\"
        }
      ]"
  fi
}

# Function to patch env in a specific container of flagd (two containers)
patch_flagd_container_env() {
  local container=$1
  local name=$2
  local value=$3

  echo "Patching flagd container $container -> $name=$value"

  # Get container index
  local c_index
  c_index=$(kubectl -n "$NAMESPACE" get deployment flagd -o jsonpath='{.spec.template.spec.containers[*].name}' \
    | tr ' ' '\n' | grep -n "^$container$" | cut -d: -f1)
  c_index=$((c_index-1)) # convert 1-based to 0-based

  # Get env var index
  local e_index
  e_index=$(kubectl -n "$NAMESPACE" get deployment flagd -o json \
    | jq -r --arg CONTAINER "$container" --arg NAME "$name" '
        .spec.template.spec.containers
        | map(select(.name==$CONTAINER))[0].env
        | map(.name) | index($NAME)
    ')

  if [[ "$e_index" == "null" ]]; then
    echo "$name not found in $container, adding it..."
    kubectl -n "$NAMESPACE" patch deployment flagd \
      --type='json' \
      -p="[
        {
          \"op\": \"add\",
          \"path\": \"/spec/template/spec/containers/$c_index/env/-\",
          \"value\": {\"name\": \"$name\", \"value\": \"$value\"}
        }
      ]"
  else
    kubectl -n "$NAMESPACE" patch deployment flagd \
      --type='json' \
      -p="[
        {
          \"op\": \"replace\",
          \"path\": \"/spec/template/spec/containers/$c_index/env/$e_index/value\",
          \"value\": \"$value\"
        }
      ]"
  fi
}

### Patch all deployments

# 1. accounting, ad, fraud-detection, email, kafka, quote
for dep in accounting ad fraud-detection email kafka quote; do
  patch_env "$dep" "OTEL_EXPORTER_OTLP_ENDPOINT" "http://$INSTANA_AGENT:4318"
done

# 2. cart, checkout, currency, frontend, load-generator, payment, product-catalog, recommendation, shipping
for dep in cart checkout currency frontend load-generator payment product-catalog recommendation shipping; do
  patch_env "$dep" "OTEL_EXPORTER_OTLP_ENDPOINT" "http://$INSTANA_AGENT:4317"
done

# 4. flagd (two containers)
patch_flagd_container_env "flagd" "FLAGD_OTEL_COLLECTOR_URI" "$INSTANA_AGENT:4317"
patch_flagd_container_env "flagd-ui" "OTEL_EXPORTER_OTLP_ENDPOINT" "http://$INSTANA_AGENT:4318"

# 5. frontend
patch_env "frontend" "OTEL_COLLECTOR_HOST" "$INSTANA_AGENT"
patch_env "frontend" "PUBLIC_OTEL_EXPORTER_OTLP_TRACES_ENDPOINT" "http://$INSTANA_AGENT:4317/v1/traces"
 
# 6. frontend-proxy
patch_env "frontend-proxy" "OTEL_COLLECTOR_HOST" "$INSTANA_AGENT"

# 7. image-provider
patch_env "image-provider" "OTEL_COLLECTOR_HOST" "$INSTANA_AGENT"

# Restart all deployments to ensure changes take effect
echo "Restarting all deployments to apply changes..."
kubectl -n "$NAMESPACE" rollout restart deployment

# Wait for rollouts to complete
echo "Waiting for rollouts to complete..."
kubectl -n "$NAMESPACE" rollout status deployment --all --timeout=300s

echo "All deployments patched and restarted successfully."


