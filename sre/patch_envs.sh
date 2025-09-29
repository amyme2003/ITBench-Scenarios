#!/usr/bin/env bash
set -euo pipefail

NAMESPACE="otel-demo"
INSTANA_AGENT="instana-agent.instana-agent"

# Function to patch or add env in a deployment
patch_env() {
  local deployment=$1
  local name=$2
  local value=$3

  echo "Patching $deployment -> $name=$value"

  # Get the index of the env var in the container
  local index
  index=$(kubectl -n "$NAMESPACE" get deployment "$deployment" -o jsonpath='{.spec.template.spec.containers[0].env}' \
    | jq -r --arg NAME "$name" 'map(.name) | index($NAME)')

  if [[ "$index" == "null" ]]; then
    echo "⚠️  $name not found in $deployment, adding it..."
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

### 1. accounting, ad, fraud-detection, kafka, quote
for dep in accounting ad fraud-detection kafka quote; do
  patch_env "$dep" "OTEL_EXPORTER_OTLP_ENDPOINT" "http://$INSTANA_AGENT:4318"
done

### 2. cart, checkout, currency, frontend, image-provider, load-generator, payment, product-catalog, recommendation, shipping
for dep in cart checkout currency frontend image-provider load-generator payment product-catalog recommendation shipping; do
  patch_env "$dep" "OTEL_EXPORTER_OTLP_ENDPOINT" "http://$INSTANA_AGENT:4317"
done

### 3. email
patch_env "email" "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT" "http://$INSTANA_AGENT:4318/v1/traces"

### 4. flagd
patch_env "flagd" "FLAGD_OTEL_COLLECTOR_URI" "$INSTANA_AGENT:4317"

### 5. frontend
patch_env "frontend" "OTEL_COLLECTOR_HOST" "$INSTANA_AGENT"

### 6. frontend-proxy
patch_env "frontend-proxy" "OTEL_COLLECTOR_HOST" "$INSTANA_AGENT"

### 7. image-provider
patch_env "image-provider" "OTEL_COLLECTOR_HOST" "$INSTANA_AGENT"

echo "✅ All deployments patched successfully."

