# Beam Search Evaluation Summary (July 18)

Configuration: Beam Width = 12, Max Iterations = 10

## Summary Table

| Scenario Name | Constraints | Goals | Iterations to First Valid Solution | Total Valid Solutions | Total Candidates Evaluated | Total Candidates Discarded |
|---------------|-------------|-------|------------------------------------|-----------------------|---------------------------|---------------------------|
| basic_sharing_primitive | 4 | 1 | 4 | 11 | 151 | 0 |
| mediator_test_primitive | 5 | 1 | 7 | 3 | 186 | 0 |
| reduce_isolation | 5 | 1 | 4 | 22 | 128 | 0 |

## Example Valid Solutions

### 1. basic_sharing_primitive
**Goal:** Minimize RSI[PD_1,PD_2] to 0.0
**Solution Path (3 steps):**
```
1. add_hold_edge(connect PD_1 to orphaned resource FILE_1_2)
2. add_pd(add new protection domain)
3. remove_hold_edge(remove PD_1 -> FILE_1_1 HOLD edge)
```
**Final Metrics:** RSI={'PD_1,PD_2': 0.0}, ASR=0.67
**Architecture:** Each PD holds different resources, achieving complete isolation

### 2. mediator_test_primitive
**Goal:** Minimize RSI[PD_1,PD_2] to 0.0
**Solution Path (6 steps):**
```
1. add_pd(add new protection domain PD_3)
2. add_hold_edge(connect PD_3 to FILE_1_1)
3. add_request_edge(create PD_1 -> PD_3 REQUEST)
4. remove_hold_edge(remove PD_1 -> FILE_1_1 HOLD edge)
5. add_request_edge(create PD_2 -> PD_3 REQUEST)
6. remove_hold_edge(remove PD_2 -> FILE_1_1 HOLD edge)
```
**Final Metrics:** RSI={'PD_1,PD_2': 0.0}, ASR=1.0
**Architecture:** PD_3 mediates access to FILE_1_1 for both PD_1 and PD_2

### 3. reduce_isolation
**Goal:** Maximize RSI (all pairs ≥ 0.5)
**Solution Path (3 steps):**
```
1. add_hold_edge(connect PD_1 to FILE_1_1)
2. add_request_edge(create PD_1 -> PD_2 REQUEST)
3. add_hold_edge(connect PD_2 to FILE_1_1)
```
**Final Metrics:** RSI={all pairs: 1.0}, ASR=1.75
**Architecture:** Increased resource sharing across all PDs

## Key Insights

1. **Solution Complexity:** mediator_test_primitive required the most iterations (7) to find a valid solution due to the complex coordinated 6-step mediation pattern required.

2. **Solution Diversity:** reduce_isolation found the most solutions (22), likely because maximizing RSI allows many valid configurations.

3. **Efficiency:** The beam search efficiently explored the design space without discarding candidates, maintaining diversity through the beam width.

4. **Constraint Impact:** Scenarios with more constraints (5 vs 4) generally required more exploration to find valid solutions.