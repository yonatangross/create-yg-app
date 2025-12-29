# Kubernetes 1.31+ Deployment

K8s deployment patterns and best practices (December 2025).

## Basic Deployment (1.31+)

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: api-backend
  labels:
    app: api-backend
    version: v1.2.0
    tier: backend
spec:
  replicas: 3
  revisionHistoryLimit: 10
  selector:
    matchLabels:
      app: api-backend
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1
      maxUnavailable: 0  # Zero downtime
  template:
    metadata:
      labels:
        app: api-backend
        version: v1.2.0
      annotations:
        prometheus.io/scrape: "true"
        prometheus.io/port: "8000"
        prometheus.io/path: "/metrics"
    spec:
      serviceAccountName: api-backend
      securityContext:
        runAsNonRoot: true
        runAsUser: 1001
        fsGroup: 1001
        seccompProfile:
          type: RuntimeDefault
      containers:
      - name: api
        image: ghcr.io/myorg/api-backend:v1.2.0
        imagePullPolicy: IfNotPresent
        ports:
        - name: http
          containerPort: 8000
          protocol: TCP
        env:
        - name: PORT
          value: "8000"
        - name: LOG_LEVEL
          value: "info"
        envFrom:
        - secretRef:
            name: api-secrets
        - configMapRef:
            name: api-config
        resources:
          requests:
            memory: "256Mi"
            cpu: "250m"
            ephemeral-storage: "1Gi"
          limits:
            memory: "512Mi"
            cpu: "500m"
            ephemeral-storage: "2Gi"
        securityContext:
          allowPrivilegeEscalation: false
          readOnlyRootFilesystem: true
          runAsNonRoot: true
          runAsUser: 1001
          capabilities:
            drop: ["ALL"]
        volumeMounts:
        - name: tmp
          mountPath: /tmp
        - name: cache
          mountPath: /app/cache
      volumes:
      - name: tmp
        emptyDir: {}
      - name: cache
        emptyDir:
          sizeLimit: 500Mi
      affinity:
        podAntiAffinity:
          preferredDuringSchedulingIgnoredDuringExecution:
          - weight: 100
            podAffinityTerm:
              labelSelector:
                matchLabels:
                  app: api-backend
              topologyKey: kubernetes.io/hostname
```

## Health Checks (Kubernetes 1.31+)

```yaml
livenessProbe:
  httpGet:
    path: /health
    port: http
    scheme: HTTP
  initialDelaySeconds: 30
  periodSeconds: 10
  timeoutSeconds: 3
  successThreshold: 1
  failureThreshold: 3

readinessProbe:
  httpGet:
    path: /ready
    port: http
    scheme: HTTP
  initialDelaySeconds: 5
  periodSeconds: 5
  timeoutSeconds: 3
  successThreshold: 1
  failureThreshold: 2

startupProbe:
  httpGet:
    path: /startup
    port: http
  initialDelaySeconds: 0
  periodSeconds: 5
  timeoutSeconds: 3
  successThreshold: 1
  failureThreshold: 30  # 150s max startup time
```

## HorizontalPodAutoscaler (HPA)

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: api-backend-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: api-backend
  minReplicas: 3
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
  behavior:
    scaleDown:
      stabilizationWindowSeconds: 300
      policies:
      - type: Percent
        value: 50
        periodSeconds: 60
    scaleUp:
      stabilizationWindowSeconds: 0
      policies:
      - type: Percent
        value: 100
        periodSeconds: 30
      - type: Pods
        value: 2
        periodSeconds: 30
      selectPolicy: Max
```

## Best Practices (2025)

1. **Set resource requests AND limits** - including ephemeral-storage
2. **Use all three probe types** - startup, liveness, readiness
3. **Security context hardening** - runAsNonRoot, readOnlyRootFilesystem, drop ALL capabilities
4. **Seccomp profiles** - type: RuntimeDefault
5. **HPA with custom metrics** - autoscaling/v2 with CPU + memory
6. **PodDisruptionBudget** - ensure availability during node maintenance
7. **Pod anti-affinity** - spread pods across nodes
8. **External Secrets Operator** - sync secrets from cloud providers

See modern manifests in `templates/k8s-manifests-2025.yaml`.
