---
name: kubernetes
description: Use when working with Kubernetes — writing or reviewing manifests, Helm charts, Kustomize bases/overlays, choosing a control plane, GitOps (Argo CD, Flux), CI/CD through the GitLab agent, networking (Gateway API, NetworkPolicy, Cilium), autoscaling (HPA/VPA/KEDA/Karpenter), secrets (External Secrets Operator/Vault), security (Pod Security Standards, Kyverno), upgrades and version skew, or deploying services such as Airflow onto a cluster. Also covers how to lay out Kubernetes manifests in a monorepo and how to manage them at scale. Read [[argocd]] for our GitOps controller in depth and [[naturalis-kubernetes]] for org-specific conventions.
metadata:
  review_after: "2026-11-01"
  docs_url: "https://kubernetes.io/docs/concepts/configuration/best-practices/"
---

# kubernetes

Operating manual for running Kubernetes: the mental model that prevents expensive mistakes, the monorepo layouts that keep manifests manageable, the GitLab integration, and the per-subsystem practices worth actually following.

**Related skills**: [[argocd]] for Argo CD — our GitOps controller — in depth, [[naturalis-kubernetes]] for org conventions (Vault, the self-managed GitLab instance, OpenStack), [[gitlab-cicd]] for CI/CD and the Component Catalog, [[glab-cli]] for `glab`, [[opentofu]] / [[naturalis-opentofu]] for provisioning the machines underneath, [[pyinfra]] / [[biocloud-pyinfra]] for host configuration, [[airflow]] for Airflow specifics, [[databricks]] / [[biocloud-databricks]] for Databricks, [[aws-cli]] for cloud verification.

Two related skills are **repo-local to other repositories**, so they are referenced by name rather than linked: `biocloud-kubernetes` (the concrete cluster implementation) and `airflow-dag` (our DAG patterns), both under `.opencode/skills/` in their own repos. A wikilink to either would resolve to nothing from here.

## Contents

1. [Mental model and golden rules](#1-mental-model-and-golden-rules)
2. [Kubernetes in a monorepo](#2-kubernetes-in-a-monorepo)
3. [Choosing a control plane](#3-choosing-a-control-plane)
4. [Installation methods](#4-installation-methods)
5. [GitLab and Kubernetes](#5-gitlab-and-kubernetes)
6. [GitOps](#6-gitops)
7. [Workload manifests](#7-workload-manifests)
8. [Networking](#8-networking)
9. [Storage](#9-storage)
10. [Autoscaling](#10-autoscaling)
11. [Security](#11-security)
12. [Secrets](#12-secrets)
13. [Observability](#13-observability)
14. [Upgrades and version skew](#14-upgrades-and-version-skew)
15. [Service playbooks](#15-service-playbooks)
16. [Local development and CI gates](#16-local-development-and-ci-gates)
17. [Troubleshooting](#17-troubleshooting)
18. [Naming and labelling](#18-naming-and-labelling)
19. [Anti-patterns](#19-anti-patterns)
20. [Version reference](#20-version-reference)

---

## 1. Mental model and golden rules

### Cattle, not pets

Servers are disposable and interchangeable. You do not SSH into a node to fix it; you delete it and the scheduler replaces it. If a procedure requires logging into a node, that procedure is a bug. The exception is the control plane on a self-managed single-node cluster, which *is* a pet until you have three of them.

Corollary: anything you cannot rebuild from Git is either configuration (manage it with OpenTofu/Ansible/pyinfra) or data (back it up properly, and usually keep it out of the cluster).

### The reconciliation loop

Every Kubernetes object is a desired-state declaration. Controllers continuously compare declared to actual and act on the difference. Practical consequences:

- You never "restart a pod". You change the declaration; the controller restarts the pod.
- `kubectl apply` is idempotent by design; `kubectl edit` is not, and creates drift that the next apply silently reverts.
- If a controller keeps reverting your change, you are fighting the wrong layer. Find the object it derives from.

### Declarative only

Every change must originate in Git. This is not dogma — imperative changes are invisible to code review, survive only until the next apply, and break the moment two people touch the cluster. If you must run a one-off command, run it against a throwaway cluster, or capture it as a manifest immediately afterwards.

### Do not run databases on Kubernetes

Stateful databases in a cluster is the single most common way teams end up with an outage they cannot recover from. The cluster's job is compute; it should be stateless and horizontally replaceable. Databases, object stores, and message brokers with durable state belong on machines you manage, where you control backups, kernel tuning, and failure modes.

The stated exception: **operators whose entire job is managing a stateful workload** (CloudNativePG, Strimzi, the ClickHouse operator, EBS/CSI controllers). If the operator owns backups, upgrades, and monitoring, the state is a managed asset rather than an accident. Even then, be deliberate: test a restore before you need it, and know which StorageClass and reclaim policy you are on.

For a data platform specifically: object storage in S3-compatible storage is fine (it is not a database, it is a remote API), and a compute cluster reading it is the normal pattern.

### Golden rules worth memorising

| Rule | Why |
|---|---|
| Always set requests; set memory limits; treat CPU limits as a trade-off | The scheduler cannot place unsized pods; memory limits are a safety valve, CPU limits throttle (§7.2) |
| A readiness probe is not a liveness probe | Readiness controls traffic; liveness controls restarts. Conflating them causes cascading restarts |
| Never `kubectl apply` from a laptop to production | Drift, no audit trail, no rollback |
| Never `hostPath` for anything you care about | Couples the workload to one node and defeats scheduling |
| No mutable image tags (`:latest`, no tag) | Non-reproducible rollouts, silent breaking changes |
| One replica is not a deployment | Without a PodDisruptionBudget and a second replica, a node drain is an outage |
| Secrets belong in Vault, not Git or the cluster | See §12 |
| CRDs before CRs | Applying custom resources before their CRDs exist fails silently-ish and leaves a mess |
| Pin every remote reference | A remote base or chart tracking `HEAD`/`latest` can change meaning overnight |
| Drift is a bug, not a feature | If Argo CD or Flux reports OutOfSync/Suspended, fix the cause rather than accepting it |

---

## 2. Kubernetes in a monorepo

A monorepo holding every cluster's manifests in one repository is the norm, not an exception. This section is the part most projects get wrong, so it is worth reading even if you never touch the platform layer.

### 2.1 What real projects actually use

| Convention | Origin | Shape | Notes |
|---|---|---|---|
| `base/` + `overlays/{env}/` | Kustomize canonical | `base/kustomization.yaml`, `overlays/production/kustomization.yaml` | The base pattern every other layout is a variation of |
| `apps/`, `infrastructure/`, `clusters/` | Flux monorepo guide | `apps/{base,production,staging}`, `clusters/{production,staging}` | `clusters/<name>` references the app + infra overlays chosen for that cluster |
| `infrastructure/{controllers,configs}/` | Flux `flux2-kustomize-helm-example` | `controllers/cert-manager.yaml`, `configs/cluster-issuers.yaml` | `controllers` = controllers and their HelmRelease/source objects; `configs` = cluster-scoped CRs (ClusterIssuer, Gateway, NetworkPolicy) |
| `clusters/<env>/{apps,infrastructure,artifacts}.yaml` | Flux helm example | one Flux `Kustomization` per layer, plus an `ArtifactGenerator` | the current reference implementation |
| `bootstrap/{base,overlays/default}` + `cluster-config/` | Red Hat GitOps structure guide | bootstrap the GitOps controller, then cluster config | separates "install GitOps" from "configure the cluster" |
| `components/` | Kustomize KEP-1802 | `components/<behaviour>/kustomization.yaml` | portable overlays that modify many bases without conflict |
| `config/{{ .Release.Name }}/{{ .Environment.Name }}.yaml` | Helmfile conventional directory structure | values per release per environment | Helmfile's official answer to repetition across dozens of releases |
| `helmfile.d/*.yaml`, `bases:`, `helmfiles:`, `templates:` | Helmfile | one state file per release/team | `helmfile -f <dir>` loads each YAML independently |
| `apps/*/` auto-discovered | Argo CD ApplicationSet **git directory generator** | `directories: [{path: "apps/*"}]` | one `Application` per directory; no list to maintain |
| `tenants/<team>/` | Flux multi-tenancy, ApplicationSet in-any-namespace | per-team subtree | only when teams need self-service |

Two things to notice. First, every mature layout separates **infrastructure from applications**, because that separation is what lets you order reconciliation (see §2.3). Second, they all converge on **one directory per cluster**, which is the rule that actually makes a monorepo operable.

### 2.2 The governing rule: one directory = one cluster

```
clusters/
├── development/
├── acceptance/
└── production/
```

That single directory should be simultaneously:

- the CI matrix entry (`kustomize build clusters/production | ...`),
- the `kubectl apply -k` target,
- the Argo CD `Application` or Flux `Kustomization` `path`,
- and the scope of a GitLab agent context.

When all four agree, adding an environment is "add a directory plus a CI matrix row", and reviewing a change is "which directories does this diff affect". When they disagree, you get per-cluster drift nobody notices.

Prefer `clusters/` over `environments/` for this reason: `environments/` reads like "one cluster, many environments", but as soon as you have two clusters the axis becomes ambiguous — is `production` an environment or a cluster? Ambiguity is where monorepos rot. If you genuinely have "one cluster, many environments", then `clusters/<cluster>/environments/<env>/` makes the axis explicit.

### 2.3 Three layers, ordered — and the order is load-bearing

```
platform (or infrastructure)
├── controllers/   # cert-manager, gateway, Cilium, ESO, KEDA, Argo CD, metrics-server
└── configs/       # ClusterIssuer, GatewayClass, StorageClass, PSA labels, NetworkPolicies
apps
└── base/<app>/
clusters/<name>/  # points at infra, then apps
```

Reconcile in the order **controllers → configs → apps**. The reason is mechanical, not stylistic: a `ClusterIssuer` is a custom resource, and it cannot be applied until `cert-manager`'s CRD exists, which cannot happen until the controller is running. Flux expresses this with `dependsOn`:

```yaml
apiVersion: kustomize.toolkit.fluxcd.io/v1
kind: Kustomization
metadata:
  name: infra-configs
  namespace: flux-system
spec:
  dependsOn:
    - name: infra-controllers
  sourceRef:
    kind: GitRepository
    name: flux-system
  path: ./infrastructure/production
  prune: true
  wait: true
```

Argo CD expresses the same with sync waves via the annotation `argocd.argoproj.io/sync-wave: "1"`, `-1` for wave ordering. Same rule, different vocabulary.

**Failure mode to recognise**: apps applied before CRDs exist report `no matches for kind`, the controller retries forever, and the error is easy to misread as a bad manifest. If you see "no matches for kind", check ordering before you check syntax.

Also: keep `controllers/` and `configs/` in **separate** top-level kustomizations even when they must deploy together, so a bump to a monitoring stack does not re-sync your cert issuers. See §2.5 on artifacts.

### 2.4 Auto-discovery, so nobody maintains a list by hand

Hand-maintained lists of applications rot within a month. Three mechanisms, pick per GitOps tool:

**Flux `ArtifactGenerator` + `ExternalArtifact`** (requires the `source-watcher` component). Splits the monorepo into independently-synced artifacts so that changes outside a given subtree do not trigger reconciliation of that subtree. From the reference implementation: *"Changes to files outside the apps/ dirs will not trigger a reconciliation of the apps Kustomization."* This is the most valuable monorepo-specific trick available, because it keeps a noisy platform directory from re-reconciling every application.

```yaml
apiVersion: source.extensions.fluxcd.io/v1beta1
kind: ArtifactGenerator
metadata:
  name: apps
  namespace: flux-system
spec:
  sources:
    - kind: GitRepository
      name: flux-system
    - kind: Directory
      path: ./apps/base
    - kind: Directory
      path: ./apps/production
  artifacts:
    - name: apps
      sourceRef:
        kind: GitRepository
        name: flux-system
      build:
        source:
          kind: Directory
          path: ./apps/base
        include:
          - ./apps/production/**/*
```

**Flux plain**: one `Kustomization` per cluster with `spec.path: ./apps/production`. Simple, obvious, and re-syncs on any repo change. Fine at small scale.

**Argo CD ApplicationSet git directory generator**: generates parameters from the repository's directory structure.

```yaml
apiVersion: argoproj.io/v1alpha1
kind: ApplicationSet
metadata:
  name: apps
  namespace: argocd
spec:
  goTemplate: true
  goTemplateOptions: ["missingkey=error"]
  generators:
    - git:
        repoURL: https://gitlab.com/<group>/<repo>
        revision: main
        directories:
          - path: "apps/*"
        exclude:
          - "*/base"
  template:
    metadata:
      name: '{{ .path.basenameNormalized }}'
    spec:
      project: default
      source:
        repoURL: https://gitlab.com/<group>/<repo>
        targetRevision: main
        path: '{{ .path }}'
      destination:
        server: https://kubernetes.default.svc
        namespace: '{{ .path.basenameNormalized }}'
```

Notes: directories beginning with `.` are excluded automatically; `exclude` lets you skip `base/`; `path.basenameNormalized` substitutes unsupported characters with `-`.

**Security caveat** from the Argo CD docs: git generators are often used to make Application creation easy for non-admins. If the `project` field is templated, developers may be able to create Applications under Projects with excessive permissions. With git generators the source of truth must remain admin-controlled.

### 2.5 Sharing configuration without duplication

**Kustomize**

- `components/` for cross-cutting behaviour that applies to many bases (KEP-1802). Use it instead of copying a base to vary it.
- `patches` for deltas, not the deprecated `patchesStrategicMerge`.
- `configMapGenerator` for anything that varies per environment; the name gets a content hash suffix, which is how a ConfigMap change triggers a rollout without you templating anything.
- `namePrefix`/`nameSuffix` for per-cluster identity when a base is not yours to modify.
- Nested overlays compose: an overlay may list other overlays as resources.

**Helmfile**

- **Release template** (`templates:`) plus the conventional directory structure is the documented way to avoid repeating `namespace`, `chart`, and values paths across dozens of releases:

  ```yaml
  templates:
    default: &default
      namespace: "{{ .Release.Name }}"
      chart: "./charts/{{ .Release.Name }}"
      values:
        - "./config/{{ .Release.Name }}/values.yaml"
        - "./config/{{ .Release.Name }}/{{ .Environment.Name }}.yaml"
  releases:
    - name: heapster
      <<: *default
  ```

- `bases:` layers state files, merged in order of occurrence — the documented way to extract shared parts into library helmfiles and stay DRY.
- `helmfiles:` are processed **before** the parent's releases, which makes them the place for CRDs a release depends on.
- `helmfile -f <dir>` loads every YAML in a directory as an independent state file (default directory `helmfile.d`); `helmfile --sequential-helmfiles` when order matters.
- Helmfile has no built-in global values file. Use `environments` plus a `.gotmpl` file referencing `{{ .StateValues }}` / `{{ .Values }}`.
- Helmfile supports both Helm 3 and Helm 4.

- **Verified values merge order** (lowest to highest priority): `bases:` files → root-level `values:` → environment values (yaml/gotmpl) → environment values (HCL, including HCL secrets) → environment secrets (non-HCL, decrypted) → command-line overrides.

**Argo CD**

- Keep config in a separate repository from application source where you can. Argo CD's own best-practices doc lists the reasons: manifests change without triggering a build, a cleaner audit log, services made of several repos, and crucially **separate access control** so app developers who should not push to production do not have commit rights on production config.
- **Never point a remote base or `targetRevision` at `HEAD`.** The docs are explicit that with templating tools a manifest "can change its meaning from one day to the next" because of an upstream change. Pin tags, commits, or chart versions.

### 2.6 Promotion across environments

| Model | Mechanism | Pros | Cons |
|---|---|---|---|
| Branch per environment | `main`, `acceptance`, `production` branches | Familiar, GitLab-native review flow | Divergence; merges back are painful; a fix must be cherry-picked forward |
| Path per environment | `clusters/development`, `clusters/acceptance`, `clusters/production` | Single branch, single history, no divergence | Every change is visible to production reviewers immediately; needs strong MR rules |
| Tag per environment | production syncs a Git tag instead of `main` | Exact, immutable promotion artifact; approval gates the tag | Requires the GitOps controller to support tag refs |

The tag model is the cleanest promotion story, and it is available: the **Flux Operator** (`FluxInstance`) lets production clusters sync from Git tags rather than the main branch, which GitLab's own enterprise best-practices doc points at when discussing scaled deployments. The operator also removes the need for write access to the Git repository (it works with OIDC providers and GitHub Apps), automates Flux controller and CRD upgrades, supports sharding, and offers a Git-less mode where cluster state lives in OCI artifacts.

For a single-tenant self-managed cluster, path-per-environment with a protected `production` environment in GitLab is the pragmatic default. Note the trade-off above and pick deliberately.

### 2.7 GitOps controller choice

| | Flux | Argo CD |
|---|---|---|
| Package model | `HelmRelease` CRs — first-class, chart values stay values | `Application` CRs rendering either Helm or Kustomize |
| Monorepo auto-discovery | `ArtifactGenerator`/`ExternalArtifact`; per-cluster `Kustomization` | ApplicationSet generators (git directory, matrix, merge) |
| UI | `flux get` CLI; Grafana dashboards | Full web UI with resource tree and diff |
| Multi-tenancy | `FluxInstance`, sharding, multi-tenancy lockdown | ApplicationSet in any namespace + `sourceNamespaces` |
| GitLab recommendation | **Recommended by GitLab** for agent-based GitOps | Supported, not GitLab's recommended path |
| Adoption (CNCF 2025) | ~11% | **~60% of clusters** |
| OpenShift | Not the native path | **OpenShift GitOps *is* Argo CD** |

**We use Argo CD.** Read [[argocd]] for the full reasoning, the install, and the gotchas. The short version: the UI is a teaching tool for a team still learning Kubernetes, adoption is five times Flux's so help is easy to find, and OpenShift GitOps is Argo CD — which matters because [[naturalis-kubernetes]] §6 plans for a provider-managed control plane that may be OpenShift.

The honest counterweight: GitLab's documentation recommends **Flux** for GitOps (since 15.10, hardened in 16.1), the agent and Flux together are GitLab's best-integrated combination, and the agent auto-configures a Flux `Receiver` so a push reconciles immediately. Choosing Argo CD means replacing that one convenience with a GitLab webhook and giving up GitLab-side deployment gating. [[argocd]] §10 scores every GitLab feature and gives the workaround for each.

Flux remains the better choice if GitLab-native integration is the dominant requirement, or if you want its signed-`OCIRepository` supply-chain flow.

### 2.8 CI gates for a Kubernetes monorepo

Every one of these should run on a merge request:

| Gate | Command | Catches |
|---|---|---|
| Render | `kustomize build clusters/<env>` (or `helmfile template`) | broken references, missing files |
| Schema validation | `kubeconform -strict -summary -kubernetes-version <ver>` | wrong apiVersions, typos, removed fields |
| Policy score | `kube-score score` or `polaris lint` | missing requests/limits, probes, securityContext |
| Policy enforcement | `kyverno apply <policies> --resource <rendered>` | org rules before they reach a cluster |
| Secret scan | `gitleaks detect` | committed secrets |
| Server-side dry run | `kubectl apply --dry-run=server -f <rendered>` (needs a cluster) | admission-time rejections, CRD version skew |
| Drift check | diff rendered output against the live cluster via the agent | the whole point of the `diff` job |

Validate **every** overlay in a matrix, not just `production`. A `development` overlay that only breaks when someone needs it is worse than no overlay. If you use Flux, also validate against the Flux schema ecosystem catalog, which type-checks the Flux CRs themselves. On Argo CD, add the `Application`/`ApplicationSet`/`AppProject` CRD schemas to `kubeconform`'s schema locations so a malformed `Application` fails in CI rather than silently generating nothing — and render ApplicationSets locally (`argocd admin applicationset generate <file>`) to see which Applications a generator change would actually produce.

### 2.9 Monorepo anti-patterns

| Anti-pattern | Why it hurts | Instead |
|---|---|---|
| One mega `kustomization.yaml` | Any change re-syncs everything; merge conflicts are constant | Split per cluster and per layer (§2.3) |
| Committing rendered YAML | Duplicates the source of truth, guarantees drift | Render in CI, publish as an artifact if needed |
| Copying a base to vary one field | Divergence nobody notices for months | `patches`, or `components/` |
| Controllers and apps in one kustomization | A CRD bump re-reconciles every application | Separate top-level kustomizations, or `ArtifactGenerator` |
| `environments/` as the top axis | Cluster/environment axis becomes ambiguous | `clusters/<name>/` |
| Per-cluster copies of shared config | Shared config drifts between clusters | Overlay onto a shared base; no copies |
| Hand-maintained app lists | Rot within a month | Auto-discovery (§2.4) |
| Mixing GitOps and imperative applies | Guarantees drift and a confusing incident | GitOps only; emergency changes get captured as manifests |
| Secrets in Git even encrypted | Key management becomes the real system, rotation pain, false sense of safety | External Secrets Operator (§12) |
| `CODEOWNERS` absent | Nobody reviews the platform layer | `CODEOWNERS` per app directory and per cluster |

---

## 3. Choosing a control plane

### Options

| Option | Who operates the control plane | Notes |
|---|---|---|
| Managed: EKS / GKE / AKS | Provider | Least operational burden; no `kubeadm`, no etcd, restricted cloud credentials. Costs more |
| Managed via OpenStack provider | External provider | Common in enterprises that have standardised on OpenStack. Treat like any other managed control plane: no node access, quotas, supported CSI drivers |
| k3s | You | Single binary + systemd unit, embedded etcd by default, very easy to run on OpenStack VMs. Best default for self-hosted small clusters |
| k0s | You | Similar ergonomics to k3s with a declarative `k0sctl` layer; more opinionated about networking and components |
| Talos | You | API-only, immutable OS, no SSH. Powerful, larger conceptual jump |
| kubeadm | You | The upstream reference. Most documentation matches it. More moving parts: certificates, etcd, control plane load balancer, join tokens |
| RKE2 / k3s (Rancher) | You | kubeadm-compatible with bundled enterprise defaults |

### Decision factors

- **How many nodes?** One or two: k3s, single control plane. Three or more with HA: three stacked control-plane nodes behind a load balancer. Either way, set `--control-plane-endpoint` at `init` — see "HA control plane" below for why that is the one decision you cannot defer.
- **Who else needs access?** If a provider or a colleague will operate it later, prefer something standard (kubeadm, k3s) over something exotic.
- **Is the control plane a pet or cattle?** A single control plane on a self-hosted cluster *is* a pet. Budget for its failure: without HA, a control-plane reboot is a cluster outage.
- **Portability.** When you move to a provider-managed control plane, you lose `kubeadm`, node access, and possibly some CSI drivers. Design for that from the start (§20 migration readiness).

### Self-hosted on OpenStack

If you are building Kubernetes on OpenStack VMs you own:

- One VM per node; a control plane and two workers is the smallest useful shape.
- Put the VMs in the same OpenStack network with a private fixed IP. Do not expose 6443 to the internet — see §5 for why an outbound-only agent connection removes the need.
- Back up etcd (`etcdctl snapshot save`) and store the snapshot somewhere outside the cluster. A cluster whose etcd backup lives inside the cluster is not backed up.
- Keep the OpenStack security groups as your first network control layer, then Kubernetes `NetworkPolicy` for the second.

### HA control plane: the decision you make at `init` time

**Best practice is three stacked control-plane nodes behind a load balancer.** That is kubeadm's default HA topology and the right answer for a self-managed cluster of our size.

**The one irreversible decision: pass `--control-plane-endpoint` on the very first `kubeadm init`, even for a single control-plane cluster.** Kubernetes' own documentation recommends exactly this: *"If you have plans to upgrade this single control-plane kubeadm cluster to high availability you should specify the `--control-plane-endpoint` to set the shared endpoint for all control-plane nodes."* It takes a DNS name or a load-balancer address.

Skip it and the API server's address is the first node's own IP, baked into every certificate SAN and every kubeconfig. Converting to HA afterwards means re-issuing the control-plane certificates and re-joining every node — in practice a rebuild. It costs nothing to set on day one, so set it even if HA is a "maybe later":

```sh
# Point it at the LB/DNS name from day one, even with one control-plane node
kubeadm init --control-plane-endpoint "k8s-api.development.example.org:6443" --upload-certs
```

| Topology | Hosts | When |
|---|---|---|
| Single control plane | 1 | Development only. It *is* a pet (§"Decision factors"); a reboot is an outage |
| **Stacked etcd, 3 control-plane nodes** | 3 | **The default.** etcd colocated with the control plane; kubeadm creates each etcd member automatically on `kubeadm join --control-plane` |
| External etcd, 3 + 3 | 6 | Only when you need the failure domains decoupled. Kubernetes' docs: *"this topology requires twice the number of hosts"* |

Rules that come from etcd, not from Kubernetes:

- **Three, not two.** etcd needs a quorum, so an odd count: 3 tolerates one node loss, 5 tolerates two. A two-node control plane is *less* available than one node, because losing either breaks quorum.
- **Stacked means coupled failure.** Losing one node loses both an etcd member and a control-plane instance, which is precisely why the minimum is three rather than two.
- **etcd is latency- and fsync-sensitive.** Put the control-plane nodes on fast disks and a low-latency network. Spreading them across distant OpenStack AZs to "improve availability" can instead make etcd unstable — spread within a region, not across high-latency links.
- **Back up etcd regardless of topology.** HA protects against node loss, not against a bad `kubectl delete` or a corrupted cluster (§9.4).

On OpenStack the load balancer in front of `:6443` is **Octavia**, which is the same dependency as §"OpenStack platform integration" below — so if Octavia is unavailable in your tenancy, an HA control plane needs `keepalived` + `haproxy` on the control-plane nodes themselves, with the VIP in `allowed_address_pairs` exactly as MetalLB requires. Decide this before provisioning, because it changes the node count and the network plan.

**Our honest recommendation**: on a development cluster, one control-plane node *with* `--control-plane-endpoint` set. For anything carrying real work, three. The upgrade from one to three is then adding nodes, not rebuilding — which is the whole point of setting the flag early.

### OpenStack platform integration

**A self-managed cluster on OpenStack is not complete without this, and the symptoms of skipping it look like bugs elsewhere.** Vanilla Kubernetes has no idea it is running on OpenStack. Three components connect it:

| Component | Provides | Symptom if missing |
|---|---|---|
| `openstack-cloud-controller-manager` (OCCM) | Node lifecycle and metadata, and `Service type=LoadBalancer` via Octavia | A `LoadBalancer` Service stays `<pending>` **forever**, with no event explaining why. Nodes may never clear the `uninitialized` taint, so nothing schedules |
| `cinder-csi-plugin` | `PersistentVolume` provisioning from Cinder | PVCs stay `Pending`; or they bind but with AWS-shaped `StorageClass` parameters that Cinder rejects (§9.2) |
| Octavia | The actual load balancers, and usually the control-plane VIP in an HA build | No externally reachable Service, no Gateway address, no HA API endpoint |

Wiring it up:

1. **kubelet needs `--cloud-provider=external`** on every node, set *before* `kubeadm join`. This is the step that is easiest to miss on a node added later: the new node joins, takes the `node.cloudprovider.kubernetes.io/uninitialized:NoSchedule` taint, and waits for a cloud controller to remove it. If OCCM is not running — or the node was joined without the flag so OCCM never claims it — the taint never clears and the node looks healthy while scheduling nothing.
2. **OCCM reads a `cloud.conf`** from a Secret in `kube-system`, conventionally created as `kubectl create secret -n kube-system generic cloud-config --from-file=cloud.conf`. It holds the Keystone endpoint and credentials, plus `[LoadBalancer]`, `[BlockStorage]` and `[Networking]` sections.
3. **Octavia is mandatory for load balancing.** OCCM's own documentation is explicit: Neutron-LBaaS support was **removed in OCCM v1.26.0**, so the current implementation is Octavia-only. Confirm with your OpenStack operator that Octavia is available and that your project has LB quota before designing anything around `type: LoadBalancer`.

**If Octavia is not available, use MetalLB.** This is the realistic fallback on an OpenStack tenancy without LBaaS, and it changes the design, so decide early:

- MetalLB in **L2 mode** answers ARP for an address pool you control, so the addresses must come from the node subnet, and OpenStack's port security will drop traffic for an address the port does not own. You must add the VIPs to the ports' `allowed_address_pairs` — this is the single step that makes "MetalLB on OpenStack" fail silently for people.
- BGP mode needs a cooperating router, which you usually do not get in a tenant network.
- MetalLB gives you `Service type=LoadBalancer`, which is all the Gateway API and ingress controllers need (§8) — a Gateway's address ultimately comes from a `LoadBalancer` Service, so without either Octavia or MetalLB a `Gateway` never gets an address and every route is unreachable.

Two platform limitations worth knowing before you debug them: OpenStack availability zone names **must not contain blanks** for OCCM to work, and if the Cinder AZs do not match the Nova AZs you must set `ignore-volume-az: true` (§9.2).

A provider-managed OpenStack Kubernetes service normally installs and operates all of this for you — which is a concrete argument for that path, not just a cost question.

---

## 4. Installation methods

| Method | Use when | Avoid when |
|---|---|---|
| Helm | A chart exists and you want its values model | You need to patch something the chart fights you on — forking beats 20 patches |
| Kustomize | You own the manifests and need overlays | A complex application whose maintainers already solved the problem |
| Raw YAML | Very small, stable things | Anything with more than a handful of resources |
| Argo CD `Application` / Flux `HelmRelease` | Any of the above, but GitOps | — |
| `kpt` / Config Sync | You want Google's declarative inventory model | You are on GitLab and want the agent path |
| Operator / CRD | The workload has a well-run operator | The operator is abandoned or immature |
| Helmfile | You have many Helm releases and want one entrypoint | You have one or two releases |

### Preflight for a self-hosted node

`kubeadm` fails late and cryptically. Check these before running `kubeadm init` or `k3s install`, and put them in the node-provisioning tool so they are a diff rather than a manual step:

| Check | Required value | Symptom if wrong |
|---|---|---|
| Swap | Disabled, and removed from `/etc/fstab` | `kubeadm init` refuses; kubelet crash-loops |
| cgroup driver | CRI and kubelet both `systemd` | `containerd` starts, nodes stay `NotReady` |
| `br_netfilter` | Loaded via `/etc/modules-load.d/` | Pod networking silently fails to route |
| `net.ipv4.ip_forward` | `1` in `/etc/sysctl.d/` | Cross-node traffic hangs |
| `overlay` module | Loaded | containerd cannot unpack images |
| `conntrack` | Installed | kube-proxy fails on large clusters |
| Container runtime | `systemd` cgroup, CRI socket enabled | Nodes register but never become ready |

The cgroup driver mismatch is the one that costs the most time, because the runtime reports itself as healthy. A minimal runtime config (Docker's default `containerd` config, for instance) omits `SystemdCgroup`; generate a full default config rather than patching a minimal one.

### Bootstrap order: bare VMs to running applications

The layering in §2.3 says *what* depends on what. This is the concrete sequence, because the order is where a first cluster actually goes wrong — each step below is blocked by the one before it, and several have no useful error message when done early.

| # | Step | Blocked until the previous step works because |
|---|---|---|
| 1 | Provision VMs, DNS names, security groups ([[naturalis-opentofu]]) | — |
| 2 | Node preflight (table above), via the provisioning tool | `kubeadm init` fails late and cryptically otherwise |
| 3 | `kubeadm init` / `k3s install` with `--cloud-provider=external` **and `--control-plane-endpoint`** | Both are effectively irreversible; retrofitting either means re-joining every node or re-issuing control-plane certs (§3) |
| 4 | **CNI** (Cilium) | Nodes stay `NotReady` and **no pod schedules** until a CNI is running. CoreDNS sits `Pending` — that is expected, not a fault |
| 5 | **OCCM** + `cloud-config` Secret | Clears the `uninitialized` taint. Until this runs, nodes look healthy and schedule nothing |
| 6 | **Cinder CSI** + a `StorageClass` (§9.2) | Anything with a PVC is unschedulable |
| 7 | **metrics-server** | HPA, VPA and `kubectl top` are silently non-functional without it |
| 8 | **Octavia or MetalLB** (§3) | A `Gateway` or `LoadBalancer` Service never gets an address |
| 9 | **Argo CD**, by hand, once ([[argocd]] §3.1) | Everything after this arrives through Git |
| 10 | Argo CD manages itself; root `Application` per cluster ([[argocd]] §3.2–3.3) | Makes step 9 reproducible instead of a snowflake |
| 11 | **ESO**, then `ClusterSecretStore`, then `ExternalSecret`s (waves `-5`/`-3`/`-1`) | Every later component's credentials come from here |
| 12 | **cert-manager** + `ClusterIssuer` | TLS is a dependency of the gateway and of nearly everything public |
| 13 | **Gateway controller** (§8.8) + `Gateway` + DNS (§8.6) | Routes are unreachable without an address *and* a DNS record |
| 14 | GitLab agent ([[argocd]] §10.5), Kyverno, monitoring, Trivy | Platform services; none block the ones above |
| 15 | Applications, via ApplicationSet ([[argocd]] §6) | — |

**The two circular dependencies, and how to break them:**

1. **Argo CD needs a repo credential before it can sync the thing that creates repo credentials.** Create that one Secret by hand at step 9, then bring it under ESO management at step 11 and delete the hand-made copy. [[argocd]] §11.3.
2. **ESO needs a working cluster to authenticate to Vault, and Vault holds the credentials the cluster needs.** Vault's Kubernetes auth role must be created *before* step 11, by whoever administers Vault, bound to the ServiceAccount name you are going to use. Agree that name up front — it is the one value you cannot discover from inside the cluster.

**Verify each step before moving on.** The cost of discovering a step-5 mistake at step 13 is a rebuild:

```sh
kubectl get nodes                                   # 4-5: all Ready, no uninitialized taint
kubectl describe node <n> | grep -i taint           # 5: must be empty
kubectl get pods -A --field-selector=status.phase!=Running   # 4-7: should be empty
kubectl top nodes                                   # 7: metrics-server alive
kubectl get sc                                      # 6: a default StorageClass exists
kubectl get svc -A -o wide | grep -i pending        # 8: no stuck LoadBalancers
kubectl get application -n argocd                   # 10+: everything Synced/Healthy
```

Steps 1–8 are not GitOps — they are the substrate GitOps runs on, and they belong in the provisioning tool ([[pyinfra]] / [[naturalis-opentofu]]), not in the manifest repo. Step 9 onward is Git. Keeping that line sharp is what makes a rebuild a known quantity.

### Helm notes

- **Helm 4 is current.** Charts must declare `apiVersion: v2`; verify a chart is Helm 4 compatible before adopting it. Helmfile supports Helm 3 and Helm 4.
- `helm lint` and `helm template` locally; `helm template --validate` against a live cluster for schema checking.
- `--set` in CI is an anti-pattern: it is invisible in the diff. Use a values file.
- Pin chart versions in Git. Let Renovate propose bumps (§16).

### Kustomize notes

- Kustomize is built into `kubectl` (`kubectl apply -k`), but the standalone binary is newer and supports more; install it for CI.
- `kustomize build` is the unit of validation. Everything in §2.8 pipes through it.

---

## 5. GitLab and Kubernetes

GitLab's supported integration is the **agent for Kubernetes**: `agentk` (in-cluster) and `kas` (GitLab-side). Certificate-based cluster integration is **deprecated** — the agent is the only supported path. This section covers the agent.

### 5.1 Architecture

`agentk` runs in the cluster and dials **outbound** to `kas` over a TLS tunnel. Nothing connects inbound to your API server, which is why this works for clusters behind NAT, private OpenStack networks, and firewalled VPCs.

```
cluster                                GitLab
agentk ──outbound TLS──▶ kas ──▶ API (projects / environments / job tokens)
   │                                    ▲
   └──────── kubeconfig over tunnel ─────┘
```

Consequences worth internalising:

- **No inbound firewall rule to the API server is ever required.** This is the single biggest operational win over manual access.
- The connection is per-project and per-environment, and a project is limited to a maximum of **500 agents** on one instance.
- `$KUBECONFIG` and `$KUBE_CONTEXT` are injected into CI jobs automatically; you do not distribute kubeconfigs.

### 5.2 Installing the agent

Prerequisites: a registered agent and an agent token from **Settings > CI/CD > Agents** (or `glab api`).

> **If you run Argo CD, skip option 1 and use option 2 or 4.** `glab cluster agent bootstrap` is a *Flux* bootstrap: it requires `flux` on your `PATH`, expects the cluster to have been `flux bootstrap`-ed first, and commits Flux `HelmRepository`/`HelmRelease` resources to your repo before triggering a Flux reconciliation. GitLab calls it the recommended path because GitLab recommends Flux ([[argocd]] §10). Running it on an Argo CD cluster installs a second GitOps controller by accident, and you end up with Flux owning the agent while Argo CD owns everything else.

```sh
# 1. Register and install with Flux support — GitLab's recommended path.
#    Requires glab, kubectl AND flux on your PATH, and a Flux-bootstrapped cluster.
#    DO NOT use this on an Argo CD cluster — it installs Flux resources.
flux bootstrap gitlab \
  --hostname <gitlab.example.org> \
  --owner <group> --repository <repo> --branch main \
  --path clusters/<env>
# --manifest-path must match flux bootstrap's --path, or reconciliation fails
glab cluster agent bootstrap <agent-name> --manifest-path clusters/<env>

# 2. Or install the chart directly (no Flux).
helm repo add gitlab https://charts.gitlab.io
helm repo update
helm upgrade --install <agent-name> gitlab/gitlab-agent \
  --namespace gitlab-agent --create-namespace \
  --set config.token=<agent-token> \
  --set config.kasAddress=wss://<gitlab-host>/-/kubernetes-agent/ \
  --set image.tag=<agentk-version> \
  --set serviceMonitor.enabled=true

# 3. Or from OCI, no repo entry needed.
helm upgrade --install <agent-name> \
  oci://registry.gitlab.com/charts/charts.gitlab.io/release/gitlab-agent \
  --namespace gitlab-agent --create-namespace \
  --set config.token=<agent-token>
```

For self-signed certificates add `--set config.kasCaCert=<PEM>`. For a private registry that hosts the chart, see the chart's `image.registry` values.

**Option 4 — the agent as an Argo CD `Application`.** This is the right shape when Argo CD is already the controller: one GitOps tool owns everything, including the agent. The token must *not* be in Git, so it comes from Vault through External Secrets (§12), and the `Application` only references the Secret by name.

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: gitlab-agent
  namespace: argocd
spec:
  project: platform
  source:
    repoURL: https://charts.gitlab.io
    chart: gitlab-agent
    targetRevision: 2.32.0          # pin it; see [[argocd]] §5
    helm:
      valuesObject:
        config:
          # Secret created by an ExternalSecret in this namespace, key `token`
          secretName: gitlab-agent-token
          kasAddress: wss://<gitlab-host>/-/kubernetes-agent/
        rbac:
          useExistingRole: gitlab-agent
        serviceMonitor:
          enabled: true
  destination:
    server: https://kubernetes.default.svc
    namespace: gitlab-agent
  syncPolicy:
    syncOptions:
      - CreateNamespace=true
      - ServerSideApply=true
```

Order matters: the `ExternalSecret` that produces `gitlab-agent-token` must sync before the chart, or `agentk` crash-loops on a missing Secret. Use a sync wave ([[argocd]] §7) to put the secret ahead of the release.

Verify chart values with `helm show values gitlab/gitlab-agent` before relying on a specific key — the chart evolves. Hardening values worth reviewing each time:

| Value | Effect |
|---|---|
| `serviceAccount.create=false` | Use a pre-created ServiceAccount |
| `rbac.useExistingRole=<name>` | Use your own ClusterRole instead of the bundled broad one |
| `rbac.create=false` | Bind nothing by default; you own RBAC |
| `config.secretName=<name>` | Bring your own Secret for the token instead of passing `config.token` on the command line |
| `config.kasCaCert=<PEM>` | Verify a self-signed KAS certificate |
| `serviceMonitor.enabled=true` | Create a `ServiceMonitor` so Prometheus scrapes the agent |
| `config.operational_container_scanning.enabled=false` | Skip the container-scanning RBAC if you do not use that feature (default `true`) |
| `securityContext` / `podSecurityContext` | Empty by default; set them to satisfy a `restricted` PSA namespace (§11) |
| `extraEnv[0].name=HTTPS_PROXY` | Reach KAS through an HTTP proxy |

The agent's bundled ClusterRole is `cluster-admin` by default — GitLab's own documentation says not to use that on production systems. On a shared or production cluster, create a least-privilege role and pass `rbac.useExistingRole`.

**On upgrades, never use `--reuse-values`.** GitLab documents this explicitly: `--reuse-values` misses new chart defaults and silently retains deprecated ones. Capture the values instead and pass them back as a file:

```sh
helm get values <agent-name> -n gitlab-agent > agent-values.yaml
helm upgrade <agent-name> gitlab/gitlab-agent -n gitlab-agent -f agent-values.yaml
```

**Version skew:** keep `agentk` within one minor of the GitLab instance version. GitLab supports the matching minor plus the previous and next one — so a 19.4 instance is happy with agent 19.3.x–19.5.x. If you omit `image.tag`, you get whatever the chart pins, which can lag the agent's own latest release.

### 5.3 The agent configuration file

Lives at **`.gitlab/agents/<agent-name>/config.yaml` in the default branch** of the project that owns the agent.

```yaml
# Minimal, development
ci_access:
  projects:
    - id: <group>/<repo>

---
# Scoped to environments, production behind a GitLab environment
ci_access:
  environments:
    - name: development
      url: https://<host>/<group>/<repo>/-/environments/development
    - name: production
      url: https://<host>/<group>/<repo>/-/environments/production
      protection_rule: all
  groups:
    - id: <group>
      default: true
  protected_branches_only: false

---
# Least privilege: impersonation instead of a real ServiceAccount
ci_access:
  projects:
    - id: <group>/<repo>
  access_as:
    ci_job:
      - groups:
          - gitlab:ci_job:deploy:development
```

Fields:

| Field | Meaning |
|---|---|
| `ci_access.projects[].id` | Full path (`group/subgroup/project`) |
| `ci_access.projects[].default` | Whether a new context defaults to this project |
| `ci_access.groups[].id` | Group-wide access |
| `ci_access.environments[]` | Scope access to GitLab environments; `protection_rule: all` requires the job to be on a protected branch |
| `ci_access.protected_branches_only` | Only allow jobs from protected branches |
| `access_as.ci_job` | Impersonate groups instead of using the agent's ServiceAccount — the least-privilege path |
| `gitops` | **Legacy**, superseded by Flux; see the migration guide |

**Prefer `access_as.ci_job`** on anything shared. With impersonation, the job's effective permissions come from its own CI/CD identity and GitLab group permissions, so a leaked kubeconfig grants nothing extra.

Impersonation requires a matching RBAC binding. Example: bind a CI job group to `view` on development namespaces only:

```yaml
# rbac.yaml, applied once
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: gitlab-ci-job-deploy-development
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: ClusterRole
  name: view
subjects:
  - apiGroup: rbac.authorization.k8s.io
    kind: Group
    name: gitlab:ci_job:deploy:development
```

### 5.4 GitOps with GitLab

**We run Argo CD** (§2.7). The agent is still worth installing alongside it — it provides the GitLab Kubernetes dashboard, `$KUBECONFIG` in CI jobs for validation gates, and outbound-only cluster access. What you do not get is the Flux `Receiver` auto-detection; the Argo CD equivalent is a GitLab webhook to `/api/webhook`. See [[argocd]] §10 for the full integration scorecard, the deployment-tracking configuration, and the webhook setup.

The rest of this section documents GitLab's own recommended path, which is Flux. Read it to understand what the agent offers natively and what we are trading away.

GitLab's documented position: GitLab recommends **Flux** for GitOps, the agent and Flux together are the recommended combination, and the GitOps workflow is preferred over CI/CD-driven deploys. The agent **automatically detects** Flux `GitRepository` objects that reference projects in the same GitLab instance and configures a `Receiver`, so a git push triggers reconciliation immediately instead of waiting for the poll interval. That requires both the agent and `source-watcher`.

GitLab's enterprise best practices for this setup:

- Run **a single agent installation per cluster**; share the connection across the domain using impersonation rather than registering agents per project.
- Install Flux at scale with the **Flux Operator** or with OpenTofu/Ansible, not by hand.
- Configure Flux **multi-tenancy lockdown**.
- Use Flux **`OCIRepository`** to store manifests: build and push an OCI artifact from a GitLab pipeline, and have Flux consume the tag. Sign the artifact and deploy only signed, verified artifacts — Flux can verify signatures. Container registry scanning still applies to OCI artifacts.
- **Trigger reconciliation from the GitLab pipeline** to shorten the feedback loop instead of relying solely on the poll interval.
- **Rotate the keys** Flux uses to access manifests, and the agent-registration token, on a schedule.

Gotcha worth knowing: if Flux is pointed at a project root with no `kustomization.yaml`, it walks the tree and will try to apply `.gitlab/agents/<name>/config.yaml` as a manifest, which fails because it is not a Kubernetes object. Always point Flux at a specific `path`, and keep agent config outside it.

### 5.5 Accessing the cluster from a CI job

```yaml
k8s:deploy:
  image: registry.gitlab.com/charts/cluster-applications
  script:
    - kubectl config use-context "$KUBE_CONTEXT"
    - kubectl get pods
```

`$KUBE_CONTEXT` format is `<agent-config-project-path>:<agent-name>`.

If you see permission errors reading the kubeconfig, the known workaround is to tighten its permissions:

```sh
chmod 400 "$KUBECONFIG"
```

The GitLab-provided cluster-applications image also ships helpers worth using rather than reimplementing:

| Helper | Purpose |
|---|---|
| `gl-use-kube-context` | select the agent context |
| `gl-helmfile` | run Helmfile against it |
| `gl-ensure-namespace` | create the namespace before deploying |

Pin the image tag and upgrade it deliberately; it is a CI dependency like any other.

**From a laptop, not CI,** the same agent connection gives you `kubectl` without a distributed kubeconfig and without an inbound firewall rule. This is how a human reaches the cluster:

```sh
glab cluster agent list                                   # find the numeric agent ID
glab cluster agent update-kubeconfig --agent <id> --use-context
kubectl get nodes
```

It writes an exec-credential plugin entry into your kubeconfig, so tokens are minted on demand and cached rather than stored as a long-lived credential. Useful flags: `--token-expiry-duration` (minimum 1 day), `--cache-mode` (defaults to `force-keyring`), and `--kubeconfig` to write somewhere other than the default file. See [[glab-cli]] for the rest of the `glab cluster agent` surface.

### 5.6 Pipeline shape: diff → sync → deploy

This mirrors an OpenTofu `plan`/`apply` split, and it is the shape GitLab's own cluster-management template uses.

```yaml
stages: [diff, sync, deploy]

variables:
  CLUSTER_ENVIRONMENT: production
  MANIFESTS_PATH: clusters/production

k8s:diff:
  stage: diff
  image: registry.gitlab.com/charts/cluster-applications
  script:
    - gl-use-kube-context
    # kubectl diff exits 1 when a diff exists, so capture it and allow that code
    - kubectl diff -k "$MANIFESTS_PATH" | tee diff.txt || [ "${PIPESTATUS[0]}" -le 1 ]
  artifacts:
    when: always
    paths: [diff.txt]
  rules:
    - if: $CI_PIPELINE_SOURCE == "merge_request_event"

k8s:sync:
  stage: sync
  image: registry.gitlab.com/charts/cluster-applications
  script:
    - gl-use-kube-context
    - kubectl apply -k "$MANIFESTS_PATH"
  environment:
    name: $CLUSTER_ENVIRONMENT
    action: prepare
  resource_group: k8s-$CLUSTER_ENVIRONMENT
  rules:
    - if: $CI_COMMIT_BRANCH == $CI_DEFAULT_BRANCH
      when: manual
```

Key points:

- `diff` runs on **merge requests** and never mutates the cluster. `|| true` because `kubectl diff` exits non-zero on differences.
- `sync` is **manual on the default branch** and declares `environment: {action: prepare}` so it contributes deployments without claiming the environment's deploy status.
- `resource_group` serialises concurrent jobs per cluster, preventing two pipelines racing the same resources.
- With Flux as the GitOps engine, prefer letting Flux reconcile: use `diff` for review, `sync` for the exceptions (a rollback, a one-off state operation). Two writers to the same objects is drift by construction.

### 5.7 CI/CD components: check the catalog first

GitLab publishes CI/CD components in the [Component Catalog](https://components.gitlab.com/). Component paths and versions change, and old ones are removed — do not copy a path from memory or an old blog post. Before writing a custom job, search the catalog and prefer a maintained component. In particular, verify any GitLab agent component path and version at the moment you add it; the historical `components/agent` paths have moved. Validate with `glab ci lint`.

Read [[gitlab-cicd]] for the catalog workflow and [[glab-cli]] for `glab` usage.

---

## 6. GitOps

### 6.1 Principles

- Git is the source of truth; the cluster converges to it.
- **Pull, not push.** The agent's outbound connection means no inbound access for GitLab to push manifests.
- Drift is visible and expected to be reverted. Treat `OutOfSync` as a bug to diagnose, not a state to accept.
- Nothing is applied by hand. If you must, capture the result as a manifest in the same session.

### 6.2 Flux

Package model: `HelmRelease` CRs (`helm.toolkit.fluxcd.io/v2`), sources as `OCIRepository` / `HelmRepository` / `GitRepository` (`source.toolkit.fluxcd.io/v1`), Kustomizations as `kustomize.toolkit.fluxcd.io/v1`. Pin CRD apiVersions to what your installed Flux version provides — these have moved (`v2beta1` → `v2`) and Flux is strict about it.

Useful operational commands:

```sh
flux get kustomizations --all-namespaces --watch
flux get helmreleases --all-namespaces
flux reconcile kustomization apps --with-source
flux suspend kustomization apps      # emergency only; re-enable after
flux logs --follow
```

`flux suspend` is the correct emergency move: it stops the controller fighting you while you fix something, and it makes the drift explicit rather than hidden. Remember to unsuspend.

**Bootstrap** with `flux bootstrap gitlab` (GitLab-specific, supports `--deploy-token-auth`) or `flux bootstrap git` for a provider-neutral repo.

**Flux Operator** (`FluxInstance` CRD) is the current answer to "manage Flux across many clusters": declarative controller lifecycle, no Git write access needed (OIDC/GitHub Apps), tag-based promotion, automated controller and CRD upgrades, multi-tenancy lockdown, sharding, and a Git-less mode storing cluster state as OCI artifacts.

### 6.3 Argo CD — our controller

**Read [[argocd]] instead of this subsection** for anything you intend to act on: it covers installation, self-management, repository layout, `Application`/`ApplicationSet`/`AppProject`, every sync option, the GitLab integration, ESO ordering, RBAC and SSO, scaling, CVEs, and the per-chart gotchas. What follows is the orientation summary.

Useful commands:

```sh
argocd app list
argocd app diff <app>
argocd app sync <app>
argocd app logs <app>
```

- **Sync waves** order reconciliation: `argocd.argoproj.io/sync-wave`. Wave `-1` runs first.
- **Pre-sync hooks**: `argocd.argoproj.io/hook: PreSync`. This is the mechanism for anything that must happen before resources are applied — a database migration, an API registration, a lease release. Hooks are the standard answer to "this resource needs state that already exists".
- `selfHeal: true` reverts manual drift. `prune: true` deletes resources removed from Git. Both are usually correct; understand them before enabling either.
- app-of-apps (a root `Application` that generates children) is superseded by **ApplicationSet**, which is strictly better: no ordering assumptions, no child-generation commits.
- **ApplicationSet in any namespace** plus `spec.applicationSet.sourceNamespaces` on the ArgoCD CR allows tenants to own their Applications without cluster-admin. Relevant on managed and multi-tenant clusters.
- Image updates: Argo CD Image Updater, or let Renovate commit the digest and treat Git as the trigger. Prefer the latter when GitLab CI already runs Renovate — one mechanism, one audit trail.

### 6.4 Choosing

**Argo CD** — see §2.7 for the reasoning and [[argocd]] for the implementation. Flux is the alternative worth knowing, and GitLab's own recommendation, so §6.2 stays in this skill.

Either way the discipline is identical — declarative only, everything in Git, drift reverted. That is the part that transfers if you ever switch: your charts and values files do not change, only the thin wrapper layer does.

---

## 7. Workload manifests

### 7.1 Non-negotiables

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: my-app
  labels: &labels
    app.kubernetes.io/name: my-app
    app.kubernetes.io/instance: my-app
    app.kubernetes.io/component: server
    app.kubernetes.io/part-of: data-platform
    app.kubernetes.io/managed-by: argocd
spec:
  replicas: 3
  revisionHistoryLimit: 5
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1
      maxUnavailable: 0
  selector:
    matchLabels:
      app.kubernetes.io/name: my-app
      app.kubernetes.io/instance: my-app
  template:
    metadata:
      labels: *labels
    spec:
      securityContext:
        runAsNonRoot: true
        runAsUser: 1000
        fsGroup: 1000
        seccompProfile:
          type: RuntimeDefault
      terminationGracePeriodSeconds: 60
      topologySpreadConstraints:
        - maxSkew: 1
          topologyKey: kubernetes.io/hostname
          whenUnsatisfiable: DoNotSchedule
          labelSelector:
            matchLabels:
              app.kubernetes.io/name: my-app
              app.kubernetes.io/instance: my-app
      containers:
        - name: server
          image: registry.example.org/my-app@sha256:<digest>
          imagePullPolicy: IfNotPresent
          securityContext:
            allowPrivilegeEscalation: false
            readOnlyRootFilesystem: true
            capabilities:
              drop: ["ALL"]
          ports:
            - name: http
              containerPort: 8080
          resources:
            requests: {cpu: 100m, memory: 256Mi}
            limits:   {memory: 512Mi}
          startupProbe:
            httpGet: {path: /health/startup, port: http}
            periodSeconds: 5
            failureThreshold: 30
          readinessProbe:
            httpGet: {path: /health/ready, port: http}
            periodSeconds: 10
          livenessProbe:
            httpGet: {path: /health/live, port: http}
            periodSeconds: 10
          volumeMounts:
            - {name: tmp, mountPath: /tmp}
            - {name: cache, mountPath: /var/cache/my-app}
      volumes:
        - name: tmp
          emptyDir: {}
        - name: cache
          emptyDir: {}
---
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: my-app
spec:
  minAvailable: 2
  selector:
    matchLabels:
      app.kubernetes.io/name: my-app
      app.kubernetes.io/instance: my-app
```

Decisions embedded above, each of which matters:

| Choice | Reason |
|---|---|
| Digest, not tag | Reproducible rollouts and a verifiable identity |
| `maxUnavailable: 0` | No capacity loss during rollout; combined with a PDB and probes, deploys become non-events |
| `startupProbe` for slow starts | Lets you set a generous liveness failure threshold without tolerating slow starts forever |
| Separate readiness and liveness paths | Readiness removes the pod from Service endpoints on a graceful degradation; liveness only restarts a genuinely wedged process |
| `readOnlyRootFilesystem` + `emptyDir` for `/tmp` | Cheap immutability; find the paths that need writing rather than defaulting to writable |
| `drop: ["ALL"]` | Start from nothing and add back only what is required |
| `topologySpreadConstraints` | Spreads replicas across nodes so one node failure is not a total outage |
| PDB with `minAvailable` | Makes node drains safe. A PDB with no matching pods blocks drains forever — check the selector matches your pod labels |
| `runAsNonRoot` at pod level, capability drop per container | Both Pod Security Standards require them |

### 7.2 CPU limits: know your trade-off

CPU requests drive scheduling; CPU limits throttle. Setting a CPU limit equal to the request causes throttling under burst and inflates cost; omitting limits risks a noisy neighbour taking the node down. The common middle ground: **always set memory requests and limits** (memory is incompressible, so a limit is a safety valve) and **set CPU requests, with limits only where you need a hard ceiling**. Validate the choice against how your workload actually behaves rather than copying a template.

### 7.3 Jobs and CronJobs

```yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: batch-run
spec:
  backoffLimit: 3
  ttlSecondsAfterFinished: 86400
  completions: 1
  parallelism: 1
  template:
    spec:
      restartPolicy: Never
      containers:
        - name: worker
          image: registry.example.org/batch@sha256:<digest>
          resources:
            requests: {cpu: "2", memory: 2Gi}
            limits:   {memory: 8Gi}
```

- `restartPolicy: Never` for Jobs; `OnFailure` if you want retries in-place.
- `ttlSecondsAfterFinished` cleans up so you do not accumulate thousands of completed Jobs — set it longer than your longest debugging window.
- `backoffLimit: 0` for jobs you would rather fail loudly than retry silently.

CronJobs:

```yaml
apiVersion: batch/v1
kind: CronJob
spec:
  schedule: "17 3 * * *"
  timeZone: Europe/Amsterdam     # explicit; never rely on the controller's local zone
  concurrencyPolicy: Forbid
  startingDeadlineSeconds: 600
  successfulJobsHistoryLimit: 3
  failedJobsHistoryLimit: 3
  jobTemplate:
    spec:
      backoffLimit: 2
      template:
        spec:
          restartPolicy: Never
          containers: [...]
```

`concurrencyPolicy: Forbid` prevents overlapping runs — set it unless overlap is genuinely wanted. `timeZone` avoids the classic "it ran at 2am because the controller is UTC" bug.

### 7.4 StatefulSets

Use when you need stable network identities, ordered rollout, or per-replica storage. Otherwise a Deployment plus a headless Service is simpler. Each replica gets a PVC from `volumeClaimTemplates`; **the PVC is not deleted when the StatefulSet scales down**, which is both the feature (data survives) and the trap (storage leaks unless you clean up deliberately).

### 7.5 Ephemeral volumes

`emptyDir` for scratch, `generic.ephemeral` for a pod-scoped PVC that is garbage-collected with the pod. Both are correct choices — knowing which is which prevents surprise data loss.

### 7.6 PriorityClass: protect the platform from the workloads

**Without priority classes, a cluster under memory pressure can evict Argo CD, the CNI agent or ESO to make room for a batch job.** The eviction is then self-inflicted and self-sustaining: the thing that would fix the cluster is the thing that got evicted. On a cluster that runs Spark or any bursty batch workload (§15.2) this is not hypothetical.

Kubernetes ships two built-in classes — `system-cluster-critical` and `system-node-critical` — reserved for genuine cluster components. Add two of your own for the tiers in between:

```yaml
apiVersion: scheduling.k8s.io/v1
kind: PriorityClass
metadata:
  name: platform
value: 100000
globalDefault: false
description: "Platform controllers: Argo CD, ESO, cert-manager, gateway, monitoring."
---
apiVersion: scheduling.k8s.io/v1
kind: PriorityClass
metadata:
  name: application
value: 1000
globalDefault: true          # everything unlabelled lands here
description: "Normal application workloads."
---
apiVersion: scheduling.k8s.io/v1
kind: PriorityClass
metadata:
  name: batch-besteffort
value: 100
preemptionPolicy: Never       # queues instead of evicting someone else
description: "Batch jobs. First to be evicted, never preempts."
```

Three rules that make this work rather than just exist:

- **Set exactly one `globalDefault: true`.** Without a default, pods with no class get priority `0`, which is below `batch-besteffort` — the opposite of what you intended.
- **`preemptionPolicy: Never` on batch** means a large Spark job waits for capacity instead of evicting a web workload to get it. Combined with Kueue (§10.7) this is how a shared pool stays predictable.
- **Priority is not a resource guarantee.** It decides who gets evicted first under pressure; it does not create capacity. Requests still do the real work.

### 7.7 Pulling from a private registry

A GitLab project registry needs credentials, and the failure mode is `ImagePullBackOff` with `no basic auth credentials` — which reads like a bad tag.

```yaml
spec:
  template:
    spec:
      imagePullSecrets:
        - name: registry-credentials
```

Two things to get right:

- **`imagePullSecrets` is namespaced.** The Secret must exist in *every* namespace that pulls, which is exactly the repetitive work ESO is for — one `ExternalSecret` per namespace sourced from the same Vault path, or a Kyverno `generate` policy that clones it into new namespaces automatically (§11.3). Do not copy it by hand; it will be missing in the one namespace you forget.
- **Use a deploy token or a project access token**, scoped to `read_registry` only, not a personal token. The same credential discipline as [[argocd]] §10.4.

Alternatively, attach the Secret to the workload's ServiceAccount (`imagePullSecrets` on the ServiceAccount) so every pod using that account inherits it — less repetition in manifests, same namespacing constraint.

---

## 8. Networking

### 8.1 Services

| Type | Use |
|---|---|
| `ClusterIP` | Default. Only reachable inside the cluster |
| `NodePort` | Rare. Simplest path for a dev cluster with no ingress controller |
| `LoadBalancer` | Provider-managed external IP. Usually prefer an ingress/gateway controller instead so TLS and routing live in one place |
| Headless (`clusterIP: None`) | StatefulSet stable DNS, client-side load balancing, and StatefulSet peer discovery |

### 8.2 Ingress vs Gateway API

**Gateway API is the current recommendation.** It is the successor to Ingress and is what current reference implementations (including Flux's) use by default. Ingress is not deprecated but is feature-frozen relative to Gateway API.

| | Ingress | Gateway API |
|---|---|---|
| Model | One resource with annotations | `GatewayClass` → `Gateway` → `HTTPRoute`/`GRPCRoute`/`TLSRoute` |
| Cross-namespace | Awkward | First-class `ReferenceGrant` |
| Weighting/redirects | Annotation-dependent | Structured `rules`, `filters`, `backendRefs` weights |
| Namespaces | Ingress lives in one | Gateways can be central or delegated per team |

```yaml
apiVersion: gateway.networking.k8s.io/v1
kind: Gateway
metadata:
  name: public
  namespace: gateway-system
spec:
  gatewayClassName: envoy        # or nginx, cilium
  listeners:
    - name: http
      protocol: HTTP
      port: 80
      allowedRoutes:
        namespaces:
          from: All              # or Selector for a strict allow-list
    - name: https
      protocol: HTTPS
      port: 443
      tls:
        mode: Terminate
        certificateRefs:
          - kind: Secret
            name: wildcard-tls
            namespace: gateway-system
---
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: my-app
  namespace: my-app
spec:
  parentRefs:
    - name: public
      namespace: gateway-system
      sectionName: https
  hostnames: ["my-app.example.org"]
  rules:
    - matches:
        - path:
            type: PathPrefix
            value: /
      backendRefs:
        - name: my-app
          port: 8080
          weight: 100
```

`allowedRoutes` is the multi-tenancy boundary: leave it at `All` on a single-tenant cluster, switch to a `Selector` listing permitted namespaces the moment another team shares the cluster.

Verify the Gateway API CRD version your cluster has before writing manifests — check `helm show crds` for the controller chart and `kubectl explain gateway.networking.k8s.io` after install.

**Which controller to run is a real decision — see §8.8.** The Gateway API is a spec, and implementations differ substantially in how much of it they actually implement.

### 8.3 TLS: cert-manager

```yaml
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: letsencrypt
spec:
  acme:
    server: https://acme-v02.api.letsencrypt.org/directory
    email: platform@example.org
    privateKeySecretRef:
      name: letsencrypt-account-key
    solvers:
      - dns01:
          route53:            # or your DNS provider
            region: eu-west-1
```

| Solver | Use when | Cost |
|---|---|---|
| `http01` | Public ingress, no wildcard needed | Easiest; port 80 must be reachable |
| `dns01` | Wildcards, or no public ingress | Needs DNS API credentials |
| Self-signed `Issuer` | Internal-only, no public trust needed | Every client must trust the CA |

Reference check: start at the ACME **staging** endpoint while iterating, then switch to production. Rate limits on production are unforgiving.

### 8.4 NetworkPolicy

`NetworkPolicy` is **additive and namespace-scoped**: a pod selected by *any* policy becomes isolated for that traffic direction, and a pod selected by *no* policy allows all traffic. This is why "I added a policy and broke DNS" happens — the DNS egress rule was never written.

Default posture:

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: default-deny
  namespace: my-app
spec:
  podSelector: {}
  policyTypes: [Ingress, Egress]
---
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-dns
  namespace: my-app
spec:
  podSelector: {}
  policyTypes: [Egress]
  egress:
    - to:
        - namespaceSelector:
            matchLabels:
              kubernetes.io/metadata.name: kube-system
          podSelector:
            matchLabels:
              k8s-app: kube-dns
      ports:
        - protocol: UDP
          port: 53
        - protocol: TCP
          port: 53
```

The last policy is the one people forget.

### 8.5 CNI and Cilium

**The CNI you choose determines whether NetworkPolicy works at all.** This is not a detail — a CNI without a policy engine silently ignores every `NetworkPolicy` you write.

| CNI | NetworkPolicy | L7 policy | Notes |
|---|---|---|---|
| flannel | **No** | No | Minimal; fine for throwaway clusters, wrong for anything else |
| Calico | Yes | Limited | Long-standing default |
| Cilium | Yes | Yes (via `CiliumNetworkPolicy`) | eBPF-based; Hubble for flow visibility; also kube-proxy replacement |

**If your cluster runs flannel, NetworkPolicy is a no-op and default-deny is impossible.** Migrating to Cilium is a prerequisite for any real isolation story, and it also unlocks:

- **L7 policy** — restrict by HTTP method, path, or gRPC service rather than port.
- **Hubble** — `hubble observe` gives live flow logs; you can alert on denied connections.
- GitLab agent **network-policy alerting**: the agent can emit events when traffic is denied, which is genuinely useful for spotting a mis-scoped egress rule before it breaks a job.

Cilium also replaces kube-proxy (eBPF datapath) if you want it — a separate decision, worth evaluating separately.

### 8.6 Publishing names: ExternalDNS

**A `Gateway` with `hostnames: ["my-app.example.org"]` does not create that DNS record.** Nothing in §8.2 or §8.3 does. This is the gap that makes a correct-looking setup unreachable, and it also blocks cert-manager's `http01` solver and `dns01` validation — so it is a dependency of TLS, not a nicety.

Two honest options:

| Approach | Use when |
|---|---|
| **ExternalDNS** reconciles records from cluster objects | You have a DNS provider with an API and more than a couple of hostnames |
| A static record per Gateway, managed in your IaC | One or two stable entry points; the gateway address rarely changes |

The static route is perfectly respectable: with one `Gateway` per cluster, you create one wildcard record (`*.development.example.org`) pointing at the Octavia or MetalLB address in [[naturalis-opentofu]], and every `HTTPRoute` hostname underneath it resolves with no controller at all. Prefer this until the number of distinct entry points makes it annoying.

If you do run ExternalDNS, two things to know:

- **Point it at Gateway API routes, not just Ingress.** It supports `HTTPRoute`/`GRPCRoute`/`TLSRoute` as sources, which is what you need given §8.2 — the Ingress-only default source will silently publish nothing.
- **OpenStack Designate is no longer an in-tree provider.** As of ExternalDNS v0.23.0 it is a **webhook provider** maintained outside the project (`inovex/external-dns-designate-webhook`), which means an extra sidecar and a different support expectation. Factor that in before assuming "ExternalDNS supports Designate" means first-class support.

Always scope it with `--domain-filter` and a `--txt-owner-id`. Without an owner ID, two clusters sharing a zone will fight over records and delete each other's.

### 8.7 DNS and service mesh

Cluster DNS is `kube-dns`/`CoreDNS` via the `kubernetes.default` Service; the search path means in-cluster FQDNs are needed for cross-namespace names. Keep the default; do not build a mesh to solve a naming problem.

A service mesh (Linkerd, Istio) is justified by mTLS everywhere, traffic management across many services, and fine-grained L7 routing. It is not justified by "we might need it later" — it adds a control plane, a failure domain, and a learning curve to every request path.

### 8.8 Choosing a Gateway controller

"Supports Gateway API" is not a yes/no. The project publishes **conformance reports** per implementation, per release, and the gaps are specific and material. Read the actual report rather than a vendor claim: `kubernetes-sigs/gateway-api` → `conformance/reports/<gw-api-version>/<implementation>/`.

Verified from the v1.6 reports (all against Gateway API **v1.6.1**):

| Controller | Version tested | `GATEWAY-HTTP` core | Profiles covered | Unsupported extended (HTTP) |
|---|---|---|---|---|
| **Envoy Gateway** | v1.9.0 | success | HTTP, GRPC, TLS | **2** — the most complete |
| **Cilium** | v1.20.0 | success | HTTP, GRPC, TLS, TCP, UDP, **+ mesh** | 6 |
| **NGINX Gateway Fabric** | v2.7.0 | success | HTTP, GRPC, TLS, TCP, UDP | 8 — no timeouts or retries |
| **Traefik** | v3.7.10 | **partial** | HTTP, GRPC, TLS | 19 |

**The recommendation, in order:**

1. **If you run Cilium for NetworkPolicy (§8.5), use Cilium's Gateway.** This is the strongest answer for us. It is fully conformant on every profile including mesh, and it is **one fewer control plane, one fewer data plane, one fewer upgrade cycle** — the gateway becomes a feature of the CNI you already operate rather than another component. For a small team that operational saving outweighs Envoy Gateway's slightly better feature coverage.
2. **If you are not on Cilium, use Envoy Gateway.** It is the most complete Gateway API implementation by conformance, and Envoy is the data plane most of the ecosystem converged on.
3. **Traefik is a legitimate choice, with one caveat you must check first.**

### On Traefik specifically

If Traefik is already the organisation's standard, that familiarity is worth real money — existing dashboards, existing runbooks, colleagues who can debug it. Do not discard it for a conformance table. But know exactly what you are accepting:

Traefik v3.7.10 reports **`core: partial`** on `GATEWAY-HTTP`, and its unsupported extended features include **`HTTPRouteRequestTimeout`, `HTTPRouteBackendTimeout`, `HTTPRouteRetry` (all variants), `HTTPRouteCORS`, and `HTTPRouteRequestMirror` (all variants)**, plus `GatewayHTTPListenerIsolation` and `ListenerSet`.

In plain terms: **through Gateway API, Traefik gives you host/path routing, TLS termination and traffic weighting, but not timeouts, retries, CORS or request mirroring.** Traefik does support all of those — through its own `Middleware` and `IngressRoute` CRDs. So the practical consequence is not "Traefik can't do it", it is:

> The moment you need a retry or a timeout, you drop out of the portable Gateway API and into Traefik-specific CRDs — which re-couples your routing layer to one vendor and gives up the main reason to adopt Gateway API in the first place.

So the decision rule is:

- **Only host/path routing and TLS, and Traefik is the house standard** → use Traefik. Perfectly sound, and the team knowledge is a genuine advantage.
- **You need timeouts, retries, mirroring or CORS declaratively** → Cilium or Envoy Gateway, or accept Traefik CRDs and document that you have done so.
- **Mixed estate** → pick one per cluster. Two gateway controllers in one cluster is two failure domains and two sets of CRDs for one job.

Confirm what the organisation actually runs, and at what version, before committing — and if it is Traefik v2.x, note that Gateway API support is a **v3** feature, so an upgrade is part of the work either way. See [[naturalis-kubernetes]] for our own estate. Record the decision and its reason in the platform repo; this is exactly the kind of choice that is expensive to revisit silently.

## 9. Storage

### 9.1 The resource hierarchy

```
StorageClass  →  PersistentVolume  →  PersistentVolumeClaim  →  Pod
   provisioner      actual backing      the request           the mount
```

- **StorageClass** names a provisioner and its parameters.
- **PV** is the actual storage, usually created dynamically by the provisioner.
- **PVC** is a request and a claim on a PV.

### 9.2 StorageClass essentials

```yaml
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: standard
provisioner: cinder.csi.openstack.org    # OpenStack; see §3 "OpenStack platform integration"
parameters:
  availability: nova                     # Cinder AZ
  type: <cinder-volume-type>             # must already exist in Cinder
reclaimPolicy: Delete        # Retain for anything you would be sad to lose
allowVolumeExpansion: true   # you will need this
volumeBindingMode: WaitForFirstConsumer   # let the scheduler pick the zone
```

**`parameters` are driver-specific and do not transfer.** This is the single most common copy-paste failure in storage config, because a wrong parameter is rejected at provisioning time, not at apply time — the `StorageClass` applies cleanly and then every PVC sits `Pending` with an error buried in the external-provisioner logs. Cinder accepts only `availability`, `type`, `appendVolumeMetadata` and `mkfs-options`. AWS EBS parameters such as `type: gp3` and `encrypted: "true"` are **not** valid for Cinder: `gp3` is not a Cinder volume type, and there is no `encrypted` parameter at all — encryption is a property of the Cinder volume type, configured in OpenStack by the operator, so you request it by naming an encrypted volume type.

Three defaults that save pain:

- **`volumeBindingMode: WaitForFirstConsumer`** — with the default `Immediate`, a PVC binds before the pod is scheduled, so a volume can land in an unavailable zone while the pod waits for one elsewhere.
- **`allowVolumeExpansion: true`** — a PVC you cannot grow is a PVC you cannot keep.
- **Check your AZ topology before trusting `availability`.** If the Cinder AZs do not match the Nova AZs, set `ignore-volume-az: true` in the driver's `[BlockStorage]` cloud config, or pods stay `Pending` with no useful event.

### 9.3 Choosing storage per workload

| Workload | Storage | Why |
|---|---|---|
| Object data (Parquet, media) | Object storage via CSI or direct SDK/S3 API | Cluster-native object storage drivers are immature; talk to S3 directly from the job |
| Databases, queues | **Outside the cluster** | See §1 |
| Caches, scratch, build output | `emptyDir` | Ephemeral by design |
| Logs that must survive a pod | Small PVC, or ship them out | Never write logs to `emptyDir` and hope |
| Anything with a StatefulSet | PVC via `volumeClaimTemplates` | Stable identity + storage |

**Important**: PVs are zone- or node-bound. A StorageClass without topology awareness plus a `topologySpreadConstraints` Deployment will leave you unable to schedule pods once the PVs land in one zone. If your storage is zonal, either use a topology-aware StorageClass or accept that replicas are zone-pinned — and put the anti-affinity in the right layer.

### 9.4 Backup and disaster recovery

The good news for a GitOps cluster is that most of it is disposable: the manifests live in Git, the applications are rebuilt from images, and the data is in object storage and external databases (§1). What is *not* disposable is the cluster state and the few things that were never in Git.

| What | How to protect it | Where the backup goes |
|---|---|---|
| **etcd** (all cluster state, secrets, CRs) | `etcdctl snapshot save` on a schedule, or the distribution's built-in snapshot (k3s, k0s) | **Outside the cluster.** A snapshot stored in the cluster is not a backup |
| **PersistentVolumes** | Velero with a volume snapshotter or restic/kopia file-level backup | Object storage in a separate account/bucket |
| **CRDs and cluster-scoped objects** | Velero, or simply keep them in Git (they should be) | Git is the primary; Velero is the safety net |
| **External databases** (Postgres, ClickHouse) | Their own backup tooling — this is why they live outside the cluster | Their own backup targets |

Rules that turn a backup into a recovery:

- **Test the restore.** An untested backup is a hypothesis. Restore into a scratch cluster on a schedule and record how long it took — the time is your real RTO, and it is usually longer than assumed.
- **etcd is the recovery point for the control plane.** Losing it without a snapshot means rebuilding the cluster from Git and re-issuing every certificate; that is a rebuild, not a restore.
- **Git is not a backup for runtime state.** It restores the *desired* state. Anything created imperatively, or any secret not in Vault, is gone.
- **Back up the secrets store separately.** If Vault is the source of truth, its own backup and unseal story is the critical path — not the cluster's.
- **Restore order:** control plane (etcd) → CRDs/controllers → configs → apps, mirroring the layering in §2.3. A restore that starts with apps will fail on missing CRDs.
- **Velero needs the CRDs it backs up.** Back up and restore cluster-scoped resources deliberately, and be aware that some operators do not survive a naive restore.

For a stateless GitOps cluster the honest summary is: **snapshot etcd, back up the few PVCs, and rehearse the rebuild.** The rebuild is the disaster plan, and it only works if everything important is already in Git and Vault.

---

## 10. Autoscaling

### 10.1 The four layers

Scaling problems are usually layer-confusion. Know which question each layer answers.

| Layer | Scales | Use when |
|---|---|---|
| **HPA** | Pod replicas within a workload | Traffic or CPU tracks demand predictably |
| **VPA** | A pod's resource requests (not replicas) | Requests are wrong; you do not know the right number by hand |
| **Karpenter** / cluster-autoscaler | Nodes | Pods are Pending because there is no room |
| **KEDA** | Pods from event sources, including to zero | Demand comes from queues, schedules, or external signals |

The dependency chain is not optional:

```
metrics-server  →  HPA and VPA can read usage at all
VPA recommender  →  HPA gets accurate requests to scale on
node autoscaler  →  new nodes when HPA/KEDA raised the replica count
```

**Without `metrics-server`, HPA, VPA, and `kubectl top` are all non-functional.** It is a small install that unblocks an entire category of feature. Check for it first when autoscaling "does nothing".

These layers scale workloads. They do not arbitrate between competing batch jobs or cap a team's share of the pool — that is Kueue's job (§10.7).

### 10.2 HPA

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: my-app
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: my-app
  minReplicas: 3
  maxReplicas: 20
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70
  behavior:
    scaleUp:
      stabilizationWindowSeconds: 30
      policies: [{type: Percent, value: 100, periodSeconds: 30}]
    scaleDown:
      stabilizationWindowSeconds: 300
      policies: [{type: Percent, value: 20, periodSeconds: 60}]
```

Scale up fast, scale down slowly. A `scaleDown` window of a few minutes is the difference between a stable replica count and thrashing on every traffic ripple.

### 10.3 VPA

Use it in `Off` mode to start with — it reports recommendations without touching anything:

```yaml
apiVersion: autoscaling.k8s.io/v1
kind: VerticalPodAutoscaler
metadata:
  name: my-app
spec:
  targetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: my-app
  updatePolicy:
    updateMode: "Off"          # report only
  resourcePolicy:
    containerPolicies:
      - containerName: server
        minAllowed:
          cpu: 100m
          memory: 128Mi
        maxAllowed:
          cpu: "4"
          memory: 8Gi
```

Read the recommendations, feed them into your requests as fixed values, then decide whether to automate. `Auto` lets VPA evict pods to resize, which is disruptive; in-place update is preferred and controlled by the update mode (`InPlaceOrRecreate` where the kubelet supports it). Current guidance is to prefer in-place behaviour; the older `Auto` shorthand is deprecated in recent VPA releases, so check the CRD schema for the version you have rather than copying an example.

VPA and HPA on the same Deployment will fight unless the HPA is told VPA owns the resource. Newer VPA requires an explicit HPA-ownership annotation or validation rejects the overlap — the safest rule is: **VPA owns requests, HPA owns replicas, and the target metric for HPA should be something VPA is not managing** (external metrics, or resource metrics where you accept the interaction and configure it).

### 10.4 Node autoscaling

| | cluster-autoscaler | Karpenter |
|---|---|---|
| Scales | Node groups / instance templates | Individual nodes, provisioned on demand |
| Provisioning | Slow: group must exist and grow | Fast: creates exactly the node needed |
| Consolidation | No | Yes — replaces underused nodes of the right size |
| Bin packing | No | Yes |
| Cloud | Broad | AWS-first, with other providers |
| Fit for | Static node groups you control | Minimising cost on a large fleet |

Karpenter's core idea is that you declare a `NodePool` (instance types, capacity types, limits) and it continuously replaces underutilised nodes with correctly-sized, cheaper ones. Relevant concepts: consolidation, `expireAfter` on node claims, and disruption budgets to keep voluntary disruptions safe.

On OpenStack, neither is a first-class fit. The realistic self-hosted approach is capacity planning with a headroom buffer — scale the OpenStack VM count yourself with [[naturalis-opentofu]] / [[biocloud-pyinfra]] and let HPA/KEDA absorb the variation inside the fixed node count. If you migrate to a provider-managed control plane, revisit whether their managed node autoscaler or Karpenter-equivalent is available.

### 10.5 KEDA

```yaml
apiVersion: keda.sh/v1alpha1
kind: ScaledObject
metadata:
  name: my-app
  namespace: my-app
spec:
  scaleTargetRef:
    name: my-app
  minReplicaCount: 0            # scale to zero only if the app tolerates cold start
  maxReplicaCount: 30
  cooldownPeriod: 300
  fallback:
    failureThreshold: 3
    replicas: 3                # what to do when the scaler cannot reach its source
  triggers:
    - type: rabbitmq
      metadata:
        queueName: jobs
        queueLength: "50"
        mode: QueueLength
```

Key behaviours that cause surprises:

- **Scale to zero requires the platform to handle cold starts.** With `minReplicaCount: 0`, a request arriving at an idle system pays the full startup latency. Use a minimum of 1 for anything user-facing.
- **`cooldownPeriod` delays scale-to-zero**, and its default is longer than people expect.
- **`fallback`** is what happens when the event source is unreachable — without it, KEDA has no metrics and does nothing. Set it deliberately rather than inheriting a default.
- **A cron trigger's `desiredReplicas` is a floor, not a target.** It ensures at least N replicas at that time; it does not hold exactly N. Use an HPA or a fixed `replicas` if you need an exact value.
- `ScaledObject` scales a Deployment; `ScaledJob` drives a job per event — the right choice for one-shot work.

### 10.6 Choosing

- Steady web traffic, CPU-bound → **HPA** on CPU.
- Steady web traffic, wrong requests → **VPA in `Off`**, fix the numbers.
- Queue or stream consumer → **KEDA**.
- Anything that must go to zero overnight → **KEDA**, with cold starts accepted.
- Nodes are the constraint → **Karpenter** on a cloud with support, otherwise plan capacity.
- Many independent batch jobs competing for one pool → **Kueue** (§10.7), not an autoscaler.

### 10.7 Queue-based scheduling (Kueue)

The four layers above scale a workload up and down. None of them answers "which of these twenty batch jobs runs first, and how much of the cluster is each team allowed?" That is a queueing problem, and **Kueue** is the Kubernetes-native answer.

| Concept | What it does |
|---|---|
| `ResourceFlavor` | A class of nodes (e.g. a Spark job pool vs general workloads) |
| `ClusterQueue` | Quota and fair-share policy over flavors — the pool's capacity |
| `LocalQueue` | The per-namespace handle users submit to |
| Workload | The admission unit; a job is admitted only when quota is free |

Why it matters for a data platform:

- **Gang scheduling.** A distributed job needs all its pods or none. Kueue admits the whole workload atomically, so a Spark job does not start its driver and then starve waiting for executors.
- **Quota without hard namespaces.** Teams share a pool; each `ClusterQueue` caps what a team can borrow, and unused quota is lent to others by fair sharing.
- **Preemption and priorities** so a nightly critical job can take capacity from a best-effort one.
- **Queueing instead of failing.** A job that does not fit waits in the queue rather than flapping or leaving a half-created deployment.

Kueue integrates with Jobs, JobSets, and the Spark operator's `SparkApplication`. If there is exactly one team and one job type, it is overkill; the moment a second team or a second competing job type exists, it is the difference between a predictable platform and a race for capacity.

---

## 11. Security

### 11.1 Pod Security Standards

Three levels, enforced at admission:

| Level | Enforces |
|---|---|
| `privileged` | Nothing extra (only useful with Admission Control) |
| `baseline` | No host namespaces, no privileged containers, default capabilities only, no `hostPath`, seccomp required |
| `restricted` | Everything in baseline plus `runAsNonRoot`, non-root user, drop `ALL` capabilities, no privilege escalation, seccomp `RuntimeDefault` |

Enforce per namespace with labels. Start in audit, watch, then enforce — jumping straight to enforce in a namespace with existing workloads takes them down:

```sh
kubectl label --overwrite ns my-app pod-security.kubernetes.io/enforce=restricted \
  pod-security.kubernetes.io/enforce-version=v1.37
kubectl label --overwrite ns my-app pod-security.kubernetes.io/audit=restricted \
  pod-security.kubernetes.io/warn=restricted
```

Target `restricted` for all application namespaces. Use `privileged` only for genuinely privileged add-ons (CNI agents, CSI drivers, node-exporter), each in its own namespace with a documented reason.

Note: recent releases tightened host-level probe and `/proc` access restrictions at `baseline` and above. An old privileged pod that used host HTTP probes can fail admission after an upgrade even though nothing in your manifests changed. When a version bump breaks admission unexpectedly, check the PSA level of the affected namespace before debugging the workload.

### 11.2 The per-namespace baseline

Every application namespace should get the same four objects, applied as a Kustomize component (§2.5) so there is one definition rather than a copy per app. PSA labels are the admission control; these are the resource and network control.

```yaml
apiVersion: v1
kind: ResourceQuota
metadata:
  name: baseline
spec:
  hard:
    requests.cpu: "8"
    requests.memory: 16Gi
    limits.memory: 32Gi
    persistentvolumeclaims: "10"
    count/deployments.apps: "20"
---
apiVersion: v1
kind: LimitRange
metadata:
  name: baseline
spec:
  limits:
    - type: Container
      default:                  # applied when a container sets no limit
        memory: 512Mi
      defaultRequest:           # applied when a container sets no request
        cpu: 100m
        memory: 128Mi
      max:
        memory: 8Gi
```

The behaviour that surprises people: **once a `ResourceQuota` sets any `requests.*` or `limits.*`, every pod in that namespace must specify the corresponding field, or admission rejects it.** A `LimitRange` with `defaultRequest` is what keeps that from breaking existing workloads — it fills in the missing values instead of failing them. Apply the `LimitRange` first, or at the same time.

Pair both with the `default-deny` plus `allow-dns` NetworkPolicy from §8.4. And note from [[argocd]] §12.1 that the `applications` AppProject deliberately **blocks** apps from defining their own `ResourceQuota`, `LimitRange` and `NetworkPolicy` — otherwise this baseline is advisory rather than enforced.

### 11.3 Policy as code

| Tool | Model | Use for |
|---|---|---|
| **Kyverno** | `validate` / `generate` / `mutate` / `verifyImages` | The default choice. Can both block and inject defaults |
| OPA Gatekeeper | Constraints + templates | Rego power, heavier |
| ValidatingAdmissionPolicy (built-in) | CEL expressions | Simple checks with no extra component |

Kyverno examples:

```yaml
apiVersion: kyverno.io/v1
kind: ClusterPolicy
metadata:
  name: require-resource-limits
spec:
  validationFailureAction: Enforce
  rules:
    - name: require-limits
      match:
        any:
          - resources:
              kinds: ["Deployment", "StatefulSet"]
      validate:
        message: "Containers must define CPU and memory limits."
        pattern:
          spec:
            template:
              spec:
                containers:
                  - resources:
                      limits:
                        memory: "?*"
---
apiVersion: kyverno.io/v1
kind: ClusterPolicy
metadata:
  name: require-non-root
spec:
  validationFailureAction: Enforce
  rules:
    - name: no-latest-tag
      match:
        any:
          - resources:
              kinds: ["Pod", "Deployment", "StatefulSet", "Job", "CronJob"]
      validate:
        message: "Images must use a digest or an explicit version, never :latest."
        pattern:
          spec:
            template:
              spec:
                containers:
                  - image: "!*:latest"
```

Run the same policies in CI against the rendered output (§2.8) so violations are caught at review time, not admission time.

### 11.4 Supply chain

- **Scan images** (Trivy, Grype) in CI and continuously in-cluster (Trivy Operator) so newly published CVEs are surfaced without a redeploy.
- **Sign and verify.** cosign signs images; a Kyverno `verifyImages` policy rejects unsigned ones at admission. Verification at admission is what turns a policy into a guarantee.
- **Pin by digest** for anything that matters. Tags are mutable.
- **Minimal base images** (`distroless`, `chainguard`) shrink both the CVE surface and the attack surface.
- Renovate or Dependabot keeps base images and charts current — treat that as part of the security model, not chore work.

### 11.5 RBAC and runtime

- Never bind `cluster-admin` to a workload or a CI job.
- Never use the `default` ServiceAccount for a workload. Create a named one per workload; `automountServiceAccountToken: false` unless it calls the API.
- `Role`/`RoleBinding` per namespace; `ClusterRole` only for genuinely cluster-scoped objects.
- Wildcards (`resources: ["*"]`, `verbs: ["*"]`) are equivalent to cluster-admin. Audit for them.
- `runtimeClassName` for sandboxed runtimes (gVisor, Kata) where untrusted code runs; a real control, not a checkbox.
- AppArmor profiles and seccomp for defence in depth beyond PSA.
- Enable API server audit logging, and alert on secret reads.

---

## 12. Secrets

### 12.1 Principles

1. **No secret values in Git.** Not plaintext, not base64, not "encrypted with a key in the same repo".
2. **No `kubectl create secret` in production.** That state is untracked and unrecoverable.
3. **One source of truth for secrets**: your secret manager.
4. **Everything else is a reference** to that source.

### 12.2 Options

| Tool | Mechanism | Use when |
|---|---|---|
| **External Secrets Operator (ESO)** | Syncs Vault/Cloud Secret Manager/etc. into `Secret` objects | Default choice. Vendor-neutral, declarative, well-supported |
| Vault Agent Injector | Sidecar writes secrets to a shared volume | You already run Vault and prefer not to mirror secrets into the cluster |
| Vault Secrets Operator (VSO) | CSI driver, secrets mounted as files | Avoids a Kubernetes `Secret` entirely |
| Sealed Secrets | Client-side encryption, controller decrypts in-cluster | Offline/air-gapped; or you accept storing a private key in-cluster |
| SOPS + age | Encrypt files in Git | Config you want reviewable in diffs; not for runtime-only values |
| `kubectl create secret` | — | Local development only |

### 12.3 External Secrets Operator

Three custom resources:

| Kind | Scope | Purpose |
|---|---|---|
| `SecretStore` | Namespaced | Connection details for a secret backend |
| `ClusterSecretStore` | Cluster | Shared store, referenced by namespaced secrets |
| `ExternalSecret` | Namespaced | The synchronisation rule |

```yaml
apiVersion: external-secrets.io/v1
kind: ClusterSecretStore
metadata:
  name: vault
spec:
  provider:
    vault:
      server: "https://vault.example.org"
      path: "<kv-mount>"            # the KV v2 mount name
      version: "v2"
      auth:
        # Authenticate with the cluster's identity, not a static token
        kubernetes:
          mountPath: "kubernetes"       # where the auth method is mounted in Vault
          role: "<vault-role>"          # required; bound server-side to the ServiceAccount
          serviceAccountRef:
            name: eso-vault-auth
            namespace: external-secrets  # mandatory on a ClusterSecretStore
            audiences:
              - vault                    # required from Vault 1.21; see below
---
apiVersion: external-secrets.io/v1
kind: ExternalSecret
metadata:
  name: my-app-db
  namespace: my-app
spec:
  refreshInterval: 1h
  secretStoreRef:
    name: vault
    kind: ClusterSecretStore
  target:
    name: my-app-db
    creationPolicy: Owner          # delete the Secret when the ExternalSecret goes
    template:
      type: kubernetes.io/basic-auth
  data:
    - secretKey: username
      remoteRef:
        key: databases/my-app
        property: username
    - secretKey: password
      remoteRef:
        key: databases/my-app
        property: password
```

Three things that matter more than the rest:

- **Use workload identity for the store, not a static token.** A static Vault token in a `SecretStore` is one rotation away from being a stale credential and a security review finding. Vault's Kubernetes auth method, or JWT/OIDC auth, means the secret store's own credentials rotate automatically.
- **Set `audiences` — this is a scheduled outage otherwise.** ESO's Vault provider documents it plainly: from **Vault 1.20** a role without an audience logs a warning during authentication, and in **Vault 1.21 and later authentication fails**. The audience is requested on the ESO side (`serviceAccountRef.audiences`) and must match what the Vault role expects. A cluster that works today breaks on the Vault upgrade, with a 403 that reads like a policy problem.
- **Get the auth stanza shape right.** `auth.kubernetes` takes `mountPath`, a **required** `role`, and then *either* `serviceAccountRef` *or* `secretRef` — never both. If you use `auth.jwt` instead, the ServiceAccount goes under `kubernetesServiceAccountToken.serviceAccountRef`, not directly under `jwt`; there is no `audience` (singular) field and no `jwtProvider` field anywhere in the CRD. Guessing here produces a manifest the API server rejects.
- **`refreshInterval` bounds staleness.** A value that changes in Vault will not reach the pod until the next refresh *and* until the pod restarts or reloads it. If the app supports hot reload, use it; otherwise expect a rollout.
- **`creationPolicy: Owner`** ties the lifecycle together so deleting the `ExternalSecret` removes the `Secret`.

**Check which CRD `apiVersion` your install serves.** `external-secrets.io/v1` is the current GA and what a recent chart serves, but older installs still serve `external-secrets.io/v1beta1`, and the two are not interchangeable — a manifest written for one gives `no matches for kind` on the other. Verify rather than guessing:

```sh
helm show crds <chart> | grep -A2 'external-secrets.io'
kubectl explain externalsecret | head
```

### 12.4 Common mistakes

| Mistake | Consequence |
|---|---|
| Committing a rendered `Secret` for convenience | Secret in Git history forever, even after "removal" |
| A static Vault token in `SecretStore` | Manual rotation, wide blast radius |
| `creationPolicy: Merge` by default | Orphaned secrets accumulate |
| Forgetting `refreshInterval` | Silent staleness |
| Secrets as env vars | Visible in `/proc` and in crash dumps; prefer mounted files |

---

## 13. Observability

### 13.1 The stack

| Signal | Tool |
|---|---|
| Metrics | Prometheus + kube-prometheus-stack (`ServiceMonitor` / `PodMonitor`) |
| Dashboards | Grafana |
| Alerting | Alertmanager, routed to the incident channel |
| Logs | Direct to an aggregator (Loki, or O Collector → your SIEM) |
| Traces | OpenTelemetry Collector + Tempo/Jaeger |
| Cluster state | kube-state-metrics, node-exporter |
| UI | Headlamp (or `kubectl` / `k9s`) |

Install the metrics stack with `ServiceMonitor`/`PodMonitor` objects rather than scrape annotations so discovery is declarative and survives chart upgrades.

### 13.2 Signals worth alerting on

Not a full list — the highest-value ones for a small team:

| Alert | Catches |
|---|---|
| Pods `CrashLoopBackOff` > N minutes | Broken deploys |
| `OOMKilled` count rising | Requests too low, or a leak |
| Pods `Pending` > 10 min | Capacity exhaustion, bad affinity, unbound PVC |
| Deployment `AvailableReplicas` < desired | A rollout that will not converge |
| Node `NotReady` | Hardware or network failure |
| Certificate expiry < 14 days | The outage you can prevent |
| etcd backup age > 24 h | The outage you cannot |
| GitOps resource `OutOfSync` or `Suspended` | Drift — the cluster is not what Git says |
| HPA at `maxReplicas` | Ceiling reached; you need more capacity |
| Pending PVCs | Storage exhaustion |

The last three are the ones most teams do not have, and they are the ones that catch problems before users do.

### 13.3 Logs

Ship stdout/stderr to a central aggregator. Do not write application logs to `emptyDir` — they die with the pod. If you must buffer locally, a small PVC with a rotation policy beats losing logs, but shipping is better.

### 13.4 UI

Headlamp is a good default: web UI, read-only mode, RBAC-aware, no cluster-admin needed to give someone visibility. `k9s` and `stern` are better for terminal work. Reach for a full admin UI (e.g. a dashboard chart) only with a real reason — they are large attack surfaces.

---

## 14. Upgrades and version skew

### 14.1 The rules

From the Kubernetes version skew policy:

- The project maintains the most recent **three** minor releases; 1.19+ get roughly one year of patch support.
- In HA clusters, the newest and oldest `kube-apiserver` must be within **one** minor.
- **`kubelet` must not be newer than `kube-apiserver`** and may be up to **three** minors older.
- **`kube-proxy` must not be newer than `kube-apiserver`** and may be up to **three** minors older.
- **`kube-controller-manager`, `kube-scheduler`, `cloud-controller-manager`** must not be newer than the API server and may be up to **one** minor older.
- **`kubectl` is supported within one minor**, older or newer.
- **Minor versions cannot be skipped.** Upgrading requires one step per minor, in order.
- **In-place minor `kubelet` upgrades are not supported** — drain the node first.
- A `kubelet` persistently three minors behind **blocks** control-plane upgrades.

### 14.2 Upgrade order

1. `kube-apiserver`
2. `kube-controller-manager`, `kube-scheduler`, `cloud-controller-manager` (any order among themselves)
3. `kubelet` (drain first)
4. `kube-proxy` (drain first, or let the kubelet restart it)

Before starting: get everything onto the newest patch of the current minor, then onto the newest patch of the target minor.

Admission webhooks are a common upgrade blocker. Validate that `ValidatingWebhookConfiguration` and `MutatingWebhookConfiguration` objects can handle the new API version's resources, or use `matchPolicy: Equivalent`.

### 14.3 Planning a large version jump

If you are several minors behind, the jump is a **project**, not a patch. `kubeadm upgrade plan` is strict about single-minor steps.

Rough shape:

```
1. Baseline: newest patch of the current minor on every component. Verify healthy.
2. For each minor in between:
   a. Control plane (apiserver, then controller-manager/scheduler).
   b. Nodes: drain → upgrade kubelet/kube-proxy → uncordon → verify.
   c. Verify workloads, then proceed. Do not batch.
3. Land on the newest patch of a supported minor.
4. Re-establish automation (do not do this by hand again).
```

Total cost scales with the number of minors times the number of nodes times your confidence that each step was healthy. This is the strongest argument for staying within the three-minor support window: each unit of drift adds a full cycle to every upgrade and shrinks your security patch coverage to zero.

### 14.4 Practical concerns

- **Package pinning conflicts with security.** `apt-mark hold kubelet` prevents surprise upgrades, which is good, and also means nothing upgrades it for you. Either automate the upgrade path or schedule it explicitly.
- **CNI and CSI compatibility** is checked before every minor bump, not during.
- **Deprecations**: check what your version removes before you upgrade, not after (`kubent`, `pluto`).
- **Back up etcd** before every minor upgrade. This is the one step that makes the rest recoverable.
- **Automate it.** Manual upgrade procedures are procedures that get skipped.

---

## 15. Service playbooks

Each entry: what it is for, minimum viable configuration, and what to watch. Cross-link the skills that own the details.

### 15.1 Airflow

Read [[airflow]] for Airflow itself, and the repo-local `airflow-dag` skill (§15 preamble) for DAG patterns in a repo that versions them next to their code.

The official Helm chart (`apache-airflow/airflow`) is the only sane way to run Airflow on Kubernetes. Current documented requirements: Kubernetes **1.30+**, Helm **3.19+**. All executors are supported, including `KubernetesExecutor`.

| Executor | Shape | Use when |
|---|---|---|
| `LocalExecutor` | Subprocesses on one pod | Small, non-distributed, simplest |
| `CeleryExecutor` | Worker pods consuming a broker | The usual production choice; pairs with KEDA |
| `KubernetesExecutor` | One pod per task | Maximum isolation, slow and noisy at high concurrency |

Key configuration decisions:

- **`workers.kubernetes.safeToEvict` defaults to `false`.** This is the single most important Airflow-on-Kubernetes setting and the most commonly missed. With it false, Airflow pods are never evicted during a node drain — which protects long-running tasks, and also means a draining node cannot free capacity. Understand the trade-off rather than inheriting the default.
- **Keep the metadata database outside the cluster**, next to your other "pets". This is the one piece of Airflow state you cannot regenerate, and it is what chart CRDs are for — not a database.
- **`git-sync` or an image-baked DAGs directory.** git-sync gives fast DAG iteration without rebuilding the image; it needs a read-only repo token and a sidecar that can fail. Baking is slower to iterate but reproducible. Pick one and be consistent.
- **`pod_mutation_hook`** for injecting per-pod settings (labels, sidecars, tolerations) without patching pod templates.
- **`pod templates`** for anything the chart's default pod does not cover — init containers, sidecars, specific volumes.
- **PgBouncer** in front of an external Postgres; Airflow opens a lot of short-lived connections.
- Airflow 3's **task execution API** allows decoupling task execution from the core scheduler; evaluate it if you are starting fresh on 3.x.
- Airflow 3.1 added a built-in event-driven scheduling mode, which may change the DAG-driven assumptions in older designs.

### 15.2 Spark and batch data workloads

For a data platform, Spark is the workload that justifies the cluster. Two ways to run it, and the choice determines everything else:

| Approach | What it is | Use when |
|---|---|---|
| `spark-submit --master k8s://...` | Spark's built-in Kubernetes scheduler; the client creates driver and executor pods directly | Ad-hoc jobs, notebooks, a team that already thinks in `spark-submit` |
| **spark-operator** (`SparkApplication` CRD) | A controller owns the lifecycle; you submit a CRD and the operator manages driver/executor pods, retries, and cleanup | Anything scheduled, GitOps-managed, or shared. The default for a platform |

With the operator, a job is a manifest and therefore reconcilable like everything else:

```yaml
apiVersion: sparkoperator.k8s.io/v1beta2
kind: SparkApplication
metadata:
  name: ingest-nanopore
  namespace: data-jobs
spec:
  type: Python
  mode: cluster
  image: registry.example.org/platform/spark-jobs:1.4.2
  mainApplicationFile: local:///opt/app/ingest.py
  sparkVersion: "4.0.4"          # must match the Spark version baked into the image
  driver:
    cores: 1
    memory: 2g
    serviceAccount: spark
  executor:
    cores: 2
    instances: 4
    memory: 8g
  dynamicAllocation:
    enabled: true
    minExecutors: 1
    maxExecutors: 20
  restartPolicy:
    type: OnFailure
    onFailureRetries: 3
```

The concerns that actually bite, in rough order of how often they cause incidents:

- **Shuffle storage is the classic failure.** Spark writes shuffle and spill data to `spark.local.dir`, which on Kubernetes defaults to an `emptyDir` backed by node disk. A large shuffle fills the node and evicts every pod on it. Set an explicit `emptyDir.sizeLimit` and a dedicated shuffle directory, or run a shuffle service, and size executors so a single job cannot fill a node. This is the single most common cause of "the whole cluster died because of one Spark job".
- **Dynamic allocation is not optional for shared clusters.** Without it, every job reserves its maximum executors forever. Enable it so executors scale down when a stage finishes, and set `maxExecutors` so one job cannot consume the pool.
- **Data stays in object storage and ClickHouse** (§1). A Spark job moves *processing* into the cluster; it reads Parquet from S3 and writes results back. Do not mount a PVC for the dataset, and do not treat executor-local disk as durable.
- **Requests must be set on the driver and every executor.** Unsized Spark pods are the fastest way to make the scheduler guess wrong and leave the cluster unbalanced.
- **Give the driver and executors a dedicated `ServiceAccount`** with only the RBAC they need to create and watch their own pods — not `cluster-admin` (see §11.5).
- **Version compatibility matters.** Spark supports a bounded range of Kubernetes versions; check the Spark release notes against your cluster before pinning. A Spark too old for the cluster's API removals will fail at driver startup, not at submit.
- **Build a job image with the dependencies baked in.** Fetching Python packages at runtime per executor is slow and non-reproducible. Pin the image digest and promote it like any other artifact.
- **Executor `podTemplate`** is how you inject the things the operator does not expose: tolerations, node selectors for a job pool, sidecars, and the shuffle volume configuration above.

Scheduling and quota:

- **Kueue** is the right tool once more than one team submits Spark jobs. It gives gang scheduling (all executors start together, or none do), per-team quotas, and fair sharing, so a large job queues instead of starving everyone or failing halfway through. See §10.7.
- Without a queue, a single unbounded `SparkApplication` with high `maxExecutors` will consume the pool and every other job will sit `Pending`.

Airflow to Spark: Airflow's `SparkKubernetesOperator` submits a `SparkApplication` and defers on its status, which keeps Airflow as the orchestrator and Spark as the compute. That is the standard shape for a data platform — Airflow owns scheduling and dependencies, the cluster owns execution. Read [[airflow]] for the operator, and see §15.1 for Airflow itself.

**When Databricks is the better answer.** A self-managed Spark on Kubernetes is worth it when you need control over the runtime, the data cannot leave your infrastructure, or you are consolidating on one platform. Databricks remains the better answer when you want a managed runtime, Delta Lake features, and serverless autoscaling without operating Spark yourself. Our pipelines currently run on Databricks; read [[biocloud-databricks]] before proposing a move in either direction, and the repo-local `biocloud-kubernetes` skill for the current cluster state.

### 15.3 Databases and stateful services

Default answer: **outside the cluster**. If you must run one in-cluster, use the operator and accept the operational cost:

| Service | In-cluster option | Recommendation |
|---|---|---|
| PostgreSQL | CloudNativePG | Reasonable; test restores. Otherwise a VM |
| ClickHouse | ClickHouse operator | Keep it on a VM where you control backups |
| Kafka | Strimzi | Operator is mature |
| RabbitMQ | Cluster operator | Fine for internal queues |
| Redis | Cluster operator | Fine as a cache, not as a system of record |
| Object storage | — | Use the real thing (S3-compatible), not MinIO in-cluster |

### 15.4 Platform components

| Component | Chart / source | Notes |
|---|---|---|
| Gateway | **Cilium's if you run Cilium, else Envoy Gateway** | One per cluster; the thing everything else publishes through. See §8.8 for the conformance comparison and the Traefik caveat |
| cert-manager | `jetstack/cert-manager` | Install early; TLS is a dependency of nearly everything else |
| metrics-server | `metrics-server` | **Prerequisite for HPA, VPA, and `kubectl top`** |
| OpenStack CCM | `cloud-provider-openstack` | **Required on OpenStack** — LoadBalancer Services and the node taint (§3) |
| Cinder CSI | `cloud-provider-openstack` | **Required on OpenStack** for any PVC (§9.2) |
| MetalLB | `metallb/metallb` | Only when Octavia is unavailable; needs `allowed_address_pairs` (§3) |
| ExternalDNS | `external-dns/external-dns` | Only if you have many entry points; a static wildcard record is often better (§8.6) |
| Cilium | `cilium/cilium` | Required for NetworkPolicy if the CNI is not policy-capable |
| External Secrets | `external-secrets/external-secrets` | For Vault |
| KEDA | `kedacore/keda` | For event-driven scaling |
| Kueue | `kubernetes-sigs/kueue` | Queue, gang scheduling, and quota for batch jobs (§10.7) |
| Spark operator | `kubeflow/spark-operator` | `SparkApplication` CRD for batch Spark jobs (§15.2) |
| GitOps | `argo/argo-cd` ([[argocd]]) | One per cluster; install it first and let it manage itself |
| Monitoring | `prometheus-community/kube-prometheus-stack` | Includes Grafana, Alertmanager, node-exporter, kube-state-metrics |
| UI | `headlamp-k8s/headlamp` | Read-only access for humans |
| Policy | `kyverno/kyverno` | Admission validation |
| Scanning | `aqua-sec/trivy-operator` | Continuous image scanning |

### 15.5 Other workloads

| Service | Use |
|---|---|
| n8n | Workflow automation; SQLite by default — point it at Postgres |
| Grafana | Dashboards; the kube-prometheus-stack already ships one |
| GitLab Runner | `runner-helm` chart for in-cluster ephemeral runners; **never run Docker-in-Docker on workload nodes** — use rootless or a dedicated runner node group |
| Argo Workflows | Kubernetes-native DAGs for batch pipelines |
| Tekton | CI/CD primitives if you want pipelines in-cluster |
| Kafka UI / Schema Registry | Operability for streaming workloads |

### 15.6 Promoting a service from local to cluster

1. Write it to run as a non-root user with a read-only root filesystem, from local dev onward — retrofitting `securityContext` is tedious.
2. Run it under `kind` or `k3d` with the same manifests CI uses.
3. Deploy to `development` via the agent, in the same commit as the manifests.
4. Add probes, requests, limits, PDB, and a `NetworkPolicy` before it carries real load.
5. Promote by changing the overlay, not by editing the cluster.

---

## 16. Local development and CI gates

### 16.1 Local clusters

| Tool | Notes |
|---|---|
| `kind` | Nodes are containers; fast; the default for CI |
| `k3d` | k3s in containers, with an integrated local registry and volume mapping |
| `minikube` | Most forgiving for beginners, supports multiple node types |
| Docker Desktop | Kubernetes is built in; fine for very small experiments |

Aim to use the same manifests CI validates. A local cluster that diverges from the manifests hides bugs rather than surfacing them.

Useful one-liners:

```sh
kubectl apply -k clusters/development
kubectl port-forward -n my-app svc/my-app 8080:80
kubectl logs -f -l app.kubernetes.io/name=my-app -n my-app --tail=100
kubectl get events -n my-app --sort-by=.lastTimestamp | tail -20
k9s -A
```

### 16.2 CI gates

Minimum for a merge request:

```sh
kustomize build clusters/development | kubeconform -strict -summary -ignore-missing-schemas -
kustomize build clusters/production  | kube-score score output=stdout
helm lint <chart> && helm template <chart> | kubeconform -strict -
gitleaks detect --no-git --source .
```

Add `kubectl apply --dry-run=server` when you have a long-lived CI cluster — it is the only gate that catches admission-time problems, including PSA violations and webhook rejections.

If you deploy from GitLab, put these in the `check` stage ahead of `diff`, and reuse the same rendered output for both so the review shows exactly what will be applied. See [[gitlab-cicd]].

### 16.3 Dependency updates

One Renovate or Dependabot configuration covering all of it, in one repo:

| Type | Renovate manager |
|---|---|
| Helm chart versions | `helm-values`, `helmv3` |
| Kustomize image tags | `kustomize` |
| Kubernetes version in CI images | `regex` |
| GitHub Actions / CI images | `github-actions`, `dockerfile` |

Chart bumps are the ones that break things. Have Renovate open them, and gate merges on the CI gates above.

---

## 17. Troubleshooting

Start here:

```sh
kubectl describe pod <pod>            # Events explain most failures
kubectl get events -n <ns> --sort-by=.lastTimestamp
kubectl logs <pod> --previous         # the crashed container, if it restarted
kubectl get pod -o wide
kubectl debug -it <pod> --image=busybox --target=<container>   # ephemeral container in a running pod
kubectl debug node/<node> -it --image=busybox                  # node's namespaces, no SSH
```

| Symptom | Likely cause | Fix |
|---|---|---|
| `CrashLoopBackOff` | App crashes at startup | `logs --previous`; check config, env, and that the port in the probe matches the app |
| `ImagePullBackOff` / `ErrImagePull` | Bad tag, or no `imagePullSecrets` for a private registry | Verify the tag exists; add `imagePullSecrets`; check registry rate limits |
| `OOMKilled` | Memory limit too low, or a leak | Raise the limit; check `metrics-server` history for a rising curve before the kill |
| `Pending` — `Insufficient cpu/memory` | No room | Scale nodes; check requests are not absurd |
| `Pending` — untainted / node selector / affinity | Scheduling constraints | Review taints, `nodeSelector`, `affinity`, `topologySpreadConstraints` |
| `Pending` — PVC unbound | No PV matching the request | Check StorageClass exists, `WaitForFirstConsumer` is set, and capacity is available |
| Pod ready but no traffic | Not matching Service selector | Compare `spec.selector` with pod labels — the single most common cause |
| Service returns 503 | No ready endpoints | Check readiness probe, not liveness |
| Restarts on a rolling deploy | Liveness too aggressive | Add a `startupProbe` and relax liveness |
| Draining hangs | PDB blocking, or a pod ignoring SIGTERM | Check PDBs (`kubectl get pdb`); confirm `terminationGracePeriodSeconds` and preStop hooks |
| Pods stuck `Terminating` | Finalizer, or unmountable volume | Inspect finalizers; check the volume backend |
| Node `NotReady` | Kubelet down, CNI down, or disk pressure | Check kubelet, `kubectl describe node` for the condition reason |
| DNS failures in a namespace | A `NetworkPolicy` without a DNS egress rule | Add the allow-dns policy (§8.4) |
| NetworkPolicy "not enforced" | CNI has no policy engine | Check the CNI — flannel ignores policies entirely |
| TLS errors at ingress | Certificate not issued, or secret in another namespace | Check cert-manager `Certificate` status and the `certificateRefs` namespace |
| CronJob ran at the wrong time | Controller timezone | Set `spec.timeZone` |
| HPA does nothing | No metrics-server, or target not a resource metric | Install metrics-server; confirm `kubectl top` works |
| VPA and HPA fight | Both own the same resource | Configure HPA ownership or separate the concerns |
| GitOps `OutOfSync` / `Suspended` | Drift, a failed hook, or a missing CRD | Read the controller message; `flux reconcile --with-source`; check CRDs exist |
| Agent job cannot reach the cluster | Wrong context, expired token, or no environment protection | `kubectl config get-contexts`; check the agent is running and its token is current |
| Flux "no matches for kind" | Flux pointed at a directory containing agent config, or CRDs missing | Point Flux at a real `path`; verify ordering (§2.3) |

Three general habits that pay off:

- **Read the Events before theorising.** Kubernetes reports most failures in `kubectl describe` output, and it is almost always more specific than the status message you saw first.
- **Debug in place with ephemeral containers, not SSH.** `kubectl debug --target` attaches a debug container to a running pod sharing its process namespace, so you can inspect the filesystem and processes of a distroless container that has no shell. `kubectl debug node/<node>` gives you the node's namespaces without SSH — the right way to debug a node on a cluster where SSH is not the access model. Both leave no permanent change to the workload.
- **Reproduce outside the cluster.** `kubectl run` with the same image, env and command turns a mysterious scheduling or crash problem into a local one in about a minute.

---

## 18. Naming and labelling

### 18.1 Names

- DNS-label-safe: lowercase alphanumeric and `-`, no underscores, no dots in most resource names.
- `{application}-{component}` for resources; `{application}-{component}-{replicaset-hash}` happens automatically for Deployments.
- Keep names stable across environments. `namePrefix`-style per-environment prefixes are an option but they break cross-environment tooling and log queries — prefer identical names in different clusters.
- Do not put the environment or the version in the resource name. Use labels for both.

### 18.2 The recommended labels

```yaml
app.kubernetes.io/name: my-app          # application name
app.kubernetes.io/instance: my-app      # unique instance within the cluster
app.kubernetes.io/component: server     # role within the app
app.kubernetes.io/part-of: data-platform  # higher-level system
app.kubernetes.io/version: "1.4.2"      # app version
app.kubernetes.io/managed-by: argocd    # the tool that owns it
```

These are the labels selectors, dashboards, and cost tooling look for. Skipping `app.kubernetes.io/name` and `managed-by` is the reason ad-hoc queries get built.

Also useful:

| Label | Purpose |
|---|---|
| `argocd.argoproj.io/sync-wave` | Argo CD ordering |
| `app.kubernetes.io/component` | Drives `kubectl rollout restart` targeting and cost attribution |
| A custom environment label | Many tools filter on this; keep it consistent |

Prefer **annotations** for non-identifying operational metadata (config hash, change reason, owner contact) and **labels** for anything you select on.

### 18.3 Environments

Use a small fixed set of tiers, named identically across the whole stack — clouds, buckets, GitLab environments, Kubernetes namespaces, and IaC states. Mismatched tier names cause more confusion than any technical decision here.

---

## 19. Anti-patterns

| Anti-pattern | Why it hurts |
|---|---|
| Running a database in the cluster | The fastest route to an unrecoverable outage (§1) |
| `hostPath` for persistent data | Node-bound; the node is disposable |
| `hostNetwork` on application pods | Defeats NetworkPolicy and port management |
| No resource requests | The scheduler guesses; the cluster cannot be tuned |
| Memory limit unset | One leak OOM-kills the node |
| CPU limit equal to request | Throttling under burst; wasted cost |
| `:latest` or untagged images | Silent breaking changes; unrollbackable rollouts |
| `kubectl apply` from a laptop to production | Invisible, unaudited, drifting |
| Editing live objects | Reverted by the next sync, and the incident is now undebuggable |
| Mixing GitOps and imperative changes | Guaranteed drift |
| `latest` remote base / `targetRevision: HEAD` | Manifests change meaning overnight |
| HPA without metrics-server | Silently does nothing |
| One replica, no PDB | Any drain is an outage |
| PDB whose selector matches nothing | Blocks every drain forever |
| `NetworkPolicy` without a DNS egress rule | Breaks DNS for the whole namespace |
| CNI without a policy engine | NetworkPolicy is a silent no-op |
| Secrets in Git "encrypted with a key nearby" | Key management becomes the real system |
| A static Vault token in a `SecretStore` | Manual rotation; wide blast radius |
| `cluster-admin` for a workload or CI job | One compromise is total compromise |
| Binding `default` ServiceAccount | Shared identity; unmounted tokens everywhere |
| Wildcard RBAC (`resources: ["*"]`) | Equivalent to cluster-admin |
| Wildcard image registry without `imagePullPolicy` | Latest digest on every restart |
| Probes pointing at the wrong port/path | Restarts under load, or readiness that never passes |
| `latest` on ingress/cert-manager/CNI | The cluster's own foundation is unpinned |
| Adding a cluster add-on by hand | Not in Git, gone after a rebuild |
| Skipping minor versions during upgrade | Not supported; will break |
| `kubeadm init` without `--control-plane-endpoint` | Converting to HA later means re-issuing certs and re-joining every node (§3) |
| A two-node control plane | Breaks etcd quorum on any single failure — *less* available than one node (§3) |
| Two Gateway controllers in one cluster | Two failure domains and two CRD sets for one job (§8.8) |
| No etcd backup | One disk failure is total loss |
| Spark shuffle on an unbounded `emptyDir` | One large shuffle fills the node and evicts every pod on it (§15.2) |
| No quota or queue on a shared batch pool | One job consumes the cluster; everything else starves (§10.7) |
| Logging to `emptyDir` | Logs die with the pod |
| Trusting a PR-triggered job on production | Needs `protected_branches_only` or environment protection |
| Binding CI to `cluster-admin` for convenience | Same as no access control |

---

## 20. Version reference

Verified against upstream release metadata. **Re-check before pinning** — these move roughly every two to three months, and the pinned version in your repo is the real source of truth.

| Component | Latest verified | Notes |
|---|---|---|
| Kubernetes | **v1.37.1** | Support window: 1.37, 1.36, 1.35 |
| k3s | v1.37.1+k3s1 | Tracks Kubernetes minors |
| Gateway API | v1.6.3 | Check the CRD versions your controller chart serves; conformance reports are per API version (§8.8) |
| Envoy Gateway | v1.9.2 | Most complete Gateway API conformance (§8.8) |
| Traefik | v3.7.14 | Gateway API needs **v3**; `GATEWAY-HTTP` core is `partial` — no timeouts/retries/CORS/mirroring via Gateway API (§8.8) |
| cert-manager | v1.21.2 | |
| External Secrets Operator | v2.12.0 (chart 2.12.0) | Check served CRD `apiVersion` before writing manifests. Set `audiences` — required from Vault 1.21 (§12) |
| Argo CD | **v3.5.4** | Fixes 4 CRITICAL advisories; do not run older 3.5.x. See [[argocd]] §16.1 |
| Argo Workflows | v4.1.4 | |
| Cilium | v1.20.2 | |
| MetalLB | chart 0.16.1 | L2 mode needs OpenStack `allowed_address_pairs` (§3) |
| ExternalDNS | v0.23.0 | OpenStack Designate is a **webhook** provider, not in-tree (§8.6) |
| Flux | v2.9.6 | CRD apiVersions: `helm.toolkit.fluxcd.io/v2`, `source.toolkit.fluxcd.io/v1`, `kustomize.toolkit.fluxcd.io/v1` |
| KEDA | v2.21.0 | |
| Kueue | v0.20.0 | API `kueue.x-k8s.io/v1beta2`; requires Kubernetes 1.29+ |
| Spark operator (Kubeflow) | v2.5.2 | API `sparkoperator.k8s.io/v1beta2`; base Spark 4.0.x, supports Spark 2.3+ |
| Apache Spark | v4.0.x | Check the Spark/Kubernetes compatibility matrix before pinning |
| Helm | v4.3.0 | Charts must be `apiVersion: v2`; Helmfile supports Helm 3 and 4 |
| Airflow chart | see [[airflow]] | Requires Kubernetes 1.30+, Helm 3.19+ |

### Migration readiness

Design for the day the control plane is someone else's problem:

| Do now | So you can move later |
|---|---|
| No `hostPath`, no `hostNetwork` | No node-level coupling |
| Portable `StorageClass` names, no driver-specific parameters inline | Works on whatever CSI the provider supports |
| No node labels in selectors | Works without node access |
| No cluster-scoped resources beyond what a GitOps controller needs | No cluster-admin dependency |
| ESO + an external secret store | No secrets in cluster state |
| GitOps only, one entrypoint per cluster | Reconcile works unchanged on a new cluster |
| GitLab agent | Same access path on any control plane |
| Manifests in one repository | The provider's platform can be a *different* path, not a fork |

The point of that table: the migration should be a change of cluster, not a rewrite of how you deploy.
