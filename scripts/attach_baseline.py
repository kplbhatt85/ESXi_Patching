#!/usr/bin/env python3

import ssl, sys, time
from pyVim.connect import SmartConnect, Disconnect # type: ignore
from pyVmomi import vim # type: ignore
import atexit

"""
Usage:
  python3 attach_baseline.py <vcenter> <username> <password> <cluster_name> <target_version>
"""

# Args
vcenter, user, pwd, cluster_name, target_version = sys.argv[1:6]

# Disable SSL verification (for self-signed certs)
ctx = ssl._create_unverified_context()
si = SmartConnect(host=vcenter, user=user, pwd=pwd, sslContext=ctx)
atexit.register(Disconnect, si)
content = si.RetrieveContent()

# Find cluster
container = content.viewManager.CreateContainerView(content.rootFolder, [vim.ClusterComputeResource], True)
cluster = None
for c in container.view:
    if c.name == cluster_name:
        cluster = c
        break
container.Destroy()

if not cluster:
    print(f"Error - Cluster {cluster_name} not found")
    sys.exit(1)

# Compliance Manager
comp_mgr = content.complianceManager
baselines = comp_mgr.QueryBaselines(entity=[cluster])

if not baselines:
    print("Error - No baselines found in vCenter")
    sys.exit(1)

match = None
for b in baselines:
    if target_version in b.name or target_version in getattr(b, "description", ""):
        match = b
        break

if not match:
    print(f"Error - No baseline found matching version {target_version}")
    print("Available baselines are:")
    for b in baselines:
        print(f" - {b.name} (ID={b.key})")
    sys.exit(1)

print(f"Attaching baseline '{match.name}' (ID={match.key}) to cluster '{cluster.name}'")

# Attach baseline
task = comp_mgr.AttachBaseline_Task(entity=cluster, baseline=[match])
while task.info.state in [vim.TaskInfo.State.queued, vim.TaskInfo.State.running]:
    time.sleep(2)

if task.info.state != vim.TaskInfo.State.success:
    print(f"Failed to attach baseline '{match.name}':", task.info.error)
    sys.exit(1)

print(f"Baseline '{match.name}' attached successfully")

# Run compliance check
print("Running compliance check...")
check_task = comp_mgr.CheckCompliance_Task(entity=[cluster])
while check_task.info.state in [vim.TaskInfo.State.queued, vim.TaskInfo.State.running]:
    time.sleep(2)

if check_task.info.state != vim.TaskInfo.State.success:
    print("Compliance check failed:", check_task.info.error)
    sys.exit(1)

# Get compliance results
results = comp_mgr.QueryComplianceStatus(entity=[cluster])
for r in results:
    print(f"Cluster compliance status: {r.complianceStatus}")
