# Backend (Django) — Dockerfile & Kubernetes YAML Explained

This document explains **every single line** of the backend Dockerfile and all 6 Kubernetes manifest files inside the `k8s/` directory.

---

## Table of Contents

1. [Dockerfile Explained](#1-dockerfile-explained)
2. [K8s YAML — Common Structure](#2-k8s-yaml--common-structure)
3. [mysql-secret.yaml — Storing Passwords Safely](#3-mysql-secretyaml--storing-passwords-safely)
4. [mysql-pvc.yaml — Persistent Storage for Database](#4-mysql-pvcyaml--persistent-storage-for-database)
5. [mysql-deployment.yaml — Running the MySQL Database](#5-mysql-deploymentyaml--running-the-mysql-database)
6. [mysql-service.yaml — Making MySQL Reachable](#6-mysql-serviceyaml--making-mysql-reachable)
7. [deployment.yaml — Running the Django Backend](#7-deploymentyaml--running-the-django-backend)
8. [service.yaml — Exposing Django to the Outside](#8-serviceyaml--exposing-django-to-the-outside)
9. [How Everything Connects](#9-how-everything-connects)
10. [Order of Deployment (and Why It Matters)](#10-order-of-deployment-and-why-it-matters)

---

## 1. Dockerfile Explained

The Dockerfile is a set of instructions that tells Docker how to package your Django application into a portable, runnable **image**.

### The Complete File

```dockerfile
FROM python:3.12-slim            # Line 1
                                 
ENV PYTHONDONTWRITEBYTECODE=1    # Line 3
ENV PYTHONUNBUFFERED=1           # Line 4
                                 
WORKDIR /app                     # Line 6
                                 
COPY requirements.txt .          # Line 8
RUN pip install --no-cache-dir -r requirements.txt   # Line 9
                                 
COPY . .                         # Line 11
                                 
RUN mkdir -p /app/data           # Line 13
                                 
RUN python manage.py collectstatic --noinput || true  # Line 15
                                 
EXPOSE 8000                      # Line 17
                                 
CMD ["gunicorn", "movie.wsgi:application", "--bind", "0.0.0.0:8000"]  # Line 19
```

### Line-by-Line Breakdown

---

#### Line 1: `FROM python:3.12-slim`

**What it does:** Picks a starting point (base image) for your container.

**Think of it like:** Choosing the operating system for a new computer. Instead of starting from a blank hard drive, you start from a machine that already has Python 3.12 installed.

| Variant | Size | Contains |
|---------|------|----------|
| `python:3.12` (full) | ~900 MB | Python + build tools + lots of system libraries |
| `python:3.12-slim` | ~150 MB | Python + minimal system libraries (what we use) |
| `python:3.12-alpine` | ~50 MB | Python on Alpine Linux (very small but can have compatibility issues) |

**Why `slim`?** It's a good balance — small enough for fast builds/deploys, but has enough system libraries that most Python packages install without issues.

---

#### Line 3: `ENV PYTHONDONTWRITEBYTECODE=1`

**What it does:** Tells Python: "Don't create `.pyc` files."

**What are `.pyc` files?** When Python runs `import mymodule`, it compiles `mymodule.py` into bytecode and saves it as `mymodule.pyc` in a `__pycache__/` folder. This speeds up future imports.

**Why disable in Docker?** Inside a container, we don't care about caching compiled Python files because:
- The container's filesystem is temporary anyway
- It clutters the image with unnecessary files
- It avoids permission issues with read-only filesystems

---

#### Line 4: `ENV PYTHONUNBUFFERED=1`

**What it does:** Tells Python: "Print output immediately. Don't hold it in a buffer."

**Why is this important?** Without this, Python buffers `print()` and log output. In a Docker container, this means:
- `docker logs` shows nothing for a long time, then dumps everything at once
- `kubectl logs` behaves the same way
- If the container crashes, buffered logs are **lost forever**

With `PYTHONUNBUFFERED=1`, every `print()` and log message appears immediately in `docker logs` and `kubectl logs`.

---

#### Line 6: `WORKDIR /app`

**What it does:** Sets the working directory inside the container to `/app`. If `/app` doesn't exist, Docker creates it.

**All commands after this line run from `/app`.** So:
- `COPY requirements.txt .` copies to `/app/requirements.txt`
- `RUN pip install ...` runs inside `/app`
- `COPY . .` copies everything into `/app/`

**Without WORKDIR:** Files would go to `/` (root), mixing your app files with system files. Messy and dangerous.

---

#### Line 8: `COPY requirements.txt .`

**What it does:** Copies _only_ `requirements.txt` from your project folder into `/app/` inside the container.

**Why copy this separately?** This is a **caching optimization**. Docker builds images in layers, and each layer is cached. Here's how it works:

```
Scenario A: You change your Python code (views.py, models.py, etc.)
───────────────────────────────────────────────────────────────────
COPY requirements.txt .     → requirements.txt UNCHANGED → ✅ CACHED (instant)
RUN pip install ...          → Same requirements         → ✅ CACHED (instant)
COPY . .                     → Code CHANGED              → ❌ REBUILT
                                                            (but just copies files, fast)

Scenario B: You add a new package to requirements.txt
───────────────────────────────────────────────────────────────────
COPY requirements.txt .     → requirements.txt CHANGED   → ❌ REBUILT
RUN pip install ...          → New requirements           → ❌ REBUILT (slow, ~30-60s)
COPY . .                     → Code may or may not change → ❌ REBUILT
```

If we did `COPY . .` first and then `pip install`, ANY code change would trigger a full `pip install` (~30-60 seconds). With the split approach, `pip install` is only re-run when `requirements.txt` actually changes.

---

#### Line 9: `RUN pip install --no-cache-dir -r requirements.txt`

**What it does:** Installs all Python packages listed in `requirements.txt`.

**`--no-cache-dir`:** Normally pip caches downloaded packages in `~/.cache/pip/` so re-installs are faster. Inside a Docker image, we'll never re-install, so this cache wastes space. This flag skips caching.

**What gets installed (from `requirements.txt`):**

| Package | Version | Purpose |
|---------|---------|---------|
| `Django` | 5.0.1 | The web framework |
| `djangorestframework` | 3.14.0 | REST API support (serializers, viewsets) |
| `django-cors-headers` | 4.3.1 | Allows cross-origin requests from the Angular frontend |
| `gunicorn` | 21.2.0 | Production WSGI server (replaces `manage.py runserver`) |
| `pymysql` | 1.1.0 | Pure-Python MySQL driver (Django uses this to talk to MySQL) |
| `cryptography` | 42.0.5 | Required by MySQL 8's `caching_sha2_password` authentication |
| `python-dotenv` | 1.0.1 | Reads `.env` files for local development |
| `asgiref` | 3.7.2 | Async support for Django (installed as a Django dependency) |
| `pytz` | 2023.3 | Timezone support |

---

#### Line 11: `COPY . .`

**What it does:** Copies your **entire project** (all Python files, templates, static files, etc.) from your computer into `/app/` inside the container.

**What gets excluded?** Anything listed in `.dockerignore`:
```
__pycache__    → compiled Python cache
*.pyc, *.pyo   → compiled Python files
.git            → git history (can be huge)
db.sqlite3      → local database file
.env            → secrets (NEVER put in an image)
*.md            → documentation
ini/            → alternate requirements files
```

---

#### Line 13: `RUN mkdir -p /app/data`

**What it does:** Creates a `/app/data` directory inside the container.

**`-p` flag:** "Create parent directories if needed, and don't error if the directory already exists."

**Purpose:** When running Django **without Kubernetes** (just plain Docker), the SQLite database file is stored at `/app/data/db.sqlite3`. This directory is also a good mount point for Docker volumes.

In K8s, this line doesn't matter much because we use MySQL instead of SQLite.

---

#### Line 15: `RUN python manage.py collectstatic --noinput || true`

**What it does:** Collects all static files (CSS, JS, images) from Django apps into a single `staticfiles/` directory.

**Breaking it down:**
- `python manage.py collectstatic` — Django's built-in command that gathers static files from all installed apps (including the admin panel) into `STATIC_ROOT`
- `--noinput` — Don't prompt "Are you sure?" Just do it.
- `|| true` — If `collectstatic` fails (e.g., `STATIC_ROOT` isn't configured), **don't fail the build**. The `||` means "or", so if the left command fails, run `true` (which always succeeds).

**Why might it fail?** Some Django configurations don't have `STATIC_ROOT` set, or static files aren't critical for an API-only backend. The `|| true` ensures the Docker build completes regardless.

---

#### Line 17: `EXPOSE 8000`

**What it does:** Documents that the container listens on port 8000.

**Important: This does NOT actually open port 8000.** It's purely informational — like a comment for humans and tools. The port is actually opened by:
- Docker: `docker run -p 8000:8000 ...` (the `-p` flag)
- Kubernetes: `containerPort: 8000` in the deployment YAML

Think of `EXPOSE` as a label on a box that says "fragile" — it tells you something, but doesn't actually protect the contents.

---

#### Line 19: `CMD ["gunicorn", "movie.wsgi:application", "--bind", "0.0.0.0:8000"]`

**What it does:** This is the **default command** that runs when the container starts.

**Breaking it down:**

| Part | Meaning |
|------|---------|
| `gunicorn` | The program to run — Gunicorn, a production-grade Python web server |
| `movie.wsgi:application` | Tells Gunicorn where to find the Django app. `movie.wsgi` is the file `movie/wsgi.py`, and `application` is the WSGI object inside it |
| `--bind 0.0.0.0:8000` | Listen on all network interfaces (`0.0.0.0`) on port 8000. Using `127.0.0.1` would only accept connections from inside the container (useless) |

**Why Gunicorn, not `python manage.py runserver`?**

| | `manage.py runserver` | Gunicorn |
|---|---|---|
| Handles concurrent requests | ❌ Single-threaded | ✅ Multiple workers |
| Production-ready | ❌ No | ✅ Yes |
| Auto-reloads on code changes | ✅ Yes (dev convenience) | ❌ No (stability) |
| Performance under load | Poor | Good |
| Django's own recommendation | "DO NOT USE IN PRODUCTION" | Recommended |

**`CMD` vs `RUN`:**
- `RUN` executes during **image build** (e.g., install packages, copy files)
- `CMD` executes when the **container starts** (e.g., run the server)

---

### Visual: How the Dockerfile Builds Layer by Layer

```
┌─────────────────────────────────────────────┐
│  Layer 7: CMD gunicorn ...                  │ ← Runs at container START
├─────────────────────────────────────────────┤
│  Layer 6: EXPOSE 8000                       │ ← Metadata only
├─────────────────────────────────────────────┤
│  Layer 5: collectstatic                     │ ← Gathers static files
├─────────────────────────────────────────────┤
│  Layer 4: mkdir /app/data                   │ ← Creates data directory
├─────────────────────────────────────────────┤
│  Layer 3: COPY . .  (your code)             │ ← Changes often → rebuilt often
├─────────────────────────────────────────────┤
│  Layer 2: pip install requirements.txt      │ ← Changes rarely → cached ✅
├─────────────────────────────────────────────┤
│  Layer 1: COPY requirements.txt             │ ← Changes rarely → cached ✅
├─────────────────────────────────────────────┤
│  Layer 0: python:3.12-slim (base image)     │ ← Never changes → cached ✅
└─────────────────────────────────────────────┘
```

---

## 2. K8s YAML — Common Structure

Every Kubernetes YAML file follows this structure:

```yaml
apiVersion: ___    # Which K8s API to use (like choosing which version of a form to fill)
kind: ___          # What type of resource (Deployment, Service, Secret, etc.)
metadata:          # Identity information
  name: ___        #   A unique name for this resource
  labels:          #   Tags for organizing/finding resources
    key: value
spec:              # The specification — what you WANT Kubernetes to create
  ...
```

**Think of it like filling out a government form:**
- `apiVersion` = which version of the form
- `kind` = what type of application (business license, building permit, etc.)
- `metadata` = your name and ID
- `spec` = what you're actually requesting

---

## 3. mysql-secret.yaml — Storing Passwords Safely

### The Complete File

```yaml
apiVersion: v1              # Line 1
kind: Secret                # Line 2
metadata:                   # Line 3
  name: mysql-secret        # Line 4
type: Opaque                # Line 5
stringData:                 # Line 6
  MYSQL_ROOT_PASSWORD: rootpass123    # Line 7
  MYSQL_DATABASE: moviedb            # Line 8
  MYSQL_USER: movieuser              # Line 9
  MYSQL_PASSWORD: moviepass123       # Line 10
```

### Line-by-Line

#### Line 1: `apiVersion: v1`

The Secret resource is part of the core Kubernetes API (`v1`). Core resources like Pods, Services, Secrets, and ConfigMaps all use `v1`. More complex resources like Deployments use `apps/v1`.

#### Line 2: `kind: Secret`

Tells Kubernetes: "I want to create a Secret." A Secret stores sensitive data (passwords, API keys, tokens) so it's not hardcoded in your deployment files.

#### Line 4: `name: mysql-secret`

The unique name of this Secret. Other resources refer to it by this name. For example, in `deployment.yaml`:
```yaml
secretKeyRef:
  name: mysql-secret     # ← This references the name on Line 4
  key: MYSQL_DATABASE
```

#### Line 5: `type: Opaque`

The type of Secret. Kubernetes supports several types:

| Type | Used For |
|------|----------|
| `Opaque` | Generic key-value pairs (our case — passwords, usernames) |
| `kubernetes.io/tls` | TLS certificates |
| `kubernetes.io/dockerconfigjson` | Docker registry credentials |
| `kubernetes.io/basic-auth` | Username/password pairs |

`Opaque` = "K8s doesn't know or care what's inside. It's just data."

#### Line 6: `stringData:`

Lets you write values in **plain text**. Kubernetes automatically base64-encodes them when storing.

**Alternative: `data:`** — requires you to manually base64-encode values:
```yaml
# Using stringData (human-readable):
stringData:
  MYSQL_PASSWORD: moviepass123

# Using data (base64-encoded):
data:
  MYSQL_PASSWORD: bW92aWVwYXNzMTIz    # base64 of "moviepass123"
```

Both produce the same result. `stringData` is just more convenient.

#### Lines 7-10: The actual secrets

| Key | Value | Who Uses It |
|-----|-------|-------------|
| `MYSQL_ROOT_PASSWORD` | `rootpass123` | MySQL container — sets the root superuser password on first boot |
| `MYSQL_DATABASE` | `moviedb` | MySQL container — creates this database on first boot. Django connects to this database. |
| `MYSQL_USER` | `movieuser` | MySQL — creates this user. Django uses this user to connect. |
| `MYSQL_PASSWORD` | `moviepass123` | MySQL — password for `movieuser`. Django uses this to authenticate. |

**How these flow through the system:**

```
mysql-secret.yaml
    │
    ├──→ mysql-deployment.yaml (envFrom: secretRef)
    │       MySQL reads MYSQL_ROOT_PASSWORD, MYSQL_DATABASE, etc.
    │       to auto-configure on first startup
    │
    └──→ deployment.yaml (env: secretKeyRef for each key)
            Django reads DB_NAME, DB_USER, DB_PASSWORD
            to connect to MySQL
```

**⚠️ Security Note:** In production, never commit secrets to Git. Use:
- HashiCorp Vault
- AWS Secrets Manager / Azure Key Vault
- Kubernetes External Secrets Operator
- Sealed Secrets

---

## 4. mysql-pvc.yaml — Persistent Storage for Database

### The Complete File

```yaml
apiVersion: v1                    # Line 1
kind: PersistentVolumeClaim       # Line 2
metadata:                         # Line 3
  name: mysql-pvc                 # Line 4
spec:                             # Line 5
  accessModes:                    # Line 6
    - ReadWriteOnce               # Line 7
  resources:                      # Line 8
    requests:                     # Line 9
      storage: 1Gi                # Line 10
```

### Line-by-Line

#### Line 2: `kind: PersistentVolumeClaim`

A PVC is a **request for storage**. It's like submitting a ticket to IT: "I need 1 GB of disk space."

**Why is this necessary?** Containers are ephemeral (temporary). When a pod restarts, everything inside its filesystem is **destroyed**. For a database, this means all your data is gone.

```
WITHOUT PVC:
  Pod starts → MySQL creates tables → You add 100 movies → Pod crashes → Pod restarts
  → ALL DATA GONE. Database is empty again. 💀

WITH PVC:
  Pod starts → MySQL writes to PVC → You add 100 movies → Pod crashes → Pod restarts
  → PVC still has all data → MySQL reads from PVC → All 100 movies are there ✅
```

#### Line 4: `name: mysql-pvc`

The name other resources use to reference this PVC. In `mysql-deployment.yaml`:
```yaml
volumes:
  - name: mysql-storage
    persistentVolumeClaim:
      claimName: mysql-pvc       # ← References this PVC
```

#### Line 7: `ReadWriteOnce`

Defines who can access the storage and how:

| Access Mode | Meaning |
|-------------|---------|
| `ReadWriteOnce` (RWO) | One node can mount it as read-write. Our case — only the MySQL pod on one node needs it. |
| `ReadOnlyMany` (ROX) | Many nodes can mount it as read-only. |
| `ReadWriteMany` (RWX) | Many nodes can mount it as read-write. Requires special storage (NFS, CephFS). |

Since we have 1 MySQL replica on 1 Minikube node, `ReadWriteOnce` is perfect.

#### Line 10: `storage: 1Gi`

Requesting 1 Gigabyte of disk space. Kubernetes will find or create a PersistentVolume (PV) that has at least 1 Gi. In Minikube, this is automatically provisioned from the host machine's disk.

**PVC lifecycle:**

```
1. You create PVC (request):  "I need 1Gi of ReadWriteOnce storage"
                                    │
2. K8s provisions PV (actual disk): "Here's a 1Gi disk"
                                    │
3. PVC is BOUND to PV:             "Your request is fulfilled"
                                    │
4. Pod mounts PVC:                  "MySQL now writes to this disk"
                                    │
5. Pod dies, restarts:              "Disk survives! Data is safe."
```

---

## 5. mysql-deployment.yaml — Running the MySQL Database

### The Complete File

```yaml
apiVersion: apps/v1               # Line 1
kind: Deployment                  # Line 2
metadata:                         # Line 3
  name: mysql                     # Line 4
  labels:                         # Line 5
    app: mysql                    # Line 6
spec:                             # Line 7
  replicas: 1                     # Line 8
  selector:                       # Line 9
    matchLabels:                  # Line 10
      app: mysql                  # Line 11
  template:                       # Line 12
    metadata:                     # Line 13
      labels:                     # Line 14
        app: mysql                # Line 15
    spec:                         # Line 16
      containers:                 # Line 17
        - name: mysql             # Line 18
          image: mysql:8.0        # Line 19
          ports:                  # Line 20
            - containerPort: 3306 # Line 21
          envFrom:                # Line 22
            - secretRef:          # Line 23
                name: mysql-secret # Line 24
          volumeMounts:           # Line 25
            - mountPath: /var/lib/mysql  # Line 26
              name: mysql-storage        # Line 27
      volumes:                    # Line 28
        - name: mysql-storage     # Line 29
          persistentVolumeClaim:  # Line 30
            claimName: mysql-pvc  # Line 31
```

### Line-by-Line

#### Line 1: `apiVersion: apps/v1`

Deployments belong to the `apps` API group (not core `v1`). This is because Deployments are a higher-level concept built on top of ReplicaSets.

#### Line 2: `kind: Deployment`

A Deployment tells Kubernetes: "I want N copies of this pod running at all times. If one dies, create a new one."

**Deployment vs Pod:** You could create a bare Pod, but if it crashes, it's gone forever. A Deployment **watches** its pods and recreates them automatically.

#### Lines 4-6: `name` and `labels`

```yaml
name: mysql           # The Deployment's unique name
labels:
  app: mysql          # A tag — like putting a "mysql" sticker on this resource
```

Labels are key-value pairs used to organize and select resources. The label `app: mysql` is used by the Service to find the right pods.

#### Line 8: `replicas: 1`

Run exactly 1 MySQL pod. **Why only 1?** Databases are stateful — running 2 MySQL pods against the same PVC would cause data corruption. Scaling databases requires specialized tools (MySQL Group Replication, StatefulSets, etc.).

#### Lines 9-11: `selector.matchLabels`

```yaml
selector:
  matchLabels:
    app: mysql      # "This Deployment manages pods with the label app=mysql"
```

This links the Deployment to its pods. The selector **must match** the labels in `template.metadata.labels` (line 15). If they don't match, K8s rejects the YAML.

#### Lines 12-15: `template` (Pod Template)

```yaml
template:               # "Here's the blueprint for each pod"
  metadata:
    labels:
      app: mysql        # Every pod gets this label (must match selector on line 11)
```

Everything inside `template:` describes what each pod looks like. The Deployment uses this template to create pods.

#### Lines 18-19: Container definition

```yaml
- name: mysql           # Container name (for logs: kubectl logs <pod> -c mysql)
  image: mysql:8.0      # Use the official MySQL 8.0 image from Docker Hub
```

Unlike our app images (which use `imagePullPolicy: Never` because they're built locally), `mysql:8.0` is pulled from Docker Hub. Minikube's Docker daemon downloads it automatically.

#### Line 21: `containerPort: 3306`

MySQL listens on port 3306 inside the container. This is informational (similar to `EXPOSE` in Dockerfile) — the actual port is configured by MySQL itself.

#### Lines 22-24: `envFrom` with `secretRef`

```yaml
envFrom:
  - secretRef:
      name: mysql-secret    # Inject ALL keys from mysql-secret as env vars
```

This takes every key-value pair in `mysql-secret` and makes them environment variables inside the container:

```
Container gets:
  MYSQL_ROOT_PASSWORD=rootpass123
  MYSQL_DATABASE=moviedb
  MYSQL_USER=movieuser
  MYSQL_PASSWORD=moviepass123
```

The official MySQL Docker image reads these variables on **first startup** and:
1. Sets the root password to `rootpass123`
2. Creates a database named `moviedb`
3. Creates a user `movieuser` with password `moviepass123`
4. Grants `movieuser` full access to `moviedb`

**`envFrom` vs `env`:**

```yaml
# envFrom: imports ALL keys, names stay the same
envFrom:
  - secretRef:
      name: mysql-secret
# Result: MYSQL_ROOT_PASSWORD, MYSQL_DATABASE, MYSQL_USER, MYSQL_PASSWORD

# env: imports specific keys, you can rename them
env:
  - name: DB_NAME              # Custom name inside container
    valueFrom:
      secretKeyRef:
        name: mysql-secret
        key: MYSQL_DATABASE    # Original key in the secret
# Result: DB_NAME=moviedb
```

MySQL needs the original names (`MYSQL_*`), so `envFrom` is perfect. Django needs different names (`DB_*`), so it uses `env` with `secretKeyRef`.

#### Lines 25-27: `volumeMounts`

```yaml
volumeMounts:
  - mountPath: /var/lib/mysql    # Mount the storage HERE inside the container
    name: mysql-storage          # Use the volume named "mysql-storage"
```

This tells the container: "At the path `/var/lib/mysql` (where MySQL stores all database files), use the external persistent storage instead of the container's own filesystem."

#### Lines 28-31: `volumes`

```yaml
volumes:
  - name: mysql-storage                # Volume name (referenced by volumeMounts)
    persistentVolumeClaim:
      claimName: mysql-pvc             # Use the PVC we created earlier
```

This links the volume name `mysql-storage` to the actual PVC named `mysql-pvc`.

**Complete storage chain:**

```
Container path /var/lib/mysql
        │ (volumeMount: name=mysql-storage)
        ▼
Volume: mysql-storage
        │ (persistentVolumeClaim: claimName=mysql-pvc)
        ▼
PVC: mysql-pvc
        │ (K8s auto-binds to a PersistentVolume)
        ▼
PV: Auto-provisioned disk (1Gi on Minikube's host)
```

---

## 6. mysql-service.yaml — Making MySQL Reachable

### The Complete File

```yaml
apiVersion: v1                # Line 1
kind: Service                 # Line 2
metadata:                     # Line 3
  name: mysql-service         # Line 4
spec:                         # Line 5
  selector:                   # Line 6
    app: mysql                # Line 7
  ports:                      # Line 8
    - protocol: TCP           # Line 9
      port: 3306              # Line 10
      targetPort: 3306        # Line 11
  type: ClusterIP             # Line 12
```

### Line-by-Line

#### Line 2: `kind: Service`

**Why do we need a Service?** Pods get random IP addresses that change every time they restart. If Django tries to connect to MySQL by IP, it would break on every restart.

A Service provides a **stable DNS name** (`mysql-service`) that always points to the right pod, no matter how many times it restarts.

```
Without Service:
  Django connects to 10.1.0.15:3306 → Pod restarts → New IP 10.1.0.23
  → Django still tries 10.1.0.15 → CONNECTION REFUSED ❌

With Service:
  Django connects to mysql-service:3306 → K8s resolves to current pod IP
  → Pod restarts → K8s updates resolution → Django still works ✅
```

#### Line 4: `name: mysql-service`

This name becomes a **DNS entry** inside the cluster. Any pod can connect to `mysql-service` by name. That's why Django's `DB_HOST` is set to `mysql-service`.

#### Lines 6-7: `selector`

```yaml
selector:
  app: mysql       # "Route traffic to pods with the label app=mysql"
```

The Service finds pods by their labels. Any pod with `app: mysql` receives traffic from this Service. This matches the label in `mysql-deployment.yaml` (line 15: `app: mysql`).

#### Lines 9-11: Port mapping

```yaml
ports:
  - protocol: TCP
    port: 3306          # The port the SERVICE listens on
    targetPort: 3306    # The port on the POD to forward to
```

| Field | What it means | Who uses it |
|-------|--------------|-------------|
| `port: 3306` | The Service's own port. Other pods connect to `mysql-service:3306`. | Django (as `DB_HOST=mysql-service`, `DB_PORT=3306`) |
| `targetPort: 3306` | The port inside the MySQL container. The Service forwards traffic here. | MySQL container (listens on 3306) |

In this case, both are 3306, but they can be different. For example, the backend service uses `port: 80` → `targetPort: 8000`.

#### Line 12: `type: ClusterIP`

| Service Type | Accessible From | Our Use |
|-------------|----------------|---------|
| **ClusterIP** | Only within the cluster | ✅ MySQL — should never be exposed outside |
| NodePort | Outside the cluster via `<NodeIP>:<30000+>` | Used for the backend |
| LoadBalancer | Outside via cloud load balancer | Used for the frontend |

**ClusterIP is the default** and the most secure. The database should ONLY be reachable from inside the cluster (by Django pods), never from the internet.

---

## 7. deployment.yaml — Running the Django Backend

### The Complete File (with sections marked)

```yaml
apiVersion: apps/v1                          # Line 1
kind: Deployment                             # Line 2
metadata:                                    # Line 3
  name: movie-app                            # Line 4
  labels:                                    # Line 5
    app: movie-app                           # Line 6

spec:                                        # Line 7
  replicas: 2                                # Line 8    ← SECTION A: Pod count
  selector:                                  # Line 9
    matchLabels:                             # Line 10
      app: movie-app                         # Line 11

  template:                                  # Line 12   ← SECTION B: Pod blueprint
    metadata:                                # Line 13
      labels:                                # Line 14
        app: movie-app                       # Line 15

    spec:                                    # Line 16
      # ─── SECTION C: Init Container ───
      initContainers:                        # Line 17
        - name: run-migrations               # Line 18
          image: movie-app:latest            # Line 19
          imagePullPolicy: Never             # Line 20
          command: ["python", "manage.py", "migrate"]  # Line 21
          env:                               # Line 22
            - name: DB_ENGINE                # Line 23
              value: "django.db.backends.mysql"  # Line 24
            - name: DB_HOST                  # Line 25
              value: "mysql-service"         # Line 26
            - name: DB_PORT                  # Line 27
              value: "3306"                  # Line 28
            - name: DB_NAME                  # Lines 29-33
              valueFrom:
                secretKeyRef:
                  name: mysql-secret
                  key: MYSQL_DATABASE
            - name: DB_USER                  # Lines 34-38
              valueFrom:
                secretKeyRef:
                  name: mysql-secret
                  key: MYSQL_USER
            - name: DB_PASSWORD              # Lines 39-43
              valueFrom:
                secretKeyRef:
                  name: mysql-secret
                  key: MYSQL_PASSWORD

      # ─── SECTION D: Main Container ───
      containers:                            # Line 44
        - name: movie-app                    # Line 45
          image: movie-app:latest            # Line 46
          imagePullPolicy: Never             # Line 47
          ports:                             # Line 48
            - containerPort: 8000            # Line 49
          env:                               # Line 50
            - name: DJANGO_SETTINGS_MODULE   # Line 51
              value: "movie.settings"        # Line 52
            - name: ALLOWED_HOSTS            # Line 53
              value: "*"                     # Line 54
            - name: DB_ENGINE                # Line 55
              value: "django.db.backends.mysql"
            - name: DB_HOST                  # Line 57
              value: "mysql-service"
            - name: DB_PORT                  # Line 59
              value: "3306"
            - name: DB_NAME                  # Lines 61-65
              valueFrom:
                secretKeyRef:
                  name: mysql-secret
                  key: MYSQL_DATABASE
            - name: DB_USER                  # Lines 66-70
              valueFrom:
                secretKeyRef:
                  name: mysql-secret
                  key: MYSQL_USER
            - name: DB_PASSWORD              # Lines 71-75
              valueFrom:
                secretKeyRef:
                  name: mysql-secret
                  key: MYSQL_PASSWORD
            - name: CORS_ALLOW_ALL_ORIGINS   # Line 76
              value: "True"                  # Line 77

          # ─── SECTION E: Health Checks ───
          readinessProbe:                    # Line 78
            httpGet:                         # Line 79
              path: /admin/                  # Line 80
              port: 8000                     # Line 81
            initialDelaySeconds: 10          # Line 82
            periodSeconds: 10                # Line 83
          livenessProbe:                     # Line 84
            httpGet:                         # Line 85
              path: /admin/                  # Line 86
              port: 8000                     # Line 87
            initialDelaySeconds: 15          # Line 88
            periodSeconds: 30                # Line 89
```

### Section-by-Section Breakdown

---

### SECTION A: Replicas & Selector (Lines 8-11)

#### Line 8: `replicas: 2`

Run **2 identical Django pods**. Benefits:

```
                    movie-app-service
                          │
                ┌─────────┴─────────┐
                ▼                   ▼
         ┌────────────┐      ┌────────────┐
         │ Django #1  │      │ Django #2  │
         │ (pod)      │      │ (pod)      │
         └────────────┘      └────────────┘

Benefit 1: HIGH AVAILABILITY
  → Django #1 crashes → Django #2 keeps serving → No downtime for users

Benefit 2: LOAD BALANCING
  → Request 1 → Django #1
  → Request 2 → Django #2
  → Request 3 → Django #1  (alternating automatically)
```

---

### SECTION C: Init Container (Lines 17-43)

#### Line 17: `initContainers:`

Init containers run **before** the main container, and they **must succeed** before the main container starts.

```
Pod Lifecycle:
═══════════════════════════════════════════════════
  Phase 1: Init Container                  Phase 2: Main Container
  ┌─────────────────────────┐             ┌─────────────────────────┐
  │ run-migrations          │             │ movie-app               │
  │                         │  success    │                         │
  │ python manage.py migrate│ ──────────▶ │ gunicorn (serves HTTP)  │
  │                         │             │                         │
  │ Creates/updates DB      │  failure    │ Handles API requests    │
  │ tables                  │ ──▶ RETRY   │                         │
  └─────────────────────────┘             └─────────────────────────┘
```

#### Line 20: `imagePullPolicy: Never`

"Don't pull this image from Docker Hub. It already exists locally in Minikube's Docker daemon."

This is why `eval $(minikube docker-env)` is critical before building — it builds the image inside Minikube where the pods can find it.

| Policy | Behavior |
|--------|----------|
| `Never` | Only use local image. Error if not found. (For local dev with Minikube) |
| `Always` | Always pull from registry. (For production) |
| `IfNotPresent` | Pull only if not cached locally. (Default for tagged images) |

#### Line 21: `command: ["python", "manage.py", "migrate"]`

**Overrides the Dockerfile's `CMD`.** Instead of running Gunicorn, this container runs Django's migration command, which creates/updates database tables.

**Why migrations need a separate step:**
- At Docker build time (Dockerfile), MySQL doesn't exist yet — it's a separate pod
- At run time, MySQL is alive, so migrations can connect and create tables
- With `replicas: 2`, if we put `migrate` in CMD, both pods would run migrations simultaneously (race condition). Init containers run once per pod startup, and K8s handles ordering.

#### Lines 23-43: Environment variables

The init container needs the same database credentials as the main container. Two approaches are used:

**Hardcoded values** (non-sensitive):
```yaml
- name: DB_ENGINE
  value: "django.db.backends.mysql"    # Which database driver to use
- name: DB_HOST
  value: "mysql-service"              # K8s DNS name of MySQL Service
- name: DB_PORT
  value: "3306"                       # MySQL's port
```

**From Secret** (sensitive):
```yaml
- name: DB_NAME
  valueFrom:
    secretKeyRef:
      name: mysql-secret        # Which Secret to read from
      key: MYSQL_DATABASE       # Which key in that Secret

# Result: DB_NAME = "moviedb"
```

**How Django uses these:** In `settings.py`:
```python
DATABASES = {
    'default': {
        'ENGINE': os.environ.get('DB_ENGINE', 'django.db.backends.sqlite3'),
        'NAME': os.environ.get('DB_NAME', BASE_DIR / 'data' / 'db.sqlite3'),
        'HOST': os.environ.get('DB_HOST', ''),
        ...
    }
}
```
When env vars are set (K8s), Django uses MySQL. When they're not (local dev), it falls back to SQLite.

---

### SECTION D: Main Container (Lines 44-77)

#### Lines 51-52: `DJANGO_SETTINGS_MODULE`

```yaml
- name: DJANGO_SETTINGS_MODULE
  value: "movie.settings"
```
Tells Django which settings file to use. Python path `movie.settings` = file `movie/settings.py`.

#### Lines 53-54: `ALLOWED_HOSTS`

```yaml
- name: ALLOWED_HOSTS
  value: "*"
```
Django rejects HTTP requests whose `Host` header doesn't match `ALLOWED_HOSTS`. `*` means "accept from any hostname." In production, you'd set this to your actual domain.

#### Lines 76-77: `CORS_ALLOW_ALL_ORIGINS`

```yaml
- name: CORS_ALLOW_ALL_ORIGINS
  value: "True"
```
Allows the Angular frontend (running on a different port/origin) to make API requests to Django. Without CORS headers, browsers block cross-origin requests.

---

### SECTION E: Health Checks (Lines 78-89)

#### Lines 78-83: `readinessProbe`

```yaml
readinessProbe:
  httpGet:
    path: /admin/           # K8s makes GET request to this URL
    port: 8000              # on this port
  initialDelaySeconds: 10   # Wait 10s after container starts before first check
  periodSeconds: 10         # Then check every 10 seconds
```

**Question it answers:** "Is this pod ready to receive user traffic?"

**If it fails:** The pod is removed from the Service's endpoint list. No traffic is routed to it. The pod keeps running — it just doesn't receive new requests.

**Timeline example:**
```
0s    Container starts (Gunicorn booting up...)
5s    Gunicorn still loading Django...
10s   FIRST READINESS CHECK → GET /admin/ → 200 OK ✅
      → Pod is marked "Ready" → Service starts sending traffic to it
20s   Check again → 200 OK ✅ → Still receiving traffic
```

#### Lines 84-89: `livenessProbe`

```yaml
livenessProbe:
  httpGet:
    path: /admin/
    port: 8000
  initialDelaySeconds: 15    # Wait 15s before first check
  periodSeconds: 30           # Check every 30 seconds
```

**Question it answers:** "Is this pod still alive and functioning?"

**If it fails 3 times in a row:** Kubernetes **kills and restarts** the pod. This handles scenarios where the application gets stuck (deadlock, memory leak, infinite loop).

**Readiness vs Liveness — Key Difference:**

| | Readiness | Liveness |
|---|---|---|
| Question | "Can you take traffic?" | "Are you alive?" |
| On failure | Stop sending traffic (pod keeps running) | Kill and restart the pod |
| Use case | Pod is booting up, or temporarily overloaded | Pod is stuck/crashed |
| initialDelaySeconds | Lower (10s) — check soon | Higher (15s) — give more time |
| periodSeconds | Lower (10s) — check frequently | Higher (30s) — less aggressive |

**Why `/admin/`?** Django's admin page is a simple URL that returns 200 if Django is working. It doesn't require authentication for a GET request (it shows the login page). A custom `/health/` endpoint would be better in production.

---

## 8. service.yaml — Exposing Django to the Outside

### The Complete File

```yaml
apiVersion: v1                 # Line 1
kind: Service                  # Line 2
metadata:                      # Line 3
  name: movie-app-service      # Line 4
spec:                          # Line 5
  type: NodePort               # Line 6
  selector:                    # Line 7
    app: movie-app             # Line 8
  ports:                       # Line 9
    - protocol: TCP            # Line 10
      port: 80                 # Line 11
      targetPort: 8000         # Line 12
      nodePort: 30080          # Line 13
```

### Line-by-Line

#### Line 4: `name: movie-app-service`

This name is critical — it's the DNS name used by the **frontend Nginx** to proxy API requests:
```nginx
# In nginx-custom.conf:
location /api/ {
    proxy_pass http://movie-app-service:80;    # ← This name!
}
```

#### Line 6: `type: NodePort`

Exposes the Service on a static port on the Minikube node. Accessible from outside the cluster.

#### Lines 8: `selector: app: movie-app`

Routes traffic to pods labeled `app: movie-app` — that's our Django pods.

Since we have `replicas: 2`, the Service **load-balances** between both Django pods automatically.

#### Lines 10-13: Port mapping

```
                 OUTSIDE CLUSTER              INSIDE CLUSTER
                 ════════════════             ════════════════
Browser/curl ──▶ nodePort: 30080 ──▶ port: 80 ──▶ targetPort: 8000 ──▶ Gunicorn
                 (on Minikube IP)    (Service)    (Container)
```

| Field | Value | Who connects to it |
|-------|-------|-------------------|
| `nodePort: 30080` | External port on the Minikube node | You, directly: `http://<minikube-ip>:30080/api/get_movies/` |
| `port: 80` | The Service's internal port | Nginx (frontend): `proxy_pass http://movie-app-service:80` |
| `targetPort: 8000` | The container's port (Gunicorn) | The Service forwards traffic here |

**Why is `port` (80) different from `targetPort` (8000)?** This provides abstraction. Nginx connects to `movie-app-service:80` (standard HTTP port). The Service translates port 80 → 8000. If you later change Gunicorn to listen on port 9000, you only update `targetPort` — Nginx config stays the same.

---

## 9. How Everything Connects

```
┌─────────────────────────────────────────────────────────────────────┐
│                      KUBERNETES CLUSTER                            │
│                                                                     │
│  mysql-secret ─────────────────────────────┐                        │
│       │                                    │                        │
│       │ (envFrom)                          │ (secretKeyRef)          │
│       ▼                                    ▼                        │
│  ┌──────────────┐                    ┌──────────────┐               │
│  │ MySQL Pod    │                    │ Django Pod×2 │               │
│  │ image:       │                    │ image:       │               │
│  │  mysql:8.0   │◀───────────────────│ movie-app    │               │
│  │ port: 3306   │  mysql-service     │ port: 8000   │               │
│  │              │  (ClusterIP)       │              │               │
│  │ Data on PVC ─┼── mysql-pvc (1Gi)  │ init: migrate│               │
│  └──────────────┘                    └──────┬───────┘               │
│                                             │                       │
│                                    movie-app-service                │
│                                    (NodePort :30080)                │
│                                             │                       │
│                                             │ proxy_pass            │
│                                             │                       │
│                                    ┌────────┴───────┐               │
│                                    │ Angular Pod    │               │
│                                    │ image:         │               │
│                                    │ movie-frontend │               │
│                                    │ Nginx :80      │               │
│                                    └────────┬───────┘               │
│                                             │                       │
│                                    angular-svc-loadbalancer         │
│                                    (LoadBalancer :30010)             │
└─────────────────────────────────────────────┼───────────────────────┘
                                              │
                                         User Browser
                                    http://<minikube-ip>:30010
```

---

## 10. Order of Deployment (and Why It Matters)

```
Step 1: mysql-secret.yaml
        ↓  (MySQL and Django both need credentials)
Step 2: mysql-pvc.yaml
        ↓  (MySQL needs storage before it can start)
Step 3: mysql-deployment.yaml
        ↓  (MySQL pod starts, creates DB using secret values)
Step 4: mysql-service.yaml
        ↓  (Creates DNS entry "mysql-service" so Django can find MySQL)
Step 5: Wait for MySQL to be ready
        ↓  (kubectl wait --for=condition=ready pod -l app=mysql)
Step 6: deployment.yaml (Django)
        ↓  (Init container runs migrations against MySQL, then Gunicorn starts)
Step 7: service.yaml (Django service)
        ↓  (Creates DNS entry "movie-app-service" so Nginx can find Django)
Step 8: angular-deployment.yaml
        ↓  (Nginx starts, proxies /api/ to movie-app-service)
Step 9: angular-load-balancer-service.yaml
        ↓  (Exposes frontend on port 30010)
```

**Why this order?**
- Secret must exist before pods that reference it (otherwise: `CreateContainerConfigError`)
- PVC must exist before the MySQL pod mounts it (otherwise: pod stuck in `Pending`)
- MySQL must be running before Django runs migrations (otherwise: `ConnectionRefused`)
- Django Service must exist before Nginx proxies to it (otherwise: `502 Bad Gateway`)

---

*Document created: April 14, 2026*
