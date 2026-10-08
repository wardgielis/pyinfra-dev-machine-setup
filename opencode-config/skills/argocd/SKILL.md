---
name: argocd
description: Use when installing, configuring, operating, or troubleshooting Argo CD — Application and ApplicationSet resources, AppProjects, sync waves and hooks, sync options (ServerSideApply, Replace, CreateNamespace, Prune), repository layout, GitLab integration (deployment tracking, webhooks, SSO, repo credentials), secrets via External Secrets Operator, RBAC and SSO, scaling the repo-server and application controller, upgrades and CVEs, and per-chart gotchas (Airflow, cert-manager, ingress-nginx, Helm hooks). Argo CD is the GitOps controller we standardise on. Read [[kubernetes]] for generic Kubernetes practice and [[naturalis-kubernetes]] for org conventions.
metadata:
  review_after: "2026-11-08"
  docs_url: "https://argo-cd.readthedocs.io/en/stable/"
---

# argocd

Operating manual for Argo CD: why it is the right choice for a team learning Kubernetes, how to install it so it manages itself, the sync semantics that explain every confusing failure, the GitLab integration gaps and their real workarounds, and the per-chart gotchas that cost a day each if you meet them cold.

**Argo CD is our GitOps controller.** Everything in the cluster arrives through it. If a change did not come from Git via Argo CD, it is drift.

**Related skills**: [[kubernetes]] for generic Kubernetes practice (manifests, networking, storage, security, monorepo layout), [[naturalis-kubernetes]] for org conventions (Vault address and roles, the self-managed GitLab instance, OpenStack, environment tiers), [[gitlab-cicd]] for CI/CD and the Component Catalog, [[glab-cli]] for `glab`, [[airflow]] for Airflow itself, [[opentofu]] / [[naturalis-opentofu]] for the infrastructure underneath, [[pyinfra]] / [[biocloud-pyinfra]] for node configuration.

## Contents

1. [The decision: why Argo CD](#1-the-decision-why-argo-cd)
2. [Mental model](#2-mental-model)
3. [Installation and bootstrap](#3-installation-and-bootstrap)
4. [Repository layout](#4-repository-layout)
5. [The Application resource](#5-the-application-resource)
6. [ApplicationSet](#6-applicationset)
7. [Sync phases, waves and hooks](#7-sync-phases-waves-and-hooks)
8. [Sync options that solve real failures](#8-sync-options-that-solve-real-failures)
9. [Helm under Argo CD](#9-helm-under-argo-cd)
10. [GitLab integration: what works and what does not](#10-gitlab-integration-what-works-and-what-does-not)
11. [Secrets](#11-secrets)
12. [Projects, RBAC and SSO](#12-projects-rbac-and-sso)
13. [Per-chart gotchas](#13-per-chart-gotchas)
14. [Daily operations](#14-daily-operations)
15. [Scaling and tuning](#15-scaling-and-tuning)
16. [Security and upgrades](#16-security-and-upgrades)
17. [Troubleshooting](#17-troubleshooting)
18. [Anti-patterns](#18-anti-patterns)
19. [Version reference](#19-version-reference)

---

## 1. The decision: why Argo CD

Re-verified October 2026. The conclusion holds, and the reasons are stronger than they were a year ago.

### The evidence

| Signal | Value |
|---|---|
| CNCF end-user survey (July 2025) | Argo CD runs in **~60% of Kubernetes clusters** — the majority-adopted GitOps solution |
| Octopus *State of GitOps* | Flux at **~11%** |
| Project status | **Both** are CNCF Graduated. Neither is a risk |
| Governance | Flux stabilised under CNCF after the Weaveworks closure; Argo CD's commercial-support ecosystem is the more mature of the two |
| OpenShift | **OpenShift GitOps *is* Argo CD.** If the managed-OpenStack provider gives us OpenShift, Argo CD is the native path |

### Why it is right for *this* team

1. **The UI teaches Kubernetes.** This is the real argument, not a convenience. The resource tree shows every Pod, Job, Secret and CRD a chart produced, which one is unhealthy, and the live-vs-desired diff that explains why. Learning that from `flux get` output and `kubectl describe` is possible but much slower. For a team whose main constraint is Kubernetes fluency, the tool that explains the cluster wins.
2. **Adoption is help.** Roughly five times the cluster share means more tutorials, more answered questions, more colleagues who have already run it. When you are stuck at 17:00 this is worth more than any feature comparison.
3. **OpenShift alignment.** [[naturalis-kubernetes]] §6 plans for a provider-managed control plane, possibly OpenShift. OpenShift's supported GitOps product is Argo CD under the OpenShift GitOps operator. Choosing Argo CD now means that migration is a change of install method, not a change of tool.
4. **The GitLab gap is narrow and closable.** See §10. You lose a status widget and some GitLab-side deployment gating; you gain a far better dashboard, and the gating moves into Argo CD where it is arguably better placed.

### What you honestly give up

Be straight about this — it is the cost side of a decision that is still correct.

| Cost | Detail | Mitigation |
|---|---|---|
| GitLab's recommended path | GitLab documents Flux as its recommendation, and the agent auto-configures a Flux `Receiver` for push-triggered reconciliation | GitLab webhook → `/api/webhook` gets you the same instant sync (§10.3) |
| GitLab-native deployment gating | Protected Environments, Deployment Approvals, Deployment safety and Deployment rollback **do not apply** to external deployment tools | Move gating into Argo CD: manual sync + AppProject RBAC + SSO groups in production (§12) |
| More to operate | Five-plus components (API server, repo-server, application controller, ApplicationSet controller, notifications controller, Redis, optionally Dex) versus Flux's set of controllers; the repo-server is the component that attracts CVEs | Install via the Helm chart, let Argo CD manage itself, subscribe to release notes, patch promptly (§16) |
| Flux's signed-OCI-artifact flow | Flux `OCIRepository` plus signature verification is a genuinely nice supply-chain story | Argo CD supports OCI sources and OCI webhooks; verification is weaker. Keep Kyverno `verifyImages` at admission as the real control |

**Why GitLab picked Flux**, for the record: Flux reconciles through the standard Kubernetes API, so GitLab's agent can read its state generically. Argo CD exposes a custom API, which GitLab would have had to special-case. It is an integration-architecture reason, not a judgement about quality.

### The reassuring part

Your charts and values files are identical under either tool. Switching later means rewriting a thin layer of `Application` / `HelmRelease` wrappers, not starting over. This decision is far less permanent than it feels.

### Starting small — the recommended path

1. Install Argo CD with its Helm chart on the **development** cluster (§3).
2. One GitLab repo, a directory per service, each holding a pinned chart version plus the values file.
3. Deploy **one simple service** by clicking through the UI, to learn `Application`, sync, and health.
4. Then move the `Application` definitions into Git — app-of-apps first, then ApplicationSet (§6). Nothing may live only in the UI.
5. Airflow **after** that, with the chart settings in §13.1.
6. Decide two things early, because they are painful to retrofit: **secrets** (ESO + Vault — §11) and **auto vs manual sync** (automated in development, manual in production is the comfortable default).

---

## 2. Mental model

### The objects

| Object | Scope | What it is |
|---|---|---|
| `Application` | namespaced (`argocd`, or any permitted namespace) | A link between **one source** (Git path, Helm chart, or OCI artifact) and **one destination** (cluster + namespace) |
| `ApplicationSet` | namespaced | A template plus generators that produce many `Application`s. Replaces hand-maintained lists |
| `AppProject` | namespaced | The security boundary: which repos, which destinations, which resource kinds, which roles |

### The components

| Component | Job | Fails as |
|---|---|---|
| `argocd-repo-server` | Clones repos, renders manifests (`helm template`, `kustomize build`), caches by commit SHA | OOM kills, slow syncs, `ComparisonError` |
| `argocd-application-controller` | Compares desired to live, syncs, assesses health | CPU burn, slow reconciliation, stale status |
| `argocd-server` | API + UI + webhook endpoint | 503s, auth failures |
| `argocd-applicationset-controller` | Generates `Application`s | Applications not appearing, or churning |
| `argocd-notifications-controller` | Triggers and sends notifications (bundled in the standard install) | Silent — no GitLab deployment records |
| Redis | Cache for rendered manifests and cluster state | Everything slows down; a cold cache re-renders everything |

### The loop

```
Git (desired)  →  repo-server renders  →  controller diffs against live  →  sync applies
                                               │
                                               └─ selfHeal reverts manual drift
```

Three facts that explain most confusion:

- **Argo CD renders, it does not install.** Helm is used *only* to inflate charts with `helm template`. There is no Helm release; `helm ls` shows nothing. Argo CD owns the lifecycle.
- **Every operation is a "sync".** Argo CD cannot tell an install from an upgrade, which is why `pre-install` and `pre-upgrade` Helm hooks both run every time (§9.2).
- **Rendering has no cluster access.** Anything a chart derives from the live cluster (`lookup`, generate-a-password-once patterns) does not work the way the chart author intended. See §9.3.

---

## 3. Installation and bootstrap

### 3.1 Install with the Helm chart, pinned

```sh
helm repo add argo https://argoproj.github.io/argo-helm
helm repo update

helm upgrade --install argocd argo/argo-cd \
  --namespace argocd --create-namespace \
  --version 10.10.1 \
  --values argocd-values.yaml
```

Minimum values worth setting from day one:

```yaml
# argocd-values.yaml
global:
  domain: argocd.development.example.org

configs:
  params:
    # Terminate TLS at the gateway, not in argocd-server
    server.insecure: true
    # Bound concurrent manifest generations — the single most effective OOM guard (§15)
    reposerver.parallelism.limit: 10
  cm:
    # Prune the UI's resource tree and reduce API load; 3.0+ ships sane defaults, extend them
    resource.exclusions: |
      - apiGroups: ["cilium.io"]
        kinds: ["CiliumIdentity", "CiliumEndpoint", "CiliumEndpointSlice"]
        clusters: ["*"]
    # Ten minutes is plenty once webhooks are wired up (§10.3); default is 3 minutes
    timeout.reconciliation: 600s

server:
  # Publish through the cluster Gateway, not a LoadBalancer Service
  ingress:
    enabled: false

redis-ha:
  enabled: false        # true for the production cluster

controller:
  replicas: 1           # shard later, when application count justifies it (§15.3)

repoServer:
  replicas: 2
  resources:
    requests: {cpu: 250m, memory: 512Mi}
    limits:   {memory: 2Gi}      # kustomize/helm renders are memory-hungry (§15.1)

applicationSet:
  replicas: 1

notifications:
  enabled: true         # needed for GitLab deployment tracking (§10.2)

dex:
  enabled: true         # GitLab SSO via the Dex GitLab connector (§12.3)
```

Keep that values file in Git from the first install. The bootstrap is the one thing you apply by hand, exactly once.

### 3.2 Make Argo CD manage itself

The install above is imperative. Immediately replace it with an `Application` that manages Argo CD from Git, so upgrades become a version bump in a merge request:

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: argocd
  namespace: argocd
  annotations:
    argocd.argoproj.io/sync-wave: "-10"   # before everything else
spec:
  project: platform
  sources:
    - repoURL: https://gitlab.example.org/group/platform.git
      targetRevision: main
      ref: values
    - repoURL: https://argoproj.github.io/argo-helm
      chart: argo-cd
      targetRevision: 10.10.1             # pinned, never a range
      helm:
        valueFiles:
          - $values/clusters/development/argocd/values.yaml
  destination:
    server: https://kubernetes.default.svc
    namespace: argocd
  syncPolicy:
    automated:
      prune: false          # never let Argo CD prune itself
      selfHeal: true
    syncOptions:
      - ServerSideApply=true   # Argo CD's own CRDs are large (§8)
      - CreateNamespace=false
```

Two deliberate choices there: `prune: false` so a mistake in the platform repo cannot delete the controller that would fix it, and `ServerSideApply=true` because the `Application`/`ApplicationSet` CRDs exceed the annotation size limit.

### 3.3 Then a root Application per cluster

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: root-development
  namespace: argocd
spec:
  project: platform
  source:
    repoURL: https://gitlab.example.org/group/platform.git
    targetRevision: main
    path: clusters/development
  destination:
    server: https://kubernetes.default.svc
    namespace: argocd
  syncPolicy:
    automated: {prune: true, selfHeal: true}
```

`clusters/development/` contains the `ApplicationSet`s and platform `Application`s for that cluster. That single directory is the cluster's entire definition — the same rule as [[kubernetes]] §2.2.

### 3.4 Initial admin password

```sh
kubectl -n argocd get secret argocd-initial-admin-secret \
  -o jsonpath='{.data.password}' | base64 -d
argocd login argocd.development.example.org --username admin
```

Set up SSO (§12.3), then disable the local admin account (`configs.cm.admin.enabled: false`) and delete the secret. A shared `admin` login defeats the audit trail that is half the point of GitOps.

---

## 4. Repository layout

Follow [[kubernetes]] §2 — one directory per cluster, platform separated from apps, reconciled controllers → configs → apps. The Argo CD specifics:

```
clusters/
├── development/
│   ├── argocd/values.yaml          # Argo CD's own values (§3.2)
│   ├── platform.yaml               # ApplicationSet for platform/controllers
│   ├── platform-configs.yaml       # ApplicationSet for cluster-scoped CRs
│   └── apps.yaml                   # ApplicationSet for applications
├── acceptance/
└── production/
platform/
├── controllers/<name>/             # cert-manager, ESO, gateway, metrics-server, KEDA
└── configs/<name>/                 # ClusterIssuer, GatewayClass, StorageClass, PSA, NetworkPolicy
apps/
└── <app>/
    ├── base/
    └── overlays/{development,acceptance,production}/
projects/
└── *.yaml                          # AppProject definitions
```

### Keep config separate from application source

Argo CD's own best-practices doc gives five reasons, and all five are real: you can change manifests without triggering a build; the config repo's history is clean enough to audit; an application assembled from several source repos has nowhere else to live; **commit access to production config can be separated from commit access to application code**; and a CI job that commits manifests to the repo it builds from creates an infinite build loop.

For us the access-separation reason is decisive — it is what lets developers ship code without holding write access to production config.

### Pin every remote reference

Argo CD's docs are explicit: with templating tools a manifest **"can change its meaning from one day to the next"** because of an upstream change. Never `targetRevision: HEAD` on a chart. Never a Kustomize remote base without `?ref=`. Pin a chart version, a Git tag, or a commit SHA, and let Renovate propose the bumps.

```yaml
# Wrong — meaning can change overnight
resources:
  - github.com/argoproj/argo-cd//manifests/cluster-install

# Right
resources:
  - github.com/argoproj/argo-cd//manifests/cluster-install?ref=v3.5.4
```

As of v3.5.4 this is also a **security** rule: a Kustomize remote ref was the vector for a critical repo-server command-execution advisory (§16.1).

### Leave room for what you do not own

If HPA owns `replicas`, do not put `replicas` in Git — otherwise Argo CD and the HPA fight forever and the app is permanently `OutOfSync`. Omit the field, or `ignoreDifferences` it:

```yaml
spec:
  ignoreDifferences:
    - group: apps
      kind: Deployment
      jsonPointers: ["/spec/replicas"]
```

---

## 5. The Application resource

Annotated, with every decision explained:

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: my-app-production
  namespace: argocd
  finalizers:
    # Cascading delete: deleting the Application deletes its resources.
    # Omit this and you orphan everything the app created.
    - resources-finalizer.argocd.argoproj.io
  annotations:
    # Monorepo performance: only re-render when these paths change (§15.2)
    argocd.argoproj.io/manifest-generate-paths: /apps/my-app;/platform/common
spec:
  project: applications          # NEVER "default" in production (§12.1)
  source:
    repoURL: https://gitlab.example.org/group/platform.git
    targetRevision: main         # a tag for production promotion
    path: apps/my-app/overlays/production
  destination:
    server: https://kubernetes.default.svc
    namespace: my-app-production
  revisionHistoryLimit: 10       # rollback targets; the default 10 is fine
  syncPolicy:
    # Omit `automated` entirely for production → sync is a human click
    automated:
      prune: true                # delete resources removed from Git
      selfHeal: true             # revert manual changes to the cluster
      allowEmpty: false          # an empty render must not wipe the app
    syncOptions:
      - CreateNamespace=true
      - ServerSideApply=true
      - PruneLast=true           # prune after everything else is healthy
      - RespectIgnoreDifferences=true
    managedNamespaceMetadata:
      labels:
        pod-security.kubernetes.io/enforce: restricted
        pod-security.kubernetes.io/audit: restricted
        pod-security.kubernetes.io/warn: restricted
    retry:
      limit: 5
      backoff: {duration: 5s, factor: 2, maxDuration: 3m}
```

| Field | Why it is set that way |
|---|---|
| `finalizers` | Without it, `kubectl delete application` leaves every resource behind. This is the most common "why is this old Deployment still here" cause |
| `project` | The only security boundary that exists. `default` is unrestricted and can reach Argo CD's own RBAC ConfigMap |
| `prune: true` | Git is the source of truth; a deleted manifest must mean a deleted resource |
| `selfHeal: true` | Makes drift self-correcting. Combined with `kubectl edit` it means "your edit is reverted in ~seconds", which is the behaviour you want |
| `allowEmpty: false` | A broken render that produces zero manifests must not be read as "delete everything" |
| `managedNamespaceMetadata` | Puts the Pod Security Standards labels from [[naturalis-kubernetes]] §7 on the namespace declaratively. **Requires `CreateNamespace=true`** or it silently does nothing |
| `retry` | Transient admission-webhook and CRD-ordering failures resolve themselves on retry |
| `manifest-generate-paths` | In a monorepo, the manifest cache is keyed by commit SHA, so *any* commit invalidates *every* Application's cache. This annotation is the fix (§15.2) |

**`managedNamespaceMetadata` caveat**: if a `Namespace` manifest for the same name also exists in the Application, the manifest wins and overwrites everything `managedNamespaceMetadata` set. Pick one mechanism.

### Automated vs manual by tier

| Tier | Policy | Rationale |
|---|---|---|
| `development` | `automated: {prune: true, selfHeal: true}` | Fast feedback; free to break |
| `acceptance` | `automated: {prune: true, selfHeal: true}` | Should mirror production's content, not its gating |
| `production` | **no `automated` block** — sync is a click or `argocd app sync` | This is where the GitLab Deployment Approvals you gave up get replaced (§10.1) |

---

## 6. ApplicationSet

Hand-maintained lists of applications rot within a month. Use a generator.

### 6.1 Git directory generator — one Application per directory

```yaml
apiVersion: argoproj.io/v1alpha1
kind: ApplicationSet
metadata:
  name: apps-development
  namespace: argocd
spec:
  goTemplate: true
  goTemplateOptions: ["missingkey=error"]   # fail loudly on a typo'd variable
  generators:
    - git:
        repoURL: https://gitlab.example.org/group/platform.git
        revision: main
        directories:
          - path: "apps/*/overlays/development"
  template:
    metadata:
      name: '{{ index (splitList "/" .path.path) 1 }}-development'
      finalizers:
        - resources-finalizer.argocd.argoproj.io
    spec:
      project: applications           # HARD-CODED — see §6.3
      source:
        repoURL: https://gitlab.example.org/group/platform.git
        targetRevision: main
        path: '{{ .path.path }}'
      destination:
        server: https://kubernetes.default.svc
        namespace: '{{ index (splitList "/" .path.path) 1 }}-development'
      syncPolicy:
        automated: {prune: true, selfHeal: true, allowEmpty: false}
        syncOptions: [CreateNamespace=true, ServerSideApply=true]
  # Keep resources when an Application disappears from the generator?
  # Default is to delete them. Leave the default unless you have a reason.
  # preserveResourcesOnDeletion: false
```

Notes: directories beginning with `.` are excluded automatically; use `exclude` to skip `base/`; `path.basenameNormalized` substitutes unsupported characters with `-`.

### 6.2 Always set `goTemplate` and `missingkey=error`

Without `goTemplateOptions: ["missingkey=error"]`, a mistyped variable renders as an empty string. An empty string in `destination.namespace` or `source.path` produces an Application that points somewhere unintended, silently. This one line turns a silent misdeploy into a loud failure.

### 6.3 Security: ApplicationSet is an admin-only tool

Straight from the Argo CD docs, and all three points are load-bearing:

1. **Only admins may create, update or delete `ApplicationSet`s** (via Kubernetes RBAC). ApplicationSets can create Applications under *arbitrary* Projects — including `default`, which often has enough permission to modify Argo CD's own RBAC ConfigMap. They can also create and delete an arbitrary number of Applications very quickly.
2. **Never template the `project` field.** A user with push access to the generator's source could then create an Application under an unrestricted Project and take control of Argo CD. If `project` is not hard-coded, admins *must* control every source of truth the generators read.
3. **The git generator can read Secrets in the `argocd` namespace** and send them as auth headers to whatever URL the `api` field names. It exists for SCM-provider auth; it can be abused.

Practical consequence for us: the platform repo's `clusters/` and `projects/` directories get `CODEOWNERS` requiring platform review. Application directories under `apps/` can be owned by their teams, because the generator's template — including `project` — is not theirs to change.

### 6.4 app-of-apps vs ApplicationSet

app-of-apps (a root `Application` whose manifests are child `Application`s) is the simpler concept and the right first step at stage 4 of §1. ApplicationSet is strictly better once you have more than a handful of apps: no ordering assumptions, no commits needed to add an app, and generators that follow the directory structure. Use app-of-apps for the **platform root** (a short, deliberate, hand-written list) and ApplicationSet for **applications** (many, repetitive, auto-discovered).

---

## 7. Sync phases, waves and hooks

This section explains most "why is my sync stuck" questions.

### 7.1 Phases

| Hook | When |
|---|---|
| `PreSync` | Before any manifest is applied. Failure stops the whole sync |
| `Sync` | Alongside the main apply |
| `Skip` | Do not apply this manifest at all |
| `PostSync` | After all `Sync` hooks succeeded, the apply succeeded, **and all resources are `Healthy`** |
| `SyncFail` | When the sync fails — cleanup and housekeeping |
| `PreDelete` | Before Application resources are deleted. Only on Application deletion, **not** on a pruning sync |
| `PostDelete` | After all Application resources are deleted |

```yaml
metadata:
  annotations:
    argocd.argoproj.io/hook: PreSync
    argocd.argoproj.io/hook-delete-policy: HookSucceeded
```

`hook-delete-policy` values: `HookSucceeded`, `HookFailed`, `BeforeHookCreation`. **If you set no policy, Argo CD assumes `BeforeHookCreation`** — the old hook is deleted before the new one is created.

Two behaviours worth knowing before you need them:

- **Hooks do not run during a selective sync.** Syncing a single resource from the UI skips them, which is a fine debugging tool and a terrible deploy habit.
- **A failing `PreDelete` hook blocks Application deletion.** The Application sits in a deleting state with a `DeletionError` condition until the hook succeeds or you delete the hook resource by hand.

### 7.2 Waves

`argocd.argoproj.io/sync-wave: "-1"` — an integer, default `0`, negatives allowed. Argo CD applies lowest to highest.

The full ordering precedence is: **phase → wave → kind → name**. Within a phase, Argo CD finds the first wave containing anything out-of-sync or unhealthy, applies that wave, waits for health, and repeats.

Three mechanics that explain real incidents:

- **There is a 2-second delay between waves** (`ARGOCD_SYNC_WAVE_DELAY`). It exists to let other controllers react before Argo CD assesses health against a stale object. Many waves make syncs noticeably slower — do not use waves as a general-purpose ordering tool.
- **Pruning reverses wave order.** Higher waves are pruned first. If pruning fails in a wave, lower waves are not processed at all.
- **An unhealthy resource in an early wave means the app can never reach `Healthy`.** If a sync is stuck, find the lowest-numbered unhealthy resource; everything after it is blocked, not broken.

### 7.3 Our wave convention

Ordering `controllers → configs → apps` from [[kubernetes]] §2.3, expressed in waves:

| Wave | Contents |
|---|---|
| `-10` | Argo CD itself, AppProjects |
| `-5` | CRDs and controllers: cert-manager, External Secrets Operator, gateway controller, metrics-server |
| `-3` | Cluster-scoped CRs: `ClusterIssuer`, `GatewayClass`, `StorageClass`, `ClusterSecretStore` |
| `-1` | Namespaces, `ExternalSecret`s, database migrations (`PreSync`) |
| `0` | Application workloads (the default) |
| `1` | `HTTPRoute`s, `ServiceMonitor`s, smoke tests (`PostSync`) |

The `-1` wave for `ExternalSecret` is the one people miss: a Deployment mounting a Secret that ESO has not created yet sits in `ContainerCreating` and the app never goes healthy. See §11.2.

---

## 8. Sync options that solve real failures

Set on `spec.syncPolicy.syncOptions` (whole Application) or the `argocd.argoproj.io/sync-options` annotation (one resource, comma-separated).

| Option | Solves |
|---|---|
| `ServerSideApply=true` | **`metadata.annotations: Too long: must have at most 262144 bytes`.** The biggest one — see below |
| `CreateNamespace=true` | Sync fails because `spec.destination.namespace` does not exist. Also required for `managedNamespaceMetadata` |
| `Replace=true` | A resource `kubectl apply` cannot patch. **Destructive** — uses `kubectl replace`/`create` and may force a recreate |
| `Force=true,Replace=true` | A Job you want deleted and recreated on every sync |
| `PruneLast=true` | Prune only after everything else is healthy — avoids deleting the old thing before the new thing works |
| `Prune=false` | Protect a resource from pruning (the app shows `OutOfSync` as a reminder) |
| `Prune=confirm` / `Delete=confirm` | Require a human to confirm before pruning/deleting something critical like a Namespace. Confirm in the UI/CLI or annotate `argocd.argoproj.io/deletion-approved: <ISO timestamp>` |
| `Delete=false` | Keep a resource (a PVC, say) when the Application is deleted |
| `ApplyOutOfSyncOnly=true` | Apps with thousands of objects: only apply what changed. Reduces API-server load and `status` size. Hooks still run |
| `PrunePropagationPolicy=foreground` | Control deletion propagation (`background`, `foreground`, `orphan`); `foreground` is the default |
| `Validate=false` | Resources using `RawExtension`, or an intentionally partial manifest |
| `SkipDryRunOnMissingResource=true` | `the server could not find the requested resource` — a CR whose CRD is created by a controller rather than by this sync (Gatekeeper, Kyverno) |
| `FailOnSharedResource=true` | Catch two Applications fighting over the same object. Worth enabling on a shared cluster |
| `RespectIgnoreDifferences=true` | Make `ignoreDifferences` apply **during sync**, not just during diffing. Without it, the desired state is applied as-is and your ignored field gets overwritten anyway |

### The annotation-size failure, in full

Symptom:

```
metadata.annotations: Too long: must have at most 262144 bytes
```

Cause: client-side `kubectl apply` stores a full copy of the object in the `kubectl.kubernetes.io/last-applied-configuration` annotation. That copy counts against Kubernetes' 256 KiB annotation limit. Large objects — cert-manager CRDs, Prometheus Operator CRDs, Gateway API CRDs, Grafana dashboard ConfigMaps — blow past it and the API server rejects them.

Fix: `ServerSideApply=true`. Server-side apply records ownership in `metadata.managedFields`, so nothing lands in annotations and the limit never applies.

```yaml
spec:
  syncPolicy:
    syncOptions:
      - ServerSideApply=true
```

Two caveats: **`Replace=true` takes precedence over `ServerSideApply=true`** (so do not set both and expect SSA), and when adopting an existing client-side-applied resource, upgrade it to server-side apply first or labels and annotations may be dropped. Argo CD's `ClientSideApplyMigration` handles this automatically and is enabled by default.

Practical advice: set `ServerSideApply=true` on every platform Application that ships CRDs. It costs nothing and removes a whole class of failure.

---

## 9. Helm under Argo CD

### 9.1 Value precedence

```
lowest   valueFiles
         values
         valuesObject
highest  parameters
```

And within `valueFiles`, **the last file listed wins**. `valuesObject` is the readable choice for inline values; `parameters` is the escape hatch that beats everything.

Multi-source Applications let you use an upstream chart with your own Git-hosted values — the pattern you want for almost every platform component:

```yaml
spec:
  sources:
    - repoURL: https://charts.example.org
      chart: some-chart
      targetRevision: 1.4.2
      helm:
        valueFiles:
          - $values/clusters/production/some-chart/values.yaml
    - repoURL: https://gitlab.example.org/group/platform.git
      targetRevision: main
      ref: values          # maps to $values
```

Rules: `$values` resolves to the **root** of the referenced source and may only appear at the start of the path; a source with `ref` set cannot also set `chart`; and if more than 2–3 entries appear in `sources` you are abusing the feature and should be using ApplicationSet or app-of-apps instead. If two sources produce the same resource, **the last one wins** and Argo CD logs a `RepeatedResourceWarning`.

`valueFiles` also supports globs (`envs/*.yaml`), expanded in lexical order — so numeric prefixes (`00-defaults.yaml`, `10-region.yaml`) are the way to make precedence explicit. A glob matching nothing raises a `ComparisonError` unless you add `ignoreMissingValueFiles: true`.

### 9.2 Helm hooks are mapped, not emulated

| Helm | Argo CD |
|---|---|
| `pre-install`, `pre-upgrade` | `PreSync` |
| `post-install`, `post-upgrade` | `PostSync` |
| `pre-delete` | `PreDelete` |
| `post-delete` | `PostDelete` |
| `hook-weight` | `sync-wave` |
| `resource-policy: keep` | `sync-options: Delete=false` |
| `pre-rollback`, `post-rollback`, `test-success`, `test-failure` | **Not supported** — ignored |

Three warnings that matter more than the table:

- **If you define *any* Argo CD hook on a resource, *all* Helm hooks are ignored.** Mixing the two systems on one chart does not work.
- **Argo CD cannot tell install from upgrade** — every operation is a sync, so `pre-install` and `pre-upgrade` hooks both run, every time.
- **Delete semantics differ from Helm's.** Policies are evaluated against Argo CD sync phases and sync results, not Helm's per-hook-event lifecycle. A passive resource like a `ServiceAccount` has no completion state, so `HookSucceeded` fires at a different moment than Helm would.

### 9.3 What breaks because rendering has no cluster

- **`randAlphaNum` and friends** regenerate on every comparison, so the app is **permanently `OutOfSync`**. Fix by setting the value explicitly in values (`-p password=...` or a values file), or better, source it from Vault via ESO (§11).
- **Helm `lookup`** has no cluster to query during `helm template`, so charts that "generate a password once and reuse the existing Secret" cannot see the existing Secret. Treat any chart doing this as needing an explicit, externally-managed secret.
- **`.Capabilities`-gated templates** may render against different API versions than you expect. Verify the rendered output (`argocd app manifests <app>`) rather than assuming.

### 9.4 Helm binary version

Argo CD **3.5 renders charts with the Helm v4 binary**. The `spec.source.helm.version` field is legacy and ignored; leaving it set is harmless. Two consequences: charts must be `apiVersion: v2`, and a `null` object in a subchart's `values.yaml` now overrides the rendered object with `null` instead of warning and ignoring it (a Helm 3.17.1+ behaviour change). If a chart suddenly renders a `null` field after an Argo CD upgrade, look for `null` values in your values files.

---

## 10. GitLab integration: what works and what does not

The honest answer to "is there really no way to make the GitLab integration work with Argo CD": **most of it works, one part does not, and the part that does not is replaceable.**

### 10.1 The scorecard

| GitLab feature | With Argo CD | How |
|---|---|---|
| Deployment records on environments, MR "deployed to" widget | **Yes** | Argo CD notifications → GitLab Deployments API (§10.2) |
| DORA metrics | **Yes** | Same mechanism — DORA reads deployment records |
| Filter MRs by environment / deployment date | **Yes** | Same mechanism |
| Track newly included MRs per deployment | **Yes** | Same mechanism |
| Instant sync on push | **Yes** | GitLab webhook → `/api/webhook` (§10.3) |
| Kubernetes dashboard in GitLab | **Yes** | Agent + `user_access`. It works for **any** connected cluster regardless of GitOps tool; the Flux resource dropdown is optional |
| Cluster access from CI jobs | **Yes** | The agent, unchanged. Outbound-only, no inbound 6443 |
| SSO with GitLab identities | **Yes** | Dex GitLab connector (§12.3) |
| Repo credentials | **Yes** | Deploy token or project access token (§10.4) |
| **Protected Environments** | **No** | GitLab cannot authorize an external deployment |
| **Deployment Approvals** | **No** | Replace with manual sync + AppProject RBAC (§12) |
| **Deployment safety / rollback from GitLab** | **No** | Use `argocd app rollback`, or revert the commit |

So: the dashboards, metrics, environment tracking, cluster access and SSO all work. What you genuinely lose is **GitLab-side gating of deployments**. That moves into Argo CD, where production Applications have no `automated` policy and only an SSO group with sync permission can press the button. For a team of our size that is arguably a better place for it, because it is the same button for every cluster regardless of which repo the change came from.

### 10.2 Deployment tracking — the verified configuration

Argo CD's notifications controller posts to GitLab's Deployment API. This is GitLab's own documented example for Argo CD:

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: argocd-notifications-cm
  namespace: argocd
data:
  trigger.on-deployed: |
    - description: Application is synced and healthy. Triggered once per commit.
      oncePer: app.status.sync.revision
      send:
        - gitlab-deployment-status
      when: app.status.operationState.phase in ['Succeeded'] and app.status.health.status == 'Healthy'
  template.gitlab-deployment-status: |
    webhook:
      gitlab:
        method: POST
        path: /projects/<project-id>/deployments
        body: |
          {
            "status": "success",
            "environment": "production",
            "sha": "{{.app.status.operationState.operation.sync.revision}}",
            "ref": "main",
            "tag": "false"
          }
  service.webhook.gitlab: |
    url: https://gitlab.example.org/api/v4
    headers:
      - name: PRIVATE-TOKEN
        value: $gitlab-token          # from a Secret, never inline
      - name: Content-type
        value: application/json
```

Subscribe an Application to it:

```yaml
metadata:
  annotations:
    notifications.argoproj.io/subscribe.on-deployed.gitlab: ""
```

Four things to get right:

- **`oncePer: app.status.sync.revision`** — without it you get a deployment record on every reconciliation, not every commit.
- **The token goes in a Secret.** Use `$gitlab-token` referencing `argocd-notifications-secret`, and populate that Secret from Vault via ESO. A project access token pasted into a ConfigMap is a finding waiting to happen.
- **`url` is our self-managed instance**, not `gitlab.com` — the `$CI_SERVER_FQDN` convention from [[naturalis-kubernetes]] §2.
- **Report failures too.** Add an `on-sync-failed` trigger posting `"status": "failed"`, or GitLab's environment view will only ever show successes.

Debug with:

```sh
argocd admin notifications template notify \
  gitlab-deployment-status <app-name> --recipient gitlab:argocd-notifications
```

That fires the request immediately and prints GitLab's error response, which is far faster than reading controller logs.

### 10.3 Instant sync: the GitLab webhook

Argo CD polls Git every three minutes by default. Replace that with a push trigger:

1. GitLab project → **Settings → Webhooks**. URL `https://argocd.example.org/api/webhook`, push events, a secret value.
2. Store the secret:

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: argocd-secret
  namespace: argocd
stringData:
  webhook.gitlab.secret: <the same value>
```

3. Then raise `timeout.reconciliation` in `argocd-cm` (600s is comfortable) so you are not paying for polling you no longer need.

**`timeout.reconciliation` only governs `Application` refresh.** ApplicationSet generators are a separate loop with a separate interval — the git generator requeues on the applicationset-controller's own schedule (default 3 minutes, `requeueAfterSeconds` on PR and SCM generators), and it needs its **own** webhook configuration pointed at the applicationset-controller. Raising `timeout.reconciliation` does not slow generator discovery down, but it also does not speed it up: if a new directory in the monorepo should become an Application immediately, configure the ApplicationSet webhook too, not just the Application one.

Notes: the webhook secret is optional but recommended if Argo CD is publicly reachable — `/api/webhook` has no rate limiting, so bound the payload with `webhook.maxPayloadSizeMB` (default 50). ApplicationSet git generators need their **own** webhook configuration; the Application webhook does not cover them. And the handler cannot distinguish a push to branch `x` from a push to tag `x`, so an app on `targetRevision: refs/tags/x` refreshes on branch pushes too.

**If your GitLab sits behind a VPN or a private network, check the path before configuring any of this.** The webhook is an outbound call *from* GitLab *to* the Argo CD server, so GitLab must be able to reach it. A self-managed GitLab on a private network and a cluster reachable only from inside that network is a common combination where it simply cannot. If the path does not exist, keep polling and accept the three-minute delay — it is not worth exposing the Argo CD server to fix. See [[naturalis-kubernetes]] §2 for our own network topology.

### 10.4 Repository credentials

Use a GitLab **deploy token** (read-only, repo-scoped) rather than a personal token:

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: repo-platform
  namespace: argocd
  labels:
    argocd.argoproj.io/secret-type: repository
stringData:
  type: git
  url: https://gitlab.example.org/group/platform.git
  username: <deploy-token-username>
  password: <deploy-token>
```

The `argocd.argoproj.io/secret-type: repository` label is what makes Argo CD pick it up. Populate it from Vault with ESO — never commit it.

**Argo CD 3.0 removed legacy repository configuration from `argocd-cm`.** Repositories are Secrets now. If you are following an old blog post that edits `argocd-cm`, stop. Check with:

```sh
kubectl get cm argocd-cm -n argocd \
  -o=jsonpath="[{.data.repositories}, {.data['repository\.credentials']}, {.data['helm\.repositories']}]"
# "[, , ]" means you are clean
```

### 10.5 What the GitLab agent is still for

Install it anyway. With Argo CD it still provides: the Kubernetes dashboard in GitLab (needs `user_access`), `$KUBECONFIG`/`$KUBE_CONTEXT` in CI jobs for validation and `kubectl diff` gates, and outbound-only cluster access with no inbound 6443 rule. See [[kubernetes]] §5 and [[naturalis-kubernetes]] §2 for the `kasAddress` configuration, which is the usual installation mistake.

What you do **not** use is the agent's Flux `Receiver` auto-detection — that is Flux-specific, and §10.3 is the Argo CD equivalent.

---

## 11. Secrets

### 11.1 External Secrets Operator, not a plugin

Two options exist; only one is right for us.

| Approach | Verdict |
|---|---|
| **External Secrets Operator + Vault** | **Use this.** Vendor-neutral, declarative, works identically under any GitOps tool, and survives a migration to OpenShift or a different controller |
| `argocd-vault-plugin` | Avoid. It is a config-management plugin, so secrets are injected at render time inside the repo-server — which couples your secret path to Argo CD, puts Vault credentials in the most CVE-exposed component, and breaks the day you change controllers |

Follow [[kubernetes]] §12 for ESO generally and [[naturalis-kubernetes]] §1 for our `ClusterSecretStore`, its Vault address and auth role — including the `serviceAccountRef`-or-`secretRef`-never-both rule and the mandatory namespace on a `ClusterSecretStore`.

### 11.2 Ordering is the Argo CD–specific part

An `ExternalSecret` is a request, not a Secret. ESO must be running, and the Secret must exist, before anything mounts it.

```yaml
# ESO itself
metadata:
  annotations:
    argocd.argoproj.io/sync-wave: "-5"
---
# The ClusterSecretStore (a CR — needs ESO's CRDs to exist first)
metadata:
  annotations:
    argocd.argoproj.io/sync-wave: "-3"
---
# ExternalSecrets
metadata:
  annotations:
    argocd.argoproj.io/sync-wave: "-1"
---
# Workloads: wave 0 (default)
```

Symptom when you get this wrong: pods stuck in `ContainerCreating` with `secret "x" not found`, the Application never reaching `Healthy`, and — because `PostSync` hooks wait for health — any smoke test never running. The error points at the workload; the cause is two waves earlier.

### 11.3 Also

- Argo CD's **own** secrets (`argocd-secret` webhook keys, repository credentials, notification tokens, Dex client secret) belong in Vault and arrive via ESO like everything else. Bootstrapping is the exception: the very first install needs the repo credential to exist before Argo CD can sync the thing that creates repo credentials. Create it once by hand, then manage it declaratively.
- Argo CD **redacts secret values in the UI** by default. Do not disable that to debug; use `kubectl` with a deliberate audit trail.
- A `Secret` managed by ESO will show as `OutOfSync` if you also define it in Git. Define it in exactly one place.

---

## 12. Projects, RBAC and SSO

### 12.1 AppProject is the security boundary

`default` is unrestricted. An Application in `default` can deploy any kind to any namespace from any repo — including Argo CD's own RBAC ConfigMap. Never use it for anything real.

```yaml
apiVersion: argoproj.io/v1alpha1
kind: AppProject
metadata:
  name: applications
  namespace: argocd
spec:
  description: Application workloads
  sourceRepos:
    - https://gitlab.example.org/group/platform.git
  destinations:
    - server: https://kubernetes.default.svc
      namespace: '*-development'
    - server: https://kubernetes.default.svc
      namespace: '*-production'
  # Applications may not create cluster-scoped resources at all
  clusterResourceWhitelist: []
  namespaceResourceBlacklist:
    - {group: "", kind: ResourceQuota}
    - {group: "", kind: LimitRange}
    - {group: networking.k8s.io, kind: NetworkPolicy}
  roles:
    - name: deployer
      policies:
        - p, proj:applications:deployer, applications, sync, applications/*, allow
        - p, proj:applications:deployer, applications, get, applications/*, allow
      groups:
        - <group>/<subgroup>/platform    # a GitLab group path, from SSO (§12.3)
```

Two deliberate choices: applications cannot create cluster-scoped resources (that is the platform project's job), and they cannot set their own `ResourceQuota`, `LimitRange` or `NetworkPolicy` — otherwise the per-namespace baseline in [[naturalis-kubernetes]] §7 is advisory rather than enforced.

Keep a separate `platform` project with the wider permissions the controllers genuinely need, and a `CODEOWNERS` rule on `projects/`.

### 12.2 RBAC changes in 3.x you must know

| Change | Effect |
|---|---|
| **Logs RBAC enforced by default** | The `logs` tab is invisible without an explicit `logs, get` policy. The old `server.rbac.log.enforce.enable` flag is gone |
| **Fine-grained RBAC no longer inherits to sub-resources** | `update`/`delete` on an application no longer implies it on the application's managed resources. Add `update/*` and `delete/*` policies, or set `server.rbac.disableApplicationFineGrainedRBACInheritance: false` to restore v2 behaviour |
| **Dex subject changed** | RBAC subjects now come from `federated_claims.user_id`, not the opaque Dex `sub`. Policies written against a base64 `sub` string must be rewritten to the plain identity |

Grant logs explicitly per role rather than globally — it is the difference between least privilege and a readonly role that can read every Secret-bearing pod's output:

```
p, role:developer, applications, get, applications/*, allow
p, role:developer, logs, get, applications/*, allow
```

### 12.3 SSO with GitLab via Dex

Use the Dex **GitLab connector** rather than generic OIDC: it maps GitLab groups and subgroups into claims you can write RBAC against, which generic OIDC does not do as cleanly. It works against a self-managed instance via `baseURL`.

```yaml
# argocd-cm
dex.config: |
  connectors:
    - type: gitlab
      id: gitlab
      name: GitLab
      config:
        baseURL: https://gitlab.example.org
        clientID: $dex.gitlab.clientId
        clientSecret: $dex.gitlab.clientSecret
        redirectURI: https://argocd.example.org/api/dex/callback
        useLoginAsID: false
        groups:
          - <group>/<subgroup>      # restrict sign-in to these GitLab groups
```

Then map groups to roles in `argocd-rbac-cm`:

```yaml
policy.default: role:readonly
policy.csv: |
  g, <group>/<subgroup>/platform, role:admin
  g, <group>/<subgroup>/developers, role:developer
  p, role:developer, applications, get, applications/*, allow
  p, role:developer, applications, sync, applications/*-development, allow
  p, role:developer, logs, get, applications/*, allow
```

Register the application in GitLab under **Settings → Applications** with the `read_user`, `openid` and `profile` scopes. Put `clientID`/`clientSecret` in `argocd-secret` via ESO.

`policy.default: role:readonly` means an authenticated colleague can look at the cluster and learn from it without being able to change it — which is exactly the property that made Argo CD the right choice in §1. Make it easy for people to log in and look.

---

## 13. Per-chart gotchas

### 13.1 Airflow — the known gotcha, in full

The official chart's jobs use Helm hooks, which Argo CD handles differently. The chart's documentation is explicit: when installing with Argo CD, Flux or Terraform you **must** set all four of these, or **the application will not start because the migrations never run**:

```yaml
createUserJob:
  useHelmHooks: false
  applyCustomEnv: false
migrateDatabaseJob:
  useHelmHooks: false
  applyCustomEnv: false
  # Without this, migrations never run automatically at all:
  jobAnnotations:
    "argocd.argoproj.io/hook": Sync
```

The two `applyCustomEnv: false` settings are the half that most summaries omit. They exist to preserve the immutability of Kubernetes Job manifests so the GitOps controller can update without conflict. The same requirement applies if you ever run `helm install --wait`.

On `migrateDatabaseJob.jobAnnotations`: `Sync` means migrations run on **every** sync event. That is not ideal, and the chart's docs say so — it is the accepted trade-off for having them run automatically at all. The alternative is `PreSync` plus `hook-delete-policy: BeforeHookCreation`, which is more correct in principle and more fragile when a migration is slow (the whole sync blocks).

Everything else about running Airflow is in [[kubernetes]] §15.1 and [[airflow]] — in particular `workers.kubernetes.safeToEvict`, keeping the metadata database **outside** the cluster, and PgBouncer.

### 13.2 ingress-nginx admission webhook

A sync that hangs on `waiting for completion of hook batch/Job/ingress-nginx-admission-create`, with the Job `Pending deletion`. Documented workaround:

```yaml
ingress-nginx:
  controller:
    admissionWebhooks:
      annotations:
        argocd.argoproj.io/hook: Skip
```

### 13.3 Large CRDs: cert-manager, Prometheus Operator, Gateway API

All of them exceed the annotation limit. Set `ServerSideApply=true` on the Application (§8). For Prometheus Operator specifically, also expect its high-churn resources to generate diff noise — Argo CD 3.0's default `resource.exclusions` and `ignoreResourceUpdates` already cover most of it, so do not blindly delete those defaults when extending the ConfigMap.

### 13.4 Charts that generate secrets

Anything using `randAlphaNum` or `lookup` (older Redis, Grafana, Keycloak charts) will be permanently `OutOfSync` or will rotate a password on every sync. Set the value explicitly from a Vault-backed Secret and pass the chart `existingSecret` where it offers one. See §9.3.

### 13.5 Kyverno, Gatekeeper and other CR-generating controllers

Their custom resources may be created by a controller rather than by your sync, so Argo CD's dry run fails with `the server could not find the requested resource`. Add `SkipDryRunOnMissingResource=true`.

### 13.6 Cilium

Cilium's identity and endpoint objects are high-churn and will swamp the UI and the controller. Argo CD 3.0 excludes `CiliumIdentity`, `CiliumEndpoint` and `CiliumEndpointSlice` by default — keep those exclusions.

---

## 14. Daily operations

```sh
# Install and log in
brew install argocd
argocd login argocd.development.example.org --sso

# Inspect
argocd app list
argocd app get my-app
argocd app diff my-app                  # desired vs live — the review tool
argocd app manifests my-app             # exactly what will be applied
argocd app logs my-app --follow
argocd app resources my-app

# Act
argocd app sync my-app                  # production's deliberate button
argocd app sync my-app --dry-run
argocd app sync my-app --prune
argocd app rollback my-app <history-id>
argocd app history my-app

# Emergency: stop the controller fighting you while you fix the cause
argocd app set my-app --sync-policy none
# ...fix, commit, then restore
argocd app set my-app --sync-policy automated --self-heal --auto-prune

# Admin
argocd admin notifications trigger run on-deployed my-app
```

### Drift and rollback discipline

- **`OutOfSync` is a bug to diagnose, not a state to accept.** Read the diff first; it names the field and the owner.
- **A `Progressing` app is not necessarily broken** — find the lowest unhealthy wave (§7.2).
- **`argocd app rollback` is for incidents, not deploys.** It makes the cluster disagree with Git, which is drift by definition. Use it to stop the bleeding, then revert the commit so Git matches reality again. If you forget the second step, the next sync undoes your rollback.
- **Suspending auto-sync is the right emergency move**, and it must be followed by restoring it. An Application left on `sync-policy none` is an invisible landmine; alert on it ([[kubernetes]] §13.2).

---

## 15. Scaling and tuning

Mostly irrelevant at ten applications, and exactly what you will wish you had read at a hundred.

### 15.1 repo-server OOM

The repo-server forks `helm`/`kustomize` processes to render manifests. Each Kustomize render costs roughly 80 MB; ten concurrent refreshes spike memory enough to trigger the OOM killer, and OOM kills look like slow syncs and `ComparisonError`s rather than like memory problems.

| Lever | Setting |
|---|---|
| Bound concurrency | `reposerver.parallelism.limit: 10` (the `--parallelismlimit` flag) — **do this first** |
| Scale horizontally | `repoServer.replicas: 2+` |
| Help the Go GC | `GOMEMLIMIT` just under the memory limit |
| Shrink the problem | Smaller repos, shallower clones, fewer giant rendered outputs |

### 15.2 The monorepo cache trap

Argo CD caches rendered manifests **keyed by commit SHA**. In a monorepo, *any* commit changes the SHA and therefore invalidates the cache for *every* Application in that repo — so a one-line change to a README re-renders a hundred apps.

The fix is the `manifest-generate-paths` annotation, which tells Argo CD which paths actually affect this Application:

```yaml
metadata:
  annotations:
    argocd.argoproj.io/manifest-generate-paths: /apps/my-app;/platform/common
```

Put it in your ApplicationSet template so every generated app gets it. This is the single highest-value tuning annotation for the layout in §4.

### 15.3 Controller sharding

With many applications across many clusters, shard the application controller (`controller.replicas` plus a sharding algorithm) so each replica reconciles a subset. Three shards over 500 applications means each handles ~170 instead of all 500, and per-shard memory drops accordingly. Not needed for a single cluster with tens of apps — revisit when reconciliation latency becomes visible.

### 15.4 Reconciliation and webhooks

Default poll is three minutes. With the GitLab webhook wired up (§10.3), raise `timeout.reconciliation` to 600s or more: you get faster syncs *and* less load, because pushes trigger refreshes and the timer becomes a safety net rather than the mechanism.

Two things this does **not** cover, both from §10.3: ApplicationSet generators run on their own requeue interval and need their own webhook, and the whole trade only works if GitLab can actually reach the Argo CD server. Without a working webhook, leave the default — a 600s timer with no push trigger means up to ten minutes of unexplained lag, which is worse than three.

### 15.5 Metrics worth alerting on

Beyond the generic list in [[kubernetes]] §13.2:

| Alert | Catches |
|---|---|
| `argocd_app_info` with `sync_status="OutOfSync"` for > 15 min | Drift, or a sync that cannot converge |
| `argocd_app_info` with `health_status="Degraded"` | A broken deploy |
| Auto-sync disabled on an Application | A forgotten emergency suspension |
| repo-server restart count rising | OOM (§15.1) |
| Reconciliation duration p99 climbing | Time to tune §15.2 or shard |

Note for dashboards built before 3.0: `argocd_app_sync_status`, `argocd_app_health_status` and `argocd_app_created_time` were **removed**. The information is now labels on `argocd_app_info`.

---

## 16. Security and upgrades

### 16.1 Patch promptly — the repo-server is the attack surface

**v3.5.4 (6 October 2026) fixed four CRITICAL advisories**, every one of them in manifest rendering:

| Advisory | Issue |
|---|---|
| GHSA-9v9p-x54c-58gc | A Kustomize **remote ref** can run commands in the repo-server |
| GHSA-fw5c-w8rc-j7fx | A Kustomize **Helm config home** can run commands in the repo-server |
| GHSA-m3vr-7329-44ww | A **Jsonnet import** can read files from the repo-server |
| GHSA-fmxq-cgp8-87wp (CVE-2026-77459) | **AppProject restrictions bypassed** via PreDelete/PostDelete resource hooks |

Plus HIGH severity: login rate-limit bypass via concurrent requests (CVE-2025-61560) and command injection via a repository proxy URL on SSH Git repositories (CVE-2026-55797).

Read that list as a design statement: **the repo-server executes untrusted templating input**, so whoever can influence what it renders is close to code execution inside it. Three consequences for how we run it:

1. **Run a current patch release.** Pin the chart version in Git, let Renovate open the bump, and treat Argo CD patches as security work, not chores.
2. **Control what the repo-server renders.** Pinned refs (§4), no remote Kustomize bases you do not control, admin-only ApplicationSets (§6.3), and `sourceRepos` restricted per AppProject (§12.1).
3. **Give it a tight `securityContext` and NetworkPolicy.** It needs Git, Helm repos and the registry; nothing else. A default-deny namespace policy plus explicit egress is the control that limits the blast radius of the next advisory.

Two potentially-breaking changes also landed in 3.5.4: Kustomize builds rendering Helm charts no longer honour `helmGlobals.configHome` (ordinary `http`/`https`/`oci` chart repos still work; Helm plugins registered from that directory do not), and OCI manifests larger than 4 MiB are now rejected.

### 16.2 Upgrading

Read the version-specific upgrade guide every time; Argo CD's are genuinely good. Patch releases are cut for the two most recent minor versions.

If you are inheriting anything on 2.x, the 3.0 changes that will surprise you:

| Change | Action |
|---|---|
| Annotation-based resource tracking is the default | Usually safe. But if any Application uses `ApplyOutOfSyncOnly=true` with label tracking, sync it explicitly right after the upgrade or you orphan resources. Opt out with `application.resourceTrackingMethod: label` |
| Logs RBAC enforced; fine-grained RBAC no longer inherits | §12.2 |
| Legacy repo config removed from `argocd-cm` | §10.4 |
| Health status no longer persisted in the Application CR | Anything parsing `.status.resources[].health` must use the CLI/API. `argocd app list` no longer returns per-resource health |
| `ignoreResourceStatusField` default `crd` → `all` | Differences in `status` are no longer detected. Restore with `resource.compareoptions` if you depend on it |
| `applyNestedSelectors` ignored — nested selectors always apply | Check ApplicationSet logs for `ignoring nested selector` before upgrading |
| Default `resource.exclusions` and `ignoreResourceUpdates` added | Keep them; they are a performance win |
| CRDs with `spec.preserveUnknownFields: false` go `OutOfSync` | Remove the deprecated field, or `ignoreDifferences` the JSON pointer |

### 16.3 Multi-cluster, later

One Argo CD per cluster is the right shape while there is one cluster per environment: no cross-environment blast radius, and no credential in a development cluster that reaches production.

When a single control plane managing several clusters becomes worth it, note that **`argocd-agent` is at v0.10.0** — pre-1.0, moving fast, and offering a pull-model agent as an alternative to storing every cluster's credentials in one Argo CD. Promising, not yet something to build a production topology on. Revisit when it reaches 1.0.

---

## 17. Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `metadata.annotations: Too long: must have at most 262144 bytes` | Client-side apply's `last-applied-configuration` annotation exceeds 256 KiB | `ServerSideApply=true` (§8) |
| Permanently `OutOfSync`, diff shows a random string | Chart uses `randAlphaNum`; regenerated every comparison | Set the value explicitly, or source it from Vault (§9.3) |
| Permanently `OutOfSync` on `spec/replicas` | HPA owns replicas, Git also declares them | Remove `replicas` from Git, or `ignoreDifferences` (§4) |
| Sync hangs on `waiting for completion of hook` | A hook Job that never completes — classically ingress-nginx admission | `argocd.argoproj.io/hook: Skip` (§13.2) |
| Airflow pods start but the app is broken; no migrations ran | `useHelmHooks` not disabled | All four settings in §13.1 |
| `no matches for kind` | CR applied before its CRD | Sync waves (§7.3); check the controller is in an earlier wave |
| `the server could not find the requested resource` | Dry run against a CRD created by a controller, not by this sync | `SkipDryRunOnMissingResource=true` |
| Pods `ContainerCreating`, `secret "x" not found` | `ExternalSecret` in the same or a later wave than the workload | Move ESO to `-5`, store to `-3`, secrets to `-1` (§11.2) |
| App never reaches `Healthy`; `PostSync` never runs | An unhealthy resource in an earlier wave blocks everything after it | Find the lowest unhealthy wave, fix that |
| Application deleted but resources remain | No `resources-finalizer.argocd.argoproj.io` | Add the finalizer; clean up the orphans by hand once |
| Application stuck deleting with `DeletionError` | A `PreDelete` hook is failing | Fix the hook in Git, or delete the hook resource manually |
| `ComparisonError` / slow syncs / repo-server restarts | repo-server OOM | `reposerver.parallelism.limit`, more replicas, `GOMEMLIMIT` (§15.1) |
| One commit re-renders every app | Manifest cache keyed by commit SHA | `manifest-generate-paths` (§15.2) |
| Logs tab missing in the UI after an upgrade | 3.0 enforces logs RBAC | Add explicit `logs, get` policies (§12.2) |
| SSO works, permissions do not | Dex subject changed from `sub` to `federated_claims.user_id` in 3.0 | Rewrite policies against the plain identity (§12.2) |
| Webhook configured, nothing happens | Wrong secret key, GitLab cannot reach Argo CD, or an ApplicationSet generator needing its own webhook | Check `webhook.gitlab.secret`, the network path, and §10.3 |
| No deployment records in GitLab | Notifications controller disabled, no subscription annotation, or a bad token | `argocd admin notifications template notify ...` prints GitLab's error (§10.2) |
| Two apps fighting over one resource | Overlapping paths or charts | `FailOnSharedResource=true` to make it loud, then fix the ownership |
| A chart renders `null` where it used to render a value | Helm 4 / 3.17.1+ `null`-object behaviour | Remove `null` values from values files (§9.4) |
| Helm hooks ignored entirely | An Argo CD hook is defined on the same chart | Pick one hook system (§9.2) |
| UI full of churning Cilium/Kyverno objects | Missing `resource.exclusions` | Keep Argo CD 3.0's defaults, extend as needed (§13.6) |

---

## 18. Anti-patterns

| Anti-pattern | Why it hurts |
|---|---|
| Applications in the `default` AppProject | Unrestricted; can reach Argo CD's own RBAC ConfigMap |
| Templating `project` in an ApplicationSet | Privilege escalation path (§6.3) |
| Non-admins able to create ApplicationSets | Same |
| `targetRevision: HEAD` on a chart, or an unpinned Kustomize remote base | Manifests change meaning overnight — and it was the vector for a critical CVE (§16.1) |
| `Application` without the resources finalizer | Deleting it orphans everything it created |
| Auto-sync with `prune: true` on Argo CD itself | A bad commit deletes the controller that would fix it |
| `allowEmpty: true` | A broken render reads as "delete everything" |
| Creating or editing Applications in the UI | Not in Git; gone on rebuild; invisible to review |
| `argocd app rollback` without reverting the commit | The next sync silently undoes your rollback |
| Auto-sync left disabled after an incident | Invisible drift; alert on it |
| `argocd-vault-plugin` instead of ESO | Vault credentials inside the most CVE-exposed component, and a lock-in you will regret |
| Secrets defined both in Git and via ESO | Permanent `OutOfSync` |
| Everything in one giant Application | Any change re-syncs everything; the diff is unreviewable |
| Many sync waves used as general ordering | 2 s per wave; syncs crawl |
| Mixing Helm hooks and Argo CD hooks on one chart | All Helm hooks are silently ignored |
| `Replace=true` as a convenient fix | Destructive; recreates resources and can cause an outage |
| Running an unpatched minor | §16.1 — four criticals in the last patch alone |
| Shared `admin` login | No audit trail, which was half the reason for GitOps |
| Config in the same repo as application source | No access separation; CI commit loops |
| No `manifest-generate-paths` in a monorepo | Every commit re-renders every app |

---

## 19. Version reference

Verified against upstream release metadata on **8 October 2026**. Re-check before pinning; the pinned version in your repo is the real source of truth.

| Component | Latest verified | Notes |
|---|---|---|
| **Argo CD** | **v3.5.4** (2026-10-06) | Fixes 4 CRITICAL + 2 HIGH advisories (§16.1). Do not run older 3.5.x |
| Argo CD Helm chart | `argo/argo-cd` **10.10.1** | Pin it; let Renovate bump it |
| Argo Rollouts | v1.10.0 | Progressive delivery; separate decision from Argo CD itself |
| Argo Workflows | v4.1.4 | In-cluster DAGs; see [[kubernetes]] §15.5 |
| `argocd-agent` | **v0.10.0** | Pre-1.0. Multi-cluster pull model. Not a production topology yet (§16.3) |
| External Secrets Operator | chart 2.12.0 | Check the served CRD `apiVersion` before writing manifests |
| Helm binary used for rendering | **v4** (since Argo CD 3.5) | `spec.source.helm.version` is legacy and ignored (§9.4) |
| Kubernetes | v1.37.x | See [[kubernetes]] §20 for the support window |

API versions: `argoproj.io/v1alpha1` for `Application`, `ApplicationSet` and `AppProject`.

### Quick-reference annotations

| Annotation | Purpose |
|---|---|
| `argocd.argoproj.io/sync-wave: "-1"` | Ordering within a phase |
| `argocd.argoproj.io/hook: PreSync` | Phase assignment |
| `argocd.argoproj.io/hook-delete-policy: HookSucceeded` | Hook cleanup |
| `argocd.argoproj.io/sync-options: ServerSideApply=true` | Per-resource sync option |
| `argocd.argoproj.io/manifest-generate-paths: /apps/x` | Monorepo cache scoping |
| `argocd.argoproj.io/compare-options: IgnoreExtraneous` | Do not report an unmanaged resource as extraneous |
| `argocd.argoproj.io/tracking-id` | Resource ownership (3.0+ default; do not hand-write it) |
| `notifications.argoproj.io/subscribe.<trigger>.<service>` | Notification subscription |
| `argocd.argoproj.io/deletion-approved: <ISO timestamp>` | Confirm a `Prune=confirm`/`Delete=confirm` deletion |
