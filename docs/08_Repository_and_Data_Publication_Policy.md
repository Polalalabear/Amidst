# Repository and Data Publication Policy

Document status: `CONFIRMED`

## Purpose and Authority

Amidst is intended to be open source while research continues with private
assets. The public GitHub repository contains the reproducible project, but it
must not become storage for raw surveillance data, sensitive physical-site
information, secrets, or large internal research artifacts.

This document is the single source of truth for classifying files before they
are added to Git or intentionally published. A file is not safe merely because
it already exists inside the working directory.

## Required Classifications

| Classification | Meaning | Required action |
| --- | --- | --- |
| `PUBLIC_ALLOWED` | Generally suitable for the public repository after normal content checks | May be added when the applicable checks pass |
| `PRIVATE_ONLY` | Must remain outside the public repository | Do not add or publish; use approved private storage |
| `REVIEW_REQUIRED` | Safety depends on content, rights, sensitivity, or intent | Do not add or publish until a human explicitly approves it |

When uncertain, use `REVIEW_REQUIRED`.

Classification is semantic: extensions and directory names are signals, not
proof that an artifact is safe.

## `PUBLIC_ALLOWED`

### Source Code

Source and test directories such as `src/`, `scripts/`, `tests/`, and `tools/`
are generally public when they contain no embedded credentials, private
infrastructure details, private data, or sensitive records.

Potentially allowed examples:

- Python, TypeScript, JavaScript, frontend, and backend source;
- evaluation, inference, and data-processing code;
- tests and utility scripts.

### Documentation

Documentation may be public when it describes architecture, evaluation
methodology, dataset/annotation formats, APIs, schemas, algorithms, decisions,
workflow, or reproducibility without exposing:

- credentials or private URLs;
- internal infrastructure;
- identifiable surveillance information or personal data;
- sensitive real-site layouts or security details;
- private Google Drive links.

### Schemas

Schema files may be public when they describe structure rather than contain real
sensitive records. Examples include camera, zone, event, retrieval, and
annotation JSON schemas.

### Configuration Templates

Example configurations such as `.env.example`, `config.example.yaml`, or
`docker-compose.example.yml` may contain placeholders only. Never copy a real
secret or private connection string into a template.

### Sanitized Sample Data

Small data under `examples/`, `sample_data/`, `fixtures/`, or `tests/fixtures/`
may be public only when it is synthetic, anonymized, sanitized, or intentionally
created for public demonstration. It should be limited to what tests,
documentation, demonstrations, or reproducibility checks need.

### Public Evaluation Results

Small aggregate metrics, benchmark summaries, plots, and error-category
summaries may be public after sanitization. Raw evidence containing sensitive
surveillance information remains private.

## `PRIVATE_ONLY`

### Raw Surveillance Media

Actual surveillance or real-site recordings, including typical `*.mp4`,
`*.mov`, `*.avi`, and `*.mkv` files, must remain in approved private team
storage. Synthetic or explicitly sanitized demonstration video is still
`REVIEW_REQUIRED` before publication.

### Real Surveillance Images

Real frames or photographs containing identifiable people, private areas,
sensitive environmental details, or operational information are private.
Directories such as `frames/`, `captures/`, `snapshots/`, and `raw_images/` do
not make their contents safe.

### Full Ground Truth Datasets

Full `dataset/raw/`, `dataset/annotations/`, train, validation, and test data are
private by default, especially when they contain real people, tracks,
timestamps, camera IDs, real locations, or surveillance events.

The public repository may document the expected private layout without
containing it. Only small sanitized samples may be considered for public
examples, and they require review.

### Sensitive Spatial Assets

Real-site Blender files, floor plans, detailed layouts, security-camera
placements, restricted-area definitions, coverage maps, internal access routes,
and security infrastructure are private by default. Simplified or synthetic
Digital Twin assets are `REVIEW_REQUIRED` before publication.

Raw `*.blend` and `*.blend1` working assets are private by default, particularly
when large, frequently modified, tied to a real site, or internally annotated.
Sanitized `*.glb` or `*.gltf` exports require review.

### Model Checkpoints and Weights

Files such as `*.pt`, `*.pth`, `*.ckpt`, `*.onnx`, and `*.weights` are not added
automatically. Treat them as `REVIEW_REQUIRED` and keep them private or in an
approved artifact registry unless publication is intentional and human review
confirms licensing, redistribution rights, training-data constraints,
sensitivity, and reasonable size.

### Raw Experiment Outputs

Raw content under `experiments/`, `runs/`, `outputs/`, `predictions/`, `logs/`,
or `artifacts/` is private by default. This includes frame-level predictions,
debug images, intermediate tensors, large logs, generated media, and complete
experiment artifacts. Only small sanitized aggregate summaries may be public.

### Secrets

Never commit `.env`, `*.pem`, `*.key`, `credentials.json`, `secrets.json`, or
any content containing API keys, tokens, passwords, SSH keys, cloud/database
credentials, camera passwords, authentication cookies, or private connection
strings. Use environment variables or an approved secret-management system.

### Private Infrastructure

Do not publish security-relevant private IP addresses, camera authentication
endpoints, internal database/server addresses, VPN information, private cloud
resource identifiers, or internal network topology. Use placeholders in public
examples.

## `REVIEW_REQUIRED`

Human review is required before adding a non-source artifact whose safety
depends on its content. Common examples include:

```text
*.glb  *.gltf  *.obj  *.fbx
*.pt   *.pth   *.onnx
*.csv  *.json  *.jsonl
*.jpg  *.jpeg  *.png
*.pdf
```

These extensions are not inherently private. For example, an architecture
diagram or schema can be public, while a camera view or real event export is
private. Always classify semantic content, not just the extension.

## File Decision Process

Before adding a new non-source artifact to Git, apply this order:

```text
Does it contain secrets?
  Yes -> NEVER COMMIT
  No  -> Does it contain real surveillance, person, or site data?
          Yes -> PRIVATE_ONLY
          No  -> Does it expose sensitive spatial/security information?
                  Yes -> PRIVATE_ONLY
                  No  -> Is it a raw dataset, experiment, or model artifact?
                          Yes -> PRIVATE_ONLY or REVIEW_REQUIRED
                          No  -> Is it code, documentation, a schema,
                                 or a reviewed sanitized sample?
                                  Yes -> PUBLIC_ALLOWED
                                  No  -> REVIEW_REQUIRED
```

If classification is uncertain, do not add the file and request human
confirmation.

## `.gitignore` Policy Template

Inspect an existing `.gitignore` before editing it and never replace it blindly.
Prefer directory-based rules and narrowly scoped patterns. Candidate rules for
human review include:

```gitignore
# Secrets
.env
.env.*
!.env.example

# Private datasets
data/raw/
data/private/
dataset/raw/
dataset/private/

# Surveillance media
*.mp4
*.mov
*.avi
*.mkv

# Private environment assets
environment/private/
*.blend
*.blend1

# Model artifacts
models/
checkpoints/
*.pt
*.pth
*.ckpt

# Experiment artifacts
runs/
outputs/
artifacts/

# Local/private configuration
config/local.*
config/private.*
```

Do not add broad ignores such as `*.json`, `*.png`, or `*.glb`; legitimate
public schemas, diagrams, and reviewed demo assets may use those formats.
This template does not itself authorize creating or changing `.gitignore`.

## Public Placeholder Structure

The repository should document private-data interfaces without containing the
private data. A candidate public structure is:

```text
data/
├── README.md
└── examples/
    ├── sample_event.json
    ├── sample_zone.json
    └── sample_annotation.json
```

The README may describe a local private structure such as `data/raw/`,
`data/annotations/`, `data/benchmarks/`, and `data/environment/`, but it must not
contain private storage or Google Drive URLs.

## Local Development Model

`PROPOSED` directory convention for future human review:

```text
amidst/
├── src/                  # public repository
├── docs/                 # public repository
├── tests/                # public repository
├── schemas/              # public repository
├── examples/             # reviewed public samples
├── data/private/         # ignored / private storage
├── models/private/       # ignored / private storage
├── experiments/private/  # ignored / private storage
└── environment/private/  # ignored / private storage
```

Application code must use documented paths and configuration rather than
hard-coded private or Google Drive paths.

## Publication Review Checklist

Before intentionally publishing any data, media, model artifact, experiment
artifact, or spatial information, verify:

- [ ] No secrets or credentials are present.
- [ ] No private infrastructure information is present.
- [ ] No unintended personal or identifiable information is present.
- [ ] No sensitive real-site information is present.
- [ ] Dataset publication is intentional.
- [ ] Licensing permits publication.
- [ ] Model redistribution is permitted where applicable.
- [ ] File size is reasonable for Git.
- [ ] Sanitization has been reviewed.
- [ ] The public repository remains reproducible without private assets.

If any item cannot be verified, classify the artifact as `REVIEW_REQUIRED` and
do not publish it automatically.

## Review Record Template

| Artifact | Classification | Reason | Reviewer | Review date | Approved action |
| --- | --- | --- | --- | --- | --- |
| TODO | REVIEW_REQUIRED | TODO | TODO | TODO | TODO |

## Policy Acceptance Checks

- [ ] Every staged non-source artifact has an explicit classification.
- [ ] No `PRIVATE_ONLY` artifact is staged or tracked.
- [ ] Every `REVIEW_REQUIRED` artifact has recorded human approval before publication.
- [ ] Example configs contain placeholders only.
- [ ] Samples and reports have documented sanitization and rights review.
- [ ] Private data locations are described without publishing private URLs.
