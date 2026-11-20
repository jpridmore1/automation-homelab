# Automation Home Lab
[![ansible-lint](https://github.com/jpridmore1/automation-homelab/actions/workflows/ansible-lint.yml/badge.svg)](https://github.com/jpridmore1/automation-homelab/actions/workflows/ansible-lint.yml)


A hands-on lab for learning infrastructure automation, containers, and CI/CD — built on Fedora with Ansible and Podman, with an eye toward OT/industrial environments.

## What it does

A single Ansible playbook that:

1. Installs Podman
2. Pulls the official nginx image
3. Runs nginx as a **rootless** container managed by systemd via Podman Quadlet (starts at boot, restarts on failure)
4. Verifies the service responds with HTTP 200

The playbook is **idempotent** — running it again makes no changes if the system is already in the desired state.

## Repo layout

```
.
├── ansible.cfg              # Points Ansible at the local inventory
├── inventory/hosts.ini      # Target hosts (currently localhost)
├── playbooks/
│   └── podman-nginx.yml     # Install Podman + deploy nginx
└── files/web/index.html     # Content served by nginx
```

## Requirements

- Fedora (tested on Fedora 44)
- Ansible
- `containers.podman` collection:
```bash
  ansible-galaxy collection install containers.podman
```

## Usage

```bash
git clone https://github.com/jpridmore1/automation-homelab.git
cd automation-homelab
ansible-playbook playbooks/podman-nginx.yml -K
curl http://localhost:8080
```

Change the host port without editing the playbook:

```bash
ansible-playbook playbooks/podman-nginx.yml -K -e nginx_host_port=8090
```

## Design notes

- **Least privilege:** only the package install uses `become`; the container runs rootless as a normal user.
- **SELinux-aware:** the content volume is mounted with `:Z` so SELinux allows the container to read it, rather than disabling SELinux.
- **Fully qualified image names** (`docker.io/library/nginx`) avoid Podman's interactive short-name prompt, which would hang automation.
- **Health check:** the final task confirms nginx actually answers, with retries.

## Roadmap

- [x] Ansible playbook: install Podman + deploy nginx
- [x] Publish to GitHub
- [x] CI: GitHub Actions running `ansible-lint`
- [x] Persist containers across reboots with Podman Quadlet (systemd)
- [ ] Local OpenShift / Kubernetes (OKD or CRC)
- [ ] OT angle: simulated PLC / Modbus service

## Background

Built while expanding from Windows/Linux administration, PowerShell automation, VMware, and OT security (Claroty, NIST) into Ansible, containers, and platform engineering.
