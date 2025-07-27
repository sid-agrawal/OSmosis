# Basic Sharing Scenario - Detailed Step-by-Step Walkthrough

## Initial Graph (Iteration 0)

```
┌─────────────────────────────────────────────────────────────────┐
│                        STARTING STATE                          │
└─────────────────────────────────────────────────────────────────┘

Graph Structure:
┌─────────────┐                          ┌─────────────┐
│    PD_1     │                          │    PD_2     │
│ user_process│                          │database_serv│
└─────────────┘                          └─────────────┘
   │  │  │  │                               │  │  │  │
   │  │  │  │             HOLD edges        │  │  │  │
   │  │  │  │                               │  │  │  │
   ▼  ▼  ▼  └──────────┐         ┌─────────┘  ▼  ▼  ▼
FILE_1_1    FILE_1_2   │         │        FILE_1_4  FILE_1_5
/etc/user.  /var/log/  │         │        /etc/data /var/log/
conf        user.log   │         │        base.conf database.log
(CONFIG)    (LOG)      │         │        (CONFIG)  (LOG)
   │           │       │         │           │        │
   │SUBSET     │SUBSET │         │SUBSET     │SUBSET  │SUBSET
   ▼           ▼       ▼         ▼           ▼        ▼
┌─────────────────────────────────────────────────────────────┐
│                    FILE_SPACE_1                             │
│               (File System Space)                           │
└─────────────────────────────────────────────────────────────┘
                              ▲         ▲
                   SUBSET     │         │     SUBSET
                              │         │
            ┌─────────────────┘         └─────────────────┐
            │                                             │
            ▼                                             ▼
       FILE_1_3                                      FILE_1_6
       /usr/lib/                                     /var/db/
       user.so                                       main.db
       (LIBRARY)                                     (DATABASE)
            ▲                                             ▲
            │ HOLD                                        │ HOLD
            │                                             │
            └─────────────┐         ┌───────────────────┘
                          │         │
                          ▼         ▼
                   ┌─────────────────────┐
                   │    FILE_1_7         │ ◄── SHARED RESOURCE!
                   │/tmp/shared_buffer   │
                   │.tmp (TEMP, 20KB)    │
                   └─────────────────────┘
                            │
                            │ SUBSET
                            ▼
                      FILE_SPACE_1

🔍 SECURITY VIOLATION:
   FILE_1_7 has HOLD edges from BOTH PD_1 and PD_2
   This violates isolation principles

📊 Initial Metrics:
   RSI[PD_1,PD_2] = 1/7 = 0.143  (VIOLATES goal ≤ 0.3? NO, within limit)
   ASR = 4.0                       (VIOLATES goal ≤ 1.0? YES)  
   TCB[PD_1] = [PD_2]             (VIOLATES goal ≤ 0? YES)
   TCB[PD_2] = [PD_1]             (VIOLATES goal ≤ 0? YES)
```

## Iteration 1: Candidate Generation & Selection

```
┌─────────────────────────────────────────────────────────────────┐
│                    CANDIDATE GENERATION                         │
└─────────────────────────────────────────────────────────────────┘

🎯 Available Transitions: 2

┌─────────────────────────────────────────────────────────────────┐
│ CANDIDATE 1: privatize_resource                                 │
├─────────────────────────────────────────────────────────────────┤
│ Target: FILE_1_7 (/tmp/shared_buffer.tmp)                      │
│ Strategy: Create private copies for each PD                     │
│ Predicted Improvement: 1.000                                   │
│ Rationale: Directly eliminates sharing violation               │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│ CANDIDATE 2: add_mediator                                       │
├─────────────────────────────────────────────────────────────────┤
│ Target: FILE_1_7 (/tmp/shared_buffer.tmp)                      │
│ Strategy: Create PD_3 as intermediary controller               │
│ Predicted Improvement: 0.500                                   │
│ Rationale: Controlled sharing through authority mediation      │
└─────────────────────────────────────────────────────────────────┘

🏆 SELECTION: privatize_resource (1.000 > 0.500)
   Algorithm chooses highest predicted improvement

❌ DISCARDED: add_mediator (lower score)
   Alternative path not explored in this iteration
```

## Iteration 1: Transformation Execution

```
┌─────────────────────────────────────────────────────────────────┐
│                  PRIVATIZE_RESOURCE STEPS                      │
└─────────────────────────────────────────────────────────────────┘

STEP 1: Analyze shared resource
   Target: FILE_1_7 (/tmp/shared_buffer.tmp)
   Holders: PD_1, PD_2
   
STEP 2: Create private copy for PD_1
   Create: FILE_1_8 (/etc/private_1.conf, CONFIG, 20KB)
   
STEP 3: Create private copy for PD_2  
   Create: FILE_1_9 (/etc/private_2.conf, CONFIG, 20KB)
   
STEP 4: Redirect PD_1 access
   Remove: PD_1 --HOLD--> FILE_1_7
   Add:    PD_1 --HOLD--> FILE_1_8
   
STEP 5: Redirect PD_2 access
   Remove: PD_2 --HOLD--> FILE_1_7  
   Add:    PD_2 --HOLD--> FILE_1_9
   
STEP 6: Remove shared resource
   Remove: FILE_1_7 and its SUBSET edge

✅ TRANSFORMATION SUCCESSFUL
```

## Post-Iteration 1 Graph

```
┌─────────────────────────────────────────────────────────────────┐
│                     AFTER ITERATION 1                          │
└─────────────────────────────────────────────────────────────────┘

Protection Domains:
┌─────────────┐              ┌─────────────┐
│    PD_1     │              │    PD_2     │
│ user_process│              │database_serv│
└─────────────┘              └─────────────┘
       │                            │
       │ HOLD                       │ HOLD
       ▼                            ▼
┌─────────────┐              ┌─────────────┐
│  FILE_1_1   │              │  FILE_1_4   │
│/etc/user.   │              │/etc/database│
│conf (CONFIG)│              │.conf(CONFIG)│
└─────────────┘              └─────────────┘
       │                            │
       │ SUBSET                     │ SUBSET
       ▼                            ▼
┌─────────────────────────────────────────────┐
│              FILE_SPACE_1                   │
│          (File System Space)                │
└─────────────────────────────────────────────┘
       ▲               ▲              ▲
       │ SUBSET        │ SUBSET       │ SUBSET
┌─────────────┐  ┌─────────────┐  ┌─────────────┐
│  FILE_1_2   │  │  FILE_1_8   │  │  FILE_1_5   │
│/var/log/user│  │/etc/private_│  │/var/log/data│
│.log (LOG)   │  │1.conf(CONFIG│  │base.log(LOG)│
└─────────────┘  └─────────────┘  └─────────────┘
       ▲               ▲              ▲
       │ HOLD          │ HOLD         │ HOLD
       │               │              │
┌─────────────┐        │        ┌─────────────┐
│  FILE_1_3   │        │        │  FILE_1_6   │
│/usr/lib/user│        │        │/var/db/main.│
│.so(LIBRARY) │        │        │db(DATABASE) │
└─────────────┘        │        └─────────────┘
       ▲               │              ▲
       │ HOLD          │              │ HOLD
       │               │              │
       └───────────────┘        ┌─────┘
                                │
                         ┌─────────────┐
                         │  FILE_1_9   │
                         │/etc/private_│
                         │2.conf(CONFIG│
                         └─────────────┘
                                │
                                │ SUBSET
                                ▼
                         FILE_SPACE_1 (shown above)

🎉 NO MORE SHARED RESOURCES!
   Each PD now has completely private file access

📊 Post-Iteration 1 Metrics:
   RSI[PD_1,PD_2] = 0/7 = 0.000   ✅ GOAL ACHIEVED (≤ 0.3)
   ASR = 4.0                       ❌ STILL VIOLATES (≤ 1.0)
   TCB[PD_1] = []                  ✅ GOAL ACHIEVED (≤ 0)
   TCB[PD_2] = []                  ✅ GOAL ACHIEVED (≤ 0)
```

## Iteration 2: No Further Progress

```
┌─────────────────────────────────────────────────────────────────┐
│                     ITERATION 2 ATTEMPT                        │
└─────────────────────────────────────────────────────────────────┘

🔍 Candidate Generation:
   - privatize_resource: No shared resources remain to privatize
   - add_mediator: No sharing patterns that benefit from mediation
   
🚫 RESULT: No valid transformation candidates found

⛔ EXPLORATION TERMINATED
   Reason: Algorithm cannot make further progress with available transitions
   Status: 2/3 goals achieved (RSI ✅, TCB ✅, ASR ❌)
```

## Summary: Graph Evolution

```
ITERATION 0 → ITERATION 1 → ITERATION 2
    |              |             |
    |              |             └─ TERMINATED
    |              |                (no candidates)
    |              |
    |              └─ privatize_resource applied
    |                 • Created FILE_1_8, FILE_1_9  
    |                 • Removed FILE_1_7
    |                 • Eliminated sharing
    |
    └─ SHARED RESOURCE VIOLATION
       • FILE_1_7 shared by PD_1, PD_2
       • RSI=0.143, TCB=[PD_2],[PD_1]

TRANSFORMATION SUCCESS:
✅ Sharing eliminated (RSI: 0.143 → 0.000)
✅ Dependencies removed (TCB: [PD_2] → [])  
❌ Attack surface unchanged (ASR: 4.0 → 4.0)
```

This detailed walkthrough shows exactly how IsoSearch:
1. **Identifies** the security violation (shared FILE_1_7)
2. **Generates** relevant transformation candidates
3. **Selects** the best option using predicted improvement
4. **Applies** the transformation through systematic steps
5. **Validates** constraint preservation and goal achievement
6. **Terminates** when no further progress is possible

The algorithm demonstrates intelligent problem-solving while maintaining safety guarantees throughout the exploration process.