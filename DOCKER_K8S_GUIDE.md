# Movie Application — Docker & Kubernetes Complete Guide

This document explains how the **Movie Application** (Angular frontend + Django backend + MySQL database) is containerized using **Docker** and orchestrated using **Kubernetes (K8s)** with **Minikube**.

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Key Terminology](#2-key-terminology)
3. [Docker — Concepts & Implementation](#3-docker--concepts--implementation)
   - 3.1 [What is Docker?](#31-what-is-docker)
   - 3.2 [Backend Dockerfile](#32-backend-dockerfile-django)
   - 3.3 [Frontend Dockerfile](#33-frontend-dockerfile-angular)
   - 3.4 [.dockerignore](#34-dockerignore)
   - 3.5 [Docker Commands Reference](#35-docker-commands-reference)
4. [Kubernetes — Concepts & Implementation](#4-kubernetes--concepts--implementation)
   - 4.1 [What is Kubernetes?](#41-what-is-kubernetes)
   - 4.2 [What is Minikube?](#42-what-is-minikube)
   - 4.3 [YAML File Structure](#43-yaml-file-structure)
   - 4.4 [MySQL Database Pod](#44-mysql-database-pod)
   - 4.5 [Backend (Django) Pod](#45-backend-django-pod)
   - 4.6 [Frontend (Angular) Pod](#46-frontend-angular-pod)
   - 4.7 [Services — Networking Between Pods](#47-services--networking-between-pods)
   - 4.8 [Secrets — Storing Sensitive Data](#48-secrets--storing-sensitive-data)
   - 4.9 [PersistentVolumeClaim — Data Persistence](#49-persistentvolumeclaim--data-persistence)
   - 4.10 [Init Containers](#410-init-containers)
   - 4.11 [Health Checks (Probes)](#411-health-checks-probes)
5. [How Frontend, Backend & Database Connect](#5-how-frontend-backend--database-connect)
6. [Django Configuration for Multi-Environment](#6-django-configuration-for-multi-environment)
7. [Complete Deployment Steps](#7-complete-deployment-steps)
8. [Useful Commands](#8-useful-commands)
9. [Common Issues & Fixes](#9-common-issues--fixes)
10. [File Structure Reference](#10-file-structure-reference)

---

## 1. Architecture Overview

The application follows a **3-tier architecture** with each tier running as a separate Kubernetes pod:

```
┌─────────────────────────────────────────────────────────────────────┐
│                        KUBERNETES CLUSTER (Minikube)                │
│                                                                     │
│  ┌──────────────────┐    ┌──────────────────┐    ┌───────────────┐ │
│  │   FRONTEND POD   │    │   BACKEND POD    │    │ DATABASE POD  │ │
│  │                  │    │   (×2 replicas)  │    │               │ │
│  │  Angular App     │───▶│  Django + DRF    │───▶│  MySQL 8.0    │ │
│  │  served by Nginx │    │  served by       │    │               │ │
│  │                  │    │  Gunicorn        │    │  Data stored  │ │
│  │  Port: 80        │    │  Port: 8000      │    │  on PVC       │ │
│  └──────┬───────────┘    └──────┬───────────┘    └───────┬───────┘ │
│         │                       │                        │         │
│  ┌──────┴───────────┐    ┌──────┴───────────┐    ┌───────┴───────┐ │
│  │  LoadBalancer     │    │  NodePort        │    │  ClusterIP    │ │
│  │  Service          │    │  Service         │    │  Service      │ │
│  │  :30010           │    │  :30080          │    │  :3306        │ │
│  └──────────────────┘    └──────────────────┘    └───────────────┘ │
│         │                       │                                   │
└─────────┼───────────────────────┼───────────────────────────────────┘
          │                       │
          ▼                       ▼
   User Browser             Direct API Access
   http://IP:30010           http://IP:30080
```

**Request Flow:**
1. User opens `http://<minikube-ip>:30010` in browser
2. Nginx serves the Angular SPA (HTML/JS/CSS)
3. Angular makes API calls to `/api/*` (relative URL)
4. Nginx proxies `/api/*` requests to `movie-app-service:80` (backend)
5. Django processes the request, queries MySQL via `mysql-service:3306`
6. Response travels back: MySQL → Django → Nginx → Browser

---

## 2. Key Terminology

### Docker Terms

| Term | What It Is | Analogy |
|------|-----------|---------|
| **Image** | A read-only template containing your app, its dependencies, and instructions to run it. Created from a `Dockerfile`. | A recipe/blueprint |
| **Container** | A running instance of an image. Isolated, lightweight, and ephemeral. | A dish made from the recipe |
| **Dockerfile** | A text file with instructions to build a Docker image. Each instruction creates a layer. | Step-by-step recipe |
| **Layer** | Each instruction in a Dockerfile creates an immutable layer. Layers are cached for faster rebuilds. | Ingredients added one by one |
| **Registry** | A storage for Docker images (e.g., Docker Hub, AWS ECR). | A cookbook library |
| **Volume** | Persistent storage that exists outside the container's filesystem. Survives container restarts. | An external hard drive |
| **Multi-stage Build** | A Dockerfile with multiple `FROM` instructions. Used to keep final images small. | Cook in a big kitchen, serve on a small plate |
| **.dockerignore** | Lists files/directories to exclude when copying files into the image. | A "do not pack" list |

### Kubernetes Terms

| Term | What It Is | Analogy |
|------|-----------|---------|
| **Cluster** | A set of machines (nodes) that run containerized applications managed by Kubernetes. | A fleet of ships |
| **Node** | A single machine (physical or virtual) in the cluster. Minikube creates one node. | One ship in the fleet |
| **Pod** | The smallest deployable unit in K8s. Contains one or more containers that share storage and network. | A cabin on the ship |
| **Deployment** | Manages pods — ensures the desired number of replicas are running, handles updates and rollbacks. | A crew manager |
| **Service** | A stable network endpoint to access pods. Pods get random IPs; services provide a fixed address. | A reception desk |
| **Secret** | Stores sensitive data (passwords, API keys) in base64 encoding. Referenced by pods as env vars. | A locked safe |
| **PersistentVolumeClaim (PVC)** | A request for storage. K8s provisions disk space that survives pod restarts. | Renting a storage unit |
| **Init Container** | A container that runs to completion BEFORE the main container starts. Used for setup tasks. | Opening the restaurant before guests arrive |
| **ConfigMap** | Stores non-sensitive configuration data as key-value pairs. | A settings file |
| **Namespace** | A virtual cluster within a cluster. Used to isolate resources. Default namespace is used here. | Departments in a company |
| **Label** | Key-value tags attached to resources. Used by selectors to identify groups of resources. | Name tags |
| **Selector** | A query that matches resources by their labels. | "Find everyone wearing the blue tag" |
| **Replica** | A copy of a pod. More replicas = more capacity and fault tolerance. | Backup crew members |

### Service Types

| Type | Accessible From | Use Case |
|------|----------------|----------|
| **ClusterIP** | Only within the cluster | Internal services (databases) |
| **NodePort** | Outside the cluster via `<NodeIP>:<NodePort>` (range: 30000-32767) | Development/testing |
| **LoadBalancer** | Outside via cloud provider's load balancer; in Minikube, works like NodePort | Production (cloud) |
| **Ingress** | Outside via HTTP/HTTPS routing rules | Production (path-based routing) |

### Networking Concepts

| Concept | Explanation |
|---------|------------|
| **containerPort** | The port your application listens on INSIDE the container |
| **targetPort** | The port on the pod that the Service forwards traffic to (usually = containerPort) |
| **port** | The port the Service listens on (used for internal cluster communication) |
| **nodePort** | The port exposed on the node's IP (accessible from outside the cluster) |
| **DNS Resolution** | K8s creates DNS entries for Services. Pod can reach `mysql-service` by name instead of IP |

```
External Request → nodePort (30080) → Service port (80) → targetPort (8000) → Container
```

---

## 3. Docker — Concepts & Implementation

### 3.1 What is Docker?

Docker packages your application with all its dependencies into a **container** — a lightweight, standalone, executable unit. This ensures the app runs the same way on every machine, whether it's your laptop, a teammate's machine, or a production server.

**Without Docker:** "But it works on my machine!"
**With Docker:** "It works in the container, and the container works everywhere."

### 3.2 Backend Dockerfile (Django)

**File:** `movie/Dockerfile`

```dockerfile
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /app/data

RUN python manage.py collectstatic --noinput || true

EXPOSE 8000

CMD ["gunicorn", "movie.wsgi:application", "--bind", "0.0.0.0:8000"]
```

**Line-by-line explanation:**

| Line | Code | What It Does |
|------|------|-------------|
| 1 | `FROM python:3.12-slim` | **Base image.** Starts from an official Python 3.12 image. `slim` variant is smaller (~150MB vs ~900MB for full). Contains Python + pip, nothing extra. |
| 3 | `ENV PYTHONDONTWRITEBYTECODE=1` | Prevents Python from creating `.pyc` bytecode cache files. Keeps the image clean. |
| 4 | `ENV PYTHONUNBUFFERED=1` | Forces Python to output logs immediately (no buffering). Critical for seeing logs in `kubectl logs` and `docker logs` in real-time. |
| 6 | `WORKDIR /app` | Sets `/app` as the working directory inside the container. All subsequent commands run from here. If it doesn't exist, Docker creates it. |
| 8 | `COPY requirements.txt .` | Copies ONLY `requirements.txt` first. This is a **caching optimization** — if requirements haven't changed, Docker reuses the cached pip install layer. |
| 9 | `RUN pip install --no-cache-dir -r requirements.txt` | Installs Python dependencies. `--no-cache-dir` avoids storing pip's download cache, keeping the image smaller. |
| 11 | `COPY . .` | Copies the entire project into `/app`. Done AFTER pip install so code changes don't invalidate the pip cache layer. |
| 13 | `RUN mkdir -p /app/data` | Creates a data directory for SQLite (used in local/Docker development without K8s). |
| 15 | `RUN python manage.py collectstatic --noinput \|\| true` | Collects Django static files (CSS/JS for admin panel). `\|\| true` ensures the build doesn't fail if this command errors. |
| 17 | `EXPOSE 8000` | Documents that the container listens on port 8000. This is informational — it doesn't actually publish the port. |
| 19 | `CMD [...]` | **Default command** when the container starts. Runs Gunicorn (a production WSGI server) serving the Django app on all interfaces (`0.0.0.0`) port 8000. |

**Why Gunicorn instead of `python manage.py runserver`?**

| Feature | `runserver` (dev) | Gunicorn (production) |
|---------|------------------|----------------------|
| Concurrent requests | Single-threaded | Multiple workers |
| Auto-reload on code changes | ✅ Yes | ❌ No |
| Static file serving | ✅ Built-in | ❌ Needs Nginx |
| Performance | Slow | Fast |
| Security | Not hardened | Production-ready |
| Django's recommendation | Dev only | Production |

**Why `requirements.txt` is copied before `COPY . .`?**

This leverages Docker's **layer caching**:

```
Step 1: COPY requirements.txt .     ← Rarely changes
Step 2: RUN pip install ...          ← Cached if requirements.txt unchanged (saves 30+ seconds)
Step 3: COPY . .                     ← Changes often (your code)
```

If you did `COPY . .` first, ANY code change would invalidate the pip install cache, making every build reinstall all packages.

### 3.3 Frontend Dockerfile (Angular)

**File:** `project/movie/Dockerfile`

```dockerfile
# Stage 0, "build-stage", based on Node.js, to build and compile the frontend
FROM node:20.11.0 as build-stage
WORKDIR /app
COPY package*.json /app/
RUN npm install
COPY ./ /app/
ARG configuration=production
RUN npm run build -- --output-path=./dist/out --configuration $configuration
RUN ls -la /app/dist/out

# Stage 1, based on Nginx, to have only the compiled app, ready for production with Nginx
FROM nginx:1.15
COPY --from=build-stage /app/dist/out/browser /usr/share/nginx/html
COPY ./nginx-custom.conf /etc/nginx/conf.d/default.conf
```

This is a **multi-stage build** — one of Docker's most powerful features.

**Stage 0 — Build Stage:**

| Line | Code | What It Does |
|------|------|-------------|
| 2 | `FROM node:20.11.0 as build-stage` | Uses Node.js as base. Named `build-stage` for reference later. This image is ~1GB but is temporary. |
| 3 | `WORKDIR /app` | Working directory inside the build container. |
| 4 | `COPY package*.json /app/` | Copies `package.json` and `package-lock.json` first (caching optimization, same principle as backend). |
| 5 | `RUN npm install` | Installs node_modules. Cached if package.json hasn't changed. |
| 6 | `COPY ./ /app/` | Copies all source code. |
| 7 | `ARG configuration=production` | Build argument with default value. `ARG` is available only during build, not at runtime. |
| 8 | `RUN npm run build ...` | Compiles Angular TypeScript → optimized JavaScript/HTML/CSS bundle. |

**Stage 1 — Production Stage:**

| Line | Code | What It Does |
|------|------|-------------|
| 12 | `FROM nginx:1.15` | Starts a NEW image from Nginx. The Node.js image is discarded. |
| 14 | `COPY --from=build-stage ...` | Copies ONLY the compiled files from Stage 0 into Nginx's serving directory. |
| 16 | `COPY ./nginx-custom.conf ...` | Replaces Nginx's default config with our custom one. |

**Why multi-stage?**

| | Single Stage | Multi-Stage |
|---|---|---|
| Final image contains | Node.js + node_modules + source code + compiled files | Only Nginx + compiled files |
| Image size | ~1.2 GB | ~100 MB |
| Security | Exposed source code, build tools | Only production artifacts |

**Nginx Configuration (`nginx-custom.conf`):**

```nginx
map $sent_http_content_type $expires {
    default                    off;
    text/html                  epoch;    # Always revalidate HTML
    text/css                   max;      # Cache CSS forever
    application/json           off;      # Never cache API responses
    application/javascript     max;      # Cache JS forever
    ~image/                    max;      # Cache images forever
}

server {
  listen 80;

  # Proxy API requests to Django backend
  location /api/ {
      proxy_pass http://movie-app-service:80;
      proxy_set_header Host $host;
      proxy_set_header X-Real-IP $remote_addr;
      proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
  }

  # Serve Angular SPA
  location / {
      root /usr/share/nginx/html;
      index index.html index.htm;
      try_files $uri $uri/ /index.html =404;
  }

  expires $expires;
  gzip on;
}
```

| Directive | Purpose |
|-----------|---------|
| `location /api/` | Any request starting with `/api/` is forwarded to the backend K8s service (`movie-app-service`). |
| `proxy_pass http://movie-app-service:80` | Kubernetes DNS resolves `movie-app-service` to the backend pods. |
| `proxy_set_header` | Passes original client info (IP, host) to Django so it knows the real client. |
| `try_files $uri $uri/ /index.html =404` | SPA routing — if the URL doesn't match a file, serve `index.html` (Angular handles the route client-side). |
| `application/json off` | **Critical:** Don't cache API responses. We had a bug where the browser cached an empty movie list forever. |

### 3.4 .dockerignore

**File:** `movie/.dockerignore`

```
__pycache__
*.pyc
*.pyo
.git
.gitignore
db.sqlite3
.env
*.md
ini/
```

Works exactly like `.gitignore` but for Docker. When `COPY . .` runs, these files/directories are excluded.

**Why exclude these?**

| Pattern | Reason |
|---------|--------|
| `__pycache__`, `*.pyc`, `*.pyo` | Compiled Python bytecode — regenerated at runtime, wastes space |
| `.git` | Git history can be huge, not needed in production |
| `db.sqlite3` | Local database file — container should start fresh or use MySQL |
| `.env` | Environment secrets — should NEVER be baked into an image |
| `*.md` | Documentation — not needed at runtime |
| `ini/` | Initial/alternate requirements — using root `requirements.txt` |

---

## 4. Kubernetes — Concepts & Implementation

### 4.1 What is Kubernetes?

Kubernetes (K8s) is a **container orchestration platform**. While Docker runs individual containers, Kubernetes manages fleets of containers:

| Docker Does | Kubernetes Does |
|------------|----------------|
| Build and run one container | Run multiple containers across multiple machines |
| — | Restart crashed containers automatically |
| — | Scale up/down based on load |
| — | Route traffic between containers |
| — | Manage secrets and configuration |
| — | Roll out updates with zero downtime |
| — | Persist data across container restarts |

### 4.2 What is Minikube?

Minikube creates a **single-node Kubernetes cluster** on your local machine. It runs inside a Docker container (or VM) and provides a full K8s environment for development.

**Important concept: `eval $(minikube docker-env)`**

Minikube has its own Docker daemon, separate from your host's Docker. When you build images, they exist only in your host's Docker. This command redirects your terminal's Docker commands to Minikube's Docker, so images are built inside the cluster and available to pods.

```
Host Docker (your Mac)     ←→     Minikube Docker (inside cluster)
  movie-app:latest                   movie-app:latest (needed here!)
```

Without `eval $(minikube docker-env)`, pods get `ErrImageNeverPull` because the image exists on your Mac but not inside Minikube.

### 4.3 YAML File Structure

Every K8s YAML file has these required fields:

```yaml
apiVersion: apps/v1    # Which K8s API version to use
kind: Deployment       # What type of resource (Deployment, Service, Secret, etc.)
metadata:              # Resource identification
  name: my-app         #   Unique name within the namespace
  labels:              #   Key-value tags for organizing
    app: my-app
spec:                  # The desired state — what you want K8s to create
  ...
```

**`apiVersion` values we use:**

| apiVersion | Used For |
|------------|----------|
| `apps/v1` | Deployments, ReplicaSets, StatefulSets |
| `v1` | Services, Secrets, PersistentVolumeClaims, Pods |

---

### 4.4 MySQL Database Pod

#### 4.4.1 Secret (`mysql-secret.yaml`)

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: mysql-secret
type: Opaque
stringData:
  MYSQL_ROOT_PASSWORD: rootpass123
  MYSQL_DATABASE: moviedb
  MYSQL_USER: movieuser
  MYSQL_PASSWORD: moviepass123
```

| Field | Purpose |
|-------|---------|
| `kind: Secret` | Tells K8s this is a Secret resource |
| `type: Opaque` | Generic secret type (as opposed to TLS certs, Docker registry creds, etc.) |
| `stringData` | Human-readable key-value pairs. K8s automatically base64-encodes them. Alternative: `data` (requires you to base64-encode manually) |
| `MYSQL_ROOT_PASSWORD` | MySQL's root superuser password |
| `MYSQL_DATABASE` | The database MySQL creates on first startup |
| `MYSQL_USER` / `MYSQL_PASSWORD` | The user/password Django uses to connect |

**How secrets are consumed:** Pods reference them as environment variables via `secretKeyRef` or `envFrom`.

**Security note:** In production, use external secret managers (HashiCorp Vault, AWS Secrets Manager) instead of storing secrets in YAML files.

#### 4.4.2 PersistentVolumeClaim (`mysql-pvc.yaml`)

```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: mysql-pvc
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 1Gi
```

| Field | Purpose |
|-------|---------|
| `kind: PersistentVolumeClaim` | A request for persistent storage |
| `accessModes: ReadWriteOnce` | Can be mounted as read-write by a **single** node. Other options: `ReadWriteMany` (multiple nodes), `ReadOnlyMany` |
| `storage: 1Gi` | Requesting 1 gigabyte of disk space |

**Why is this needed?**

Without a PVC, MySQL stores data inside the container's filesystem. When the pod restarts, all data is lost. A PVC provides a disk that exists independently of the pod.

```
Without PVC:  Pod restarts → Data GONE
With PVC:     Pod restarts → Data SAFE (PVC survives)
```

**PVC lifecycle:**
1. You create a PVC (a "request" for storage)
2. K8s finds or creates a PersistentVolume (PV) that satisfies the request
3. The PVC is "bound" to the PV
4. Pod mounts the PVC at a specific path
5. Pod can restart, be deleted, recreated — the PV keeps the data

#### 4.4.3 Deployment (`mysql-deployment.yaml`)

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: mysql
  labels:
    app: mysql
spec:
  replicas: 1
  selector:
    matchLabels:
      app: mysql
  template:
    metadata:
      labels:
        app: mysql
    spec:
      containers:
        - name: mysql
          image: mysql:8.0
          ports:
            - containerPort: 3306
          envFrom:
            - secretRef:
                name: mysql-secret
          volumeMounts:
            - mountPath: /var/lib/mysql
              name: mysql-storage
      volumes:
        - name: mysql-storage
          persistentVolumeClaim:
            claimName: mysql-pvc
```

**Detailed breakdown:**

| Section | Field | Purpose |
|---------|-------|---------|
| `spec` | `replicas: 1` | Run exactly 1 MySQL pod. Databases typically use 1 replica (scaling databases requires special setup like StatefulSets). |
| `spec` | `selector.matchLabels` | "This deployment manages pods with label `app: mysql`." Must match `template.metadata.labels`. |
| `template` | — | The **pod template**. Every pod created by this deployment follows this template. |
| `template.metadata` | `labels: app: mysql` | Tags every pod so the Service and Deployment can find them. |
| `containers` | `image: mysql:8.0` | Uses the official MySQL 8.0 image from Docker Hub. Unlike our app images, this is pulled from the internet (no `imagePullPolicy: Never`). |
| `containers` | `containerPort: 3306` | MySQL listens on port 3306 (MySQL's default port). |
| `containers` | `envFrom.secretRef` | Injects ALL key-value pairs from `mysql-secret` as environment variables. MySQL's official Docker image reads `MYSQL_ROOT_PASSWORD`, `MYSQL_DATABASE`, etc. to auto-configure on first boot. |
| `volumeMounts` | `mountPath: /var/lib/mysql` | Mounts persistent storage at MySQL's data directory. MySQL stores all databases, tables, and data here. |
| `volumes` | `persistentVolumeClaim` | Links the volume name (`mysql-storage`) to the actual PVC (`mysql-pvc`). |

**`envFrom` vs `env`:**

```yaml
# envFrom — imports ALL keys from the secret
envFrom:
  - secretRef:
      name: mysql-secret
# Result: MYSQL_ROOT_PASSWORD=rootpass123, MYSQL_DATABASE=moviedb, etc.

# env — imports specific keys, can rename them
env:
  - name: DB_NAME           # Variable name in the container
    valueFrom:
      secretKeyRef:
        name: mysql-secret
        key: MYSQL_DATABASE  # Key in the secret
# Result: DB_NAME=moviedb
```

#### 4.4.4 Service (`mysql-service.yaml`)

```yaml
apiVersion: v1
kind: Service
metadata:
  name: mysql-service
spec:
  selector:
    app: mysql
  ports:
    - protocol: TCP
      port: 3306
      targetPort: 3306
  type: ClusterIP
```

| Field | Purpose |
|-------|---------|
| `selector: app: mysql` | Routes traffic to pods with label `app: mysql` |
| `port: 3306` | The port the Service listens on (other pods connect to `mysql-service:3306`) |
| `targetPort: 3306` | The port on the MySQL pod to forward traffic to |
| `type: ClusterIP` | Only accessible from within the cluster. Django pods can reach it, but you can't access it from your browser. This is intentional — databases should never be exposed publicly. |

**DNS Magic:** When you create a Service named `mysql-service`, Kubernetes automatically creates a DNS entry. Any pod in the cluster can connect to `mysql-service:3306` by name. No IP addresses needed.

---

### 4.5 Backend (Django) Pod

#### 4.5.1 Deployment (`deployment.yaml`)

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: movie-app
  labels:
    app: movie-app
spec:
  replicas: 2
  selector:
    matchLabels:
      app: movie-app
  template:
    metadata:
      labels:
        app: movie-app
    spec:
      initContainers:
        - name: run-migrations
          image: movie-app:latest
          imagePullPolicy: Never
          command: ["python", "manage.py", "migrate"]
          env:
            - name: DB_ENGINE
              value: "django.db.backends.mysql"
            - name: DB_HOST
              value: "mysql-service"
            - name: DB_PORT
              value: "3306"
            - name: DB_NAME
              valueFrom:
                secretKeyRef:
                  name: mysql-secret
                  key: MYSQL_DATABASE
            - name: DB_USER
              valueFrom:
                secretKeyRef:
                  name: mysql-secret
                  key: MYSQL_USER
            - name: DB_PASSWORD
              valueFrom:
                secretKeyRef:
                  name: mysql-secret
                  key: MYSQL_PASSWORD
      containers:
        - name: movie-app
          image: movie-app:latest
          imagePullPolicy: Never
          ports:
            - containerPort: 8000
          env:
            - name: DJANGO_SETTINGS_MODULE
              value: "movie.settings"
            - name: ALLOWED_HOSTS
              value: "*"
            - name: DB_ENGINE
              value: "django.db.backends.mysql"
            - name: DB_HOST
              value: "mysql-service"
            - name: DB_PORT
              value: "3306"
            - name: DB_NAME
              valueFrom:
                secretKeyRef:
                  name: mysql-secret
                  key: MYSQL_DATABASE
            - name: DB_USER
              valueFrom:
                secretKeyRef:
                  name: mysql-secret
                  key: MYSQL_USER
            - name: DB_PASSWORD
              valueFrom:
                secretKeyRef:
                  name: mysql-secret
                  key: MYSQL_PASSWORD
            - name: CORS_ALLOW_ALL_ORIGINS
              value: "True"
          readinessProbe:
            httpGet:
              path: /admin/
              port: 8000
            initialDelaySeconds: 10
            periodSeconds: 10
          livenessProbe:
            httpGet:
              path: /admin/
              port: 8000
            initialDelaySeconds: 15
            periodSeconds: 30
```

**Key sections explained:**

**`replicas: 2`** — Runs 2 identical Django pods. Benefits:
- If one pod crashes, the other handles requests (high availability)
- Traffic is distributed between both pods (load balancing)
- The Service automatically routes to healthy pods

**`imagePullPolicy: Never`** — Tells K8s: "Don't try to pull this image from Docker Hub. It's already available locally." Required when using locally-built images with Minikube.

### 4.10 Init Containers

```yaml
initContainers:
  - name: run-migrations
    image: movie-app:latest
    command: ["python", "manage.py", "migrate"]
    env: [...]
```

**What are init containers?**

Init containers run **before** the main container starts. They must complete successfully or the pod won't start.

**Lifecycle:**

```
Pod Created
    │
    ▼
┌─────────────────────┐
│  Init Container:     │
│  run-migrations      │──── Runs "python manage.py migrate"
│                      │     Creates/updates database tables
└──────────┬──────────┘
           │ (exits successfully)
           ▼
┌─────────────────────┐
│  Main Container:     │
│  movie-app           │──── Runs Gunicorn (serves requests)
│                      │     Only starts after init container succeeds
└─────────────────────┘
```

**Why not run migrate in the Dockerfile?** Because at build time, the database doesn't exist yet. MySQL is a separate pod. Migrations need to run at deploy time when MySQL is available.

**Why not run migrate in CMD?** With `replicas: 2`, both pods would run migrations simultaneously. Init containers also provide clear separation of concerns: setup (migrate) vs. serving (gunicorn).

### 4.11 Health Checks (Probes)

```yaml
readinessProbe:
  httpGet:
    path: /admin/
    port: 8000
  initialDelaySeconds: 10
  periodSeconds: 10

livenessProbe:
  httpGet:
    path: /admin/
    port: 8000
  initialDelaySeconds: 15
  periodSeconds: 30
```

| Probe | Question It Answers | What Happens If It Fails |
|-------|--------------------|-----------------------|
| **readinessProbe** | "Is this pod ready to receive traffic?" | Pod is removed from the Service's endpoint list. No traffic is routed to it. Pod keeps running. |
| **livenessProbe** | "Is this pod still alive?" | K8s kills and restarts the pod. |

| Parameter | Meaning |
|-----------|---------|
| `httpGet.path` | K8s makes a GET request to this URL. If response is 200-399, the check passes. |
| `initialDelaySeconds` | Wait this many seconds after the container starts before running the first check. Gives the app time to boot. |
| `periodSeconds` | Run the check every N seconds. |

**Real-world scenario:**
1. Pod starts, Gunicorn takes 5 seconds to boot
2. At 10 seconds: readinessProbe fires, gets 200 from `/admin/` → pod added to Service, receives traffic
3. At 15 seconds: livenessProbe fires, gets 200 → pod is alive
4. If Django crashes and `/admin/` returns 500 → livenessProbe fails 3 times → K8s restarts the pod

**Environment variables explained:**

| Variable | Value | Purpose |
|----------|-------|---------|
| `DJANGO_SETTINGS_MODULE` | `movie.settings` | Tells Django which settings file to use |
| `ALLOWED_HOSTS` | `*` | Django accepts requests from any hostname (in production, restrict to your domain) |
| `DB_ENGINE` | `django.db.backends.mysql` | Use MySQL driver instead of default SQLite |
| `DB_HOST` | `mysql-service` | K8s DNS name of the MySQL Service |
| `DB_PORT` | `3306` | MySQL's port |
| `DB_NAME` | (from Secret) | Database name: `moviedb` |
| `DB_USER` | (from Secret) | Database user: `movieuser` |
| `DB_PASSWORD` | (from Secret) | Database password: `moviepass123` |
| `CORS_ALLOW_ALL_ORIGINS` | `True` | Allow cross-origin requests from the frontend |

#### 4.5.2 Service (`service.yaml`)

```yaml
apiVersion: v1
kind: Service
metadata:
  name: movie-app-service
spec:
  type: NodePort
  selector:
    app: movie-app
  ports:
    - protocol: TCP
      port: 80
      targetPort: 8000
      nodePort: 30080
```

| Field | Value | Purpose |
|-------|-------|---------|
| `type: NodePort` | Exposes the service on a static port on each node. Accessible from outside the cluster at `<NodeIP>:30080`. |
| `port: 80` | Internal cluster port. Other pods (like Nginx) connect to `movie-app-service:80`. |
| `targetPort: 8000` | Forwards to Gunicorn's port inside the Django container. |
| `nodePort: 30080` | External port. You access the backend directly at `http://<minikube-ip>:30080`. |

**Port mapping flow:**

```
Browser/Nginx → :30080 (nodePort) → :80 (service port) → :8000 (container/Gunicorn)
```

**Why does Nginx use `movie-app-service:80` and not `:8000`?**
Because the Service listens on port 80 and internally routes to 8000. Consumers of a Service use the Service's `port`, not the container's `targetPort`.

---

### 4.6 Frontend (Angular) Pod

#### 4.6.1 Deployment (`angular-deployment.yaml`)

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: angular-spa-deployment
spec:
  replicas: 1
  selector:
    matchLabels:
      app: angular
  template:
    metadata:
      labels:
        app: angular
    spec:
      containers:
        - name: angular-spa
          image: movie-frontend:latest
          imagePullPolicy: Never
          ports:
          - containerPort: 80
```

Simpler than the backend — no init containers, no secrets, no volumes. Nginx just serves static files and proxies API requests.

| Field | Purpose |
|-------|---------|
| `replicas: 1` | One frontend pod is sufficient. Static files are lightweight. |
| `image: movie-frontend:latest` | The multi-stage Docker image containing Nginx + compiled Angular files. |
| `containerPort: 80` | Nginx listens on port 80 inside the container. |

#### 4.6.2 Service (`angular-load-balancer-service.yaml`)

```yaml
apiVersion: v1
kind: Service
metadata:
  labels:
    app: angular
  name: angular-svc-loadbalancer
spec:
  type: LoadBalancer
  ports:
  - port: 80
    protocol: TCP
    nodePort: 30010
  selector:
    app: angular
```

| Field | Purpose |
|-------|---------|
| `type: LoadBalancer` | In cloud environments (AWS, GCP), this creates a real load balancer with a public IP. In Minikube, it works like NodePort. |
| `nodePort: 30010` | You access the frontend at `http://<minikube-ip>:30010` |

---

### 4.7 Services — Networking Between Pods

Pods get random IP addresses that change on every restart. Services provide stable DNS names.

```
┌──────────────────────────────────────────────────────────┐
│                    KUBERNETES CLUSTER                     │
│                                                          │
│  angular-svc-loadbalancer (LoadBalancer, :30010)         │
│       │                                                  │
│       ▼                                                  │
│  ┌─────────────┐                                         │
│  │ Nginx Pod   │─── proxy_pass http://movie-app-service  │
│  └─────────────┘                         │               │
│                                          ▼               │
│                    movie-app-service (NodePort, :30080)   │
│                         │           │                    │
│                         ▼           ▼                    │
│                    ┌─────────┐ ┌─────────┐               │
│                    │Django #1│ │Django #2│               │
│                    └────┬────┘ └────┬────┘               │
│                         │           │                    │
│                         ▼           ▼                    │
│                    mysql-service (ClusterIP, :3306)       │
│                              │                           │
│                              ▼                           │
│                        ┌───────────┐                     │
│                        │ MySQL Pod │                     │
│                        └───────────┘                     │
└──────────────────────────────────────────────────────────┘
```

**How Kubernetes DNS works:**

When a Service is created, K8s automatically creates a DNS entry:
- `mysql-service` → resolves to the MySQL pod's IP
- `movie-app-service` → load-balances between the two Django pods

This is why we use `DB_HOST=mysql-service` in Django and `proxy_pass http://movie-app-service:80` in Nginx — Kubernetes resolves these names to actual pod IPs.

---

## 5. How Frontend, Backend & Database Connect

### Complete Request Flow: User Adds a Movie

```
1. User fills form at http://192.168.105.2:30010/add-movie
   Browser sends:
   POST http://192.168.105.2:30010/api/add_movie/
   Body: {"name": "Bahubali", "year": "2020", ...}

2. Request hits NodePort 30010 → angular-svc-loadbalancer Service
   → Nginx pod (port 80)

3. Nginx sees URL starts with /api/ → matches location /api/ block
   → proxy_pass http://movie-app-service:80

4. K8s DNS resolves movie-app-service → Django pod IP
   Service load-balances: picks Django pod #1 or #2

5. Django pod receives POST /api/add_movie/ on port 8000
   → URL routing: movie/urls.py → movie_app/urls.py → MovieAddView
   → Serializer validates data
   → Movie.objects.create() → SQL INSERT

6. Django connects to mysql-service:3306 (K8s DNS → MySQL pod)
   → INSERT INTO movie_app_movie (name, year, image, description) VALUES (...)
   → Data stored on PVC (persistent)

7. Response: 201 Created
   MySQL → Django → Nginx → Browser

8. Angular receives 201 → router.navigate(['/']) → navigates to home page
   → CardComponent.ngOnInit() → GET /api/get_movies/
   → Same flow as above, returns all movies
   → Movies displayed in the UI
```

### How the Frontend Talks to the Backend

**Before K8s (hardcoded IPs):**
```typescript
private addMovieUrl = 'http://192.168.105.2:30105/api/add_movie/';
```
Problem: IP changes, port changes, breaks in different environments.

**After K8s (relative URLs):**
```typescript
private apiBase = '/api';
private addMovieUrl = `${this.apiBase}/add_movie/`;
```
The browser sends requests to the **same origin** (the Nginx pod), and Nginx proxies to the backend. No hardcoded IPs.

### How the Backend Talks to the Database

**Django `settings.py` uses environment variables:**
```python
DATABASES = {
    'default': {
        'ENGINE': os.environ.get('DB_ENGINE', 'django.db.backends.sqlite3'),
        'NAME': os.environ.get('DB_NAME', BASE_DIR / 'data' / 'db.sqlite3'),
        'USER': os.environ.get('DB_USER', ''),
        'PASSWORD': os.environ.get('DB_PASSWORD', ''),
        'HOST': os.environ.get('DB_HOST', ''),
        'PORT': os.environ.get('DB_PORT', ''),
    }
}
```

| Environment | DB_ENGINE | DB_HOST | Result |
|-------------|-----------|---------|--------|
| Local dev (no env vars) | `django.db.backends.sqlite3` | (empty) | Uses local SQLite file |
| Kubernetes (env vars set) | `django.db.backends.mysql` | `mysql-service` | Connects to MySQL pod |

**PyMySQL setup (`movie_app/__init__.py`):**
```python
import pymysql
pymysql.install_as_MySQLdb()
```
Django expects `mysqlclient` (C library) for MySQL. `pymysql` is a pure-Python alternative. This line tricks Django into using PyMySQL instead. The `cryptography` package is also required because MySQL 8 uses `caching_sha2_password` authentication.

---

## 6. Django Configuration for Multi-Environment

### ALLOWED_HOSTS

```python
ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', '').split(',') if os.environ.get('ALLOWED_HOSTS') else ['*']
```

| Scenario | ALLOWED_HOSTS env var | Result |
|----------|----------------------|--------|
| Local dev | Not set | `['*']` (allow all) |
| K8s deployment | `"*"` | `['*']` |
| Production | `"mysite.com,api.mysite.com"` | `['mysite.com', 'api.mysite.com']` |

### CORS (Cross-Origin Resource Sharing)

```python
INSTALLED_APPS = [
    ...
    'corsheaders',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',  # Must be FIRST
    ...
]

CORS_ALLOW_ALL_ORIGINS = True
```

**Why CORS?** When the frontend (`http://192.168.105.2:30010`) makes API calls to the backend (`http://192.168.105.2:30080`), the browser blocks it because they're different origins (different ports). CORS headers tell the browser: "It's okay, this backend allows requests from this frontend."

In our setup with Nginx proxy, CORS is technically not needed (requests go through the same origin). But it's useful when accessing the backend directly at `:30080`.

---

## 7. Complete Deployment Steps

### Prerequisites

- Docker Desktop installed
- Minikube installed (`brew install minikube`)
- kubectl installed (`brew install kubectl`)

### Step-by-Step Deployment

```bash
# ──────────────────────────────────
# STEP 1: Start the Cluster
# ──────────────────────────────────
minikube start

# Point your Docker CLI to Minikube's Docker daemon
# This is CRITICAL — without it, images are built in
# your Mac's Docker, not Minikube's
eval $(minikube docker-env)

# ──────────────────────────────────
# STEP 2: Build Docker Images
# ──────────────────────────────────
# Build backend image
cd /Users/kaushiknandan/Desktop/new_learning/movie
docker build -t movie-app:latest .

# Build frontend image
cd /Users/kaushiknandan/Desktop/project/movie
docker build -t movie-frontend:latest .

# ──────────────────────────────────
# STEP 3: Deploy MySQL (Database)
# ──────────────────────────────────
cd /Users/kaushiknandan/Desktop/new_learning/movie

# Create secret first (others depend on it)
kubectl apply -f k8s/mysql-secret.yaml

# Create persistent storage
kubectl apply -f k8s/mysql-pvc.yaml

# Deploy MySQL pod
kubectl apply -f k8s/mysql-deployment.yaml

# Create MySQL service (DNS entry)
kubectl apply -f k8s/mysql-service.yaml

# Wait for MySQL to be ready
kubectl wait --for=condition=ready pod -l app=mysql --timeout=120s

# ──────────────────────────────────
# STEP 4: Deploy Backend (Django)
# ──────────────────────────────────
# This will:
#   1. Start init container → run migrations against MySQL
#   2. Start main container → run Gunicorn
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml

# ──────────────────────────────────
# STEP 5: Deploy Frontend (Angular)
# ──────────────────────────────────
cd /Users/kaushiknandan/Desktop/project/movie
kubectl apply -f angular-deployment.yaml
kubectl apply -f angular-load-balancer-service.yaml

# ──────────────────────────────────
# STEP 6: Verify & Access
# ──────────────────────────────────
# Check all pods are running
kubectl get pods

# Access the application
minikube service angular-svc-loadbalancer    # Frontend
minikube service movie-app-service           # Backend API

# Open the dashboard (optional)
minikube dashboard
```

### Shutdown

```bash
# Delete all resources
kubectl delete deployment angular-spa-deployment movie-app mysql
kubectl delete service angular-svc-loadbalancer movie-app-service mysql-service
kubectl delete secret mysql-secret
kubectl delete pvc mysql-pvc

# Stop the cluster
minikube stop

# (Optional) Delete the cluster entirely
minikube delete
```

---

## 8. Useful Commands

### Docker Commands

| Command | Purpose |
|---------|---------|
| `docker build -t name:tag .` | Build an image from the Dockerfile in the current directory |
| `docker run -p 8000:8000 image` | Run a container, mapping host port 8000 to container port 8000 |
| `docker run -v vol:/path image` | Run with a named volume for persistent data |
| `docker images` | List all local images |
| `docker ps` | List running containers |
| `docker logs <container_id>` | View container logs |
| `docker exec -it <id> /bin/sh` | Open a shell inside a running container |
| `docker stop <id>` | Stop a container |
| `docker system prune` | Remove unused images, containers, and volumes |

### Kubernetes Commands

| Command | Purpose |
|---------|---------|
| `kubectl get pods` | List all pods |
| `kubectl get all` | List all resources (pods, services, deployments) |
| `kubectl get pods -w` | Watch pods in real-time (live updates) |
| `kubectl logs <pod>` | View pod logs |
| `kubectl logs -l app=movie-app` | View logs for all pods with a label |
| `kubectl describe pod <pod>` | Detailed info about a pod (events, errors) |
| `kubectl exec -it <pod> -- /bin/sh` | Shell into a running pod |
| `kubectl apply -f file.yaml` | Create/update resources from a YAML file |
| `kubectl apply -f k8s/` | Apply ALL YAML files in a directory |
| `kubectl delete -f file.yaml` | Delete resources defined in a YAML file |
| `kubectl rollout restart deployment <name>` | Restart all pods in a deployment (picks up new images) |
| `kubectl scale deployment <name> --replicas=3` | Scale to 3 pods |
| `kubectl port-forward pod/<name> 8000:8000` | Forward local port to pod port |

### Minikube Commands

| Command | Purpose |
|---------|---------|
| `minikube start` | Start the cluster |
| `minikube stop` | Stop the cluster (preserves state) |
| `minikube delete` | Delete the cluster entirely |
| `minikube dashboard` | Open the K8s web dashboard |
| `minikube service <name>` | Open a service in your browser |
| `minikube service <name> --url` | Print the URL without opening browser |
| `eval $(minikube docker-env)` | Use Minikube's Docker daemon |
| `minikube logs` | View Minikube system logs |

---

## 9. Common Issues & Fixes

### `ErrImageNeverPull`

**Cause:** Image wasn't built inside Minikube's Docker.
**Fix:**
```bash
eval $(minikube docker-env)
docker build -t movie-app:latest .
```

### `Init:Error` or `CrashLoopBackOff` on backend pods

**Cause:** Migration failed (MySQL not ready, wrong credentials, missing packages).
**Fix:**
```bash
kubectl logs <pod-name> -c run-migrations   # Check init container logs
kubectl describe pod <pod-name>              # Check events
```

### `sqlite3.OperationalError: no such table`

**Cause:** Migrations haven't run. Each container starts with a fresh filesystem.
**Fix:** In Docker, include `python manage.py migrate` in CMD. In K8s, use init containers.

### `unable to open database file` (SQLite + Docker volume)

**Cause:** Docker volumes are directories, not files. Mounting a volume at `/app/db.sqlite3` creates a directory named `db.sqlite3`.
**Fix:** Mount to a directory: `-v moviedata:/app/data` and set DB path to `data/db.sqlite3`.

### `RuntimeError: 'cryptography' package is required`

**Cause:** MySQL 8 uses `caching_sha2_password` auth which requires the Python `cryptography` package.
**Fix:** Add `cryptography==42.0.5` to `requirements.txt`.

### Browser shows stale data (empty movie list)

**Cause:** Nginx config had `application/json max` which cached API responses forever.
**Fix:** Changed to `application/json off` in `nginx-custom.conf`.

### CORS errors in browser console

**Cause:** Frontend and backend are on different origins (different ports).
**Fix:** Added `django-cors-headers` with `CORS_ALLOW_ALL_ORIGINS = True`.

---

## 10. File Structure Reference

### Backend (`/Users/kaushiknandan/Desktop/new_learning/movie/`)

```
movie/
├── Dockerfile                  # Builds Django app image
├── .dockerignore               # Files excluded from Docker image
├── requirements.txt            # Python dependencies (includes gunicorn, pymysql)
├── manage.py                   # Django management script
├── movie/                      # Django project settings
│   ├── settings.py             # Database config (env-var driven), CORS, etc.
│   ├── urls.py                 # Root URL routing
│   └── wsgi.py                 # WSGI entry point (used by Gunicorn)
├── movie_app/                  # Django app
│   ├── __init__.py             # PyMySQL initialization
│   ├── models.py               # Movie & User models
│   ├── serializers.py          # DRF serializers
│   ├── apiviews.py             # API views (CRUD operations)
│   ├── urls.py                 # App URL routing
│   └── admin.py                # Admin configuration
└── k8s/                        # Kubernetes manifests
    ├── deployment.yaml         # Django deployment (2 replicas + init container)
    ├── service.yaml            # Backend NodePort service (:30080)
    ├── mysql-secret.yaml       # Database credentials
    ├── mysql-pvc.yaml          # Persistent storage claim (1Gi)
    ├── mysql-deployment.yaml   # MySQL deployment
    └── mysql-service.yaml      # MySQL ClusterIP service (:3306)
```

### Frontend (`/Users/kaushiknandan/Desktop/project/movie/`)

```
movie/
├── Dockerfile                          # Multi-stage: Node build → Nginx serve
├── nginx-custom.conf                   # Nginx config (SPA routing + API proxy)
├── angular-deployment.yaml             # Frontend K8s deployment
├── angular-load-balancer-service.yaml  # Frontend service (:30010)
├── package.json                        # Node dependencies
└── src/
    └── app/
        ├── shared/
        │   └── shared.service.ts       # HTTP service (relative API URLs)
        ├── card/
        │   └── card.component.ts       # Movie list (calls getAllMovies on init)
        ├── add-movie/
        │   └── add-movie.component.ts  # Add movie form (navigates to / on success)
        ├── login/                      # Login component
        └── register/                   # Registration component
```

---

*Document created: April 13, 2026*
*Application: Movie App (Angular 17 + Django 5 + MySQL 8)*
*Orchestration: Kubernetes via Minikube*
