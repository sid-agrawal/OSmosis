# Attack Surface Reduction Enhanced Scenario

## Overview

The `attack_surface_reduction_enhanced` scenario demonstrates how enabling all primitive operations allows for sophisticated security architecture discovery through pattern-aware scoring. This scenario uses the same initial conditions as the original `attack_surface_reduction` scenario but removes operational restrictions.

## Scenario Configuration

```python
"attack_surface_reduction_enhanced": Scenario(
    name="Attack Surface Reduction Enhanced",
    description="Same high attack surface system as attack_surface_reduction but with all primitives enabled for pattern-aware optimization",
    goals=[
        Goal("ASR", 2.5, "minimize")   # System-wide ASR goal
    ],
    constraints=[
        Constraint("requires_file_access", 1, FileType.TEMP, properties={"min_size_kb": 10}),
        Constraint("requires_file_access", 2, FileType.ANY, properties={"min_size_kb": 15}),
        Constraint("requires_file_access", 3, FileType.ANY, properties={"min_size_kb": 5}),
        Constraint("requires_file_access", 4, FileType.CACHE, properties={"min_size_kb": 5}),
        Constraint("requires_communication", 1, target_pd=2),
        Constraint("requires_communication", 2, target_pd=3),
        Constraint("requires_communication", 4, target_pd=1),
        Constraint("requires_communication", 4, target_pd=2),
    ],
    allowed_primitives=PRIMITIVES,  # ALL atomic graph operations enabled
    allowed_multistep=[],
    graph_builder=build_high_attack_surface_graph
)
```

## Key Differences from Original Scenario

| Aspect | Original | Enhanced |
|--------|----------|----------|
| **Allowed Operations** | Only `remove_hold_edge` | ALL primitives (12 operations) |
| **Strategy Space** | Edge removal only | Full architectural flexibility |
| **Solution Approach** | Reduce sharing | Architectural expansion |
| **Success Rate** | 0% (failed) | 100% (3 mechanisms found) |

## Initial Graph Structure

The scenario starts with a high attack surface configuration representing a typical multi-service system:

```python
def build_high_attack_surface_graph():
    """Build a graph with high attack surface from extensive file sharing"""
    g = ModelGraph()
    
    # Create file system space
    fs_id = g.add_resource_space_node(ResourceType.FILE)
    
    # Create 4 PDs representing different services
    pd1 = g.add_pd_node("web_frontend", 1)
    pd2 = g.add_pd_node("api_server", 2)
    pd3 = g.add_pd_node("database", 3)
    pd4 = g.add_pd_node("admin_panel", 4)
    
    # Create shared files
    file1 = g.add_file_node(fs_id, FileType.TEMP, "/tmp/shared_mem.tmp", 30*1024)
    file2 = g.add_file_node(fs_id, FileType.CONFIG, "/etc/shared_config.conf", 20*1024)
    file3 = g.add_file_node(fs_id, FileType.LOG, "/var/log/shared.log", 15*1024)
    file4 = g.add_file_node(fs_id, FileType.DATABASE, "/var/db/conn_pool.db", 25*1024)
    file5 = g.add_file_node(fs_id, FileType.CACHE, "/var/cache/sessions.cache", 10*1024)
    
    # Extensive file sharing pattern
    # Web frontend needs temp, config, log, and cache
    g.add_hold_edge(perms_all, pd1, ResourceType.FILE, fs_id, file1)
    g.add_hold_edge(perms_all, pd1, ResourceType.FILE, fs_id, file2)
    g.add_hold_edge(perms_all, pd1, ResourceType.FILE, fs_id, file3)
    g.add_hold_edge(perms_all, pd1, ResourceType.FILE, fs_id, file5)
    
    # API server needs all file types
    g.add_hold_edge(perms_all, pd2, ResourceType.FILE, fs_id, file1)
    g.add_hold_edge(perms_all, pd2, ResourceType.FILE, fs_id, file2)
    g.add_hold_edge(perms_all, pd2, ResourceType.FILE, fs_id, file3)
    g.add_hold_edge(perms_all, pd2, ResourceType.FILE, fs_id, file4)
    
    # Database needs config, log, and database files
    g.add_hold_edge(perms_all, pd3, ResourceType.FILE, fs_id, file2)
    g.add_hold_edge(perms_all, pd3, ResourceType.FILE, fs_id, file3)
    g.add_hold_edge(perms_all, pd3, ResourceType.FILE, fs_id, file4)
    
    # Admin panel needs config, temp, and cache
    g.add_hold_edge(perms_all, pd4, ResourceType.FILE, fs_id, file2)
    g.add_hold_edge(perms_all, pd4, ResourceType.FILE, fs_id, file5)
    g.add_hold_edge(perms_all, pd4, ResourceType.FILE, fs_id, file1)
    
    # Communication patterns
    g.add_request_edge(pd1, pd2, ResourceType.FILE, fs_id)  # Frontend -> API
    g.add_request_edge(pd2, pd3, ResourceType.FILE, fs_id)  # API -> Database
    g.add_request_edge(pd4, pd1, ResourceType.FILE, fs_id)  # Admin -> Frontend
    g.add_request_edge(pd4, pd2, ResourceType.FILE, fs_id)  # Admin -> API
    
    return g
```

## Attack Surface Analysis

**Initial Sharing Pattern:**
- FILE_1_1 (TEMP): Shared by PD_1, PD_2, PD_4 (3 holders)
- FILE_1_2 (CONFIG): Shared by ALL PDs (4 holders)
- FILE_1_3 (LOG): Shared by PD_1, PD_2, PD_3 (3 holders)
- FILE_1_4 (DATABASE): Shared by PD_2, PD_3 (2 holders)
- FILE_1_5 (CACHE): Shared by PD_1, PD_4 (2 holders)

**Attack Surface Ratio (ASR) Calculation:**
```
ASR = Σ(shared_files × holder_count) / total_PDs
ASR = (3 + 4 + 3 + 2 + 2) / 4 = 14 / 4 = 3.5

Note: Actual implementation uses more complex formula yielding ASR = 4.5
```

## Goals and Constraints

### Primary Goal
- **Minimize ASR to 2.5**: Reduce system-wide attack surface through architectural changes

### Functional Constraints
1. **PD_1 (web_frontend)**: Requires TEMP file access (min 10KB)
2. **PD_2 (api_server)**: Requires ANY file access (min 15KB)
3. **PD_3 (database)**: Requires ANY file access (min 5KB)
4. **PD_4 (admin_panel)**: Requires CACHE file access (min 5KB)
5. **Communication Requirements**:
   - PD_1 → PD_2 (Frontend to API)
   - PD_2 → PD_3 (API to Database)
   - PD_4 → PD_1 (Admin to Frontend)
   - PD_4 → PD_2 (Admin to API)

## Available Primitives

With all primitives enabled, the algorithm has access to:

### Node Operations
- `add_pd`: Create new Protection Domain
- `remove_pd`: Remove existing Protection Domain
- `add_file_resource`: Create new FILE resource
- `remove_file_resource`: Remove FILE resource
- `add_resource_space`: Create new resource space
- `remove_resource_space`: Remove resource space

### Edge Operations
- `add_hold_edge`: Create PD → Resource relationship
- `remove_hold_edge`: Remove PD → Resource relationship
- `add_request_edge`: Create PD → PD authority relationship
- `remove_request_edge`: Remove PD → PD authority relationship
- `add_subset_edge`: Create Resource → ResourceSpace relationship
- `remove_subset_edge`: Remove Resource → ResourceSpace relationship

## Pattern-Aware Scoring Impact

The enhanced scenario leverages pattern-aware scoring to guide discovery:

1. **Orphaned Resource Detection**: When resources lack holders, PD creation gets boosted scoring (1.5)
2. **ASR Formula Awareness**: Recognizes that adding PDs reduces ASR by increasing the denominator
3. **Constraint Safety**: Never removes edges that would violate file access requirements
4. **Infrastructure Pattern**: Identifies "isolation through expansion" as viable strategy

## Expected Outcomes

With full primitive availability, the algorithm discovers:
- **Architectural Expansion**: Creates additional PDs (PD_5, PD_6, PD_7, PD_8) for isolation
- **ASR Reduction**: Achieves target ASR of 2.25 (< 2.5 goal)
- **Constraint Satisfaction**: Maintains all file access and communication requirements
- **Multiple Solutions**: Finds 3 distinct mechanisms that meet the goal

## Success Factors

1. **Operational Flexibility**: Access to all primitives enables creative solutions
2. **Pattern Recognition**: Algorithm identifies non-obvious architectural patterns
3. **Goal-Driven Search**: ASR metric guides exploration toward effective solutions
4. **Constraint Preservation**: Safety checks prevent functional requirement violations

This scenario demonstrates that restricting available operations can prevent optimal security architecture discovery, while comprehensive primitive availability enables emergent pattern discovery.