# Beam Search Evaluation Summary - Beam Width 6 (July 18)

Configuration: Beam Width = 6, Max Iterations = 10

## Summary Table

| Scenario Name | Constraints | Goals | Iterations to First Valid Solution | Total Valid Solutions | Total Candidates Evaluated | Total Candidates Discarded |
|---------------|-------------|-------|------------------------------------|-----------------------|---------------------------|---------------------------|
| basic_sharing_primitive | 4 | 1 | 8 | 7 | 673 | 628 |
| mediator_test_primitive | 5 | 1 | - | 0 | 705 | 660 |
| reduce_isolation | 5 | 1 | 8 | 10 | 845 | 802 |

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
**Result:** No complete solution found within 8 iterations  
**Challenge:** The reduced beam width (6 vs 12) was insufficient to maintain the diverse paths needed to discover the complex 6-step mediation pattern required for this scenario.

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

## Comparison with Beam Width 12

| Scenario | BW=12 Solutions | BW=6 Solutions | Impact |
|----------|-----------------|----------------|--------|
| basic_sharing_primitive | 11 | 7 | -36% |
| mediator_test_primitive | 3 | 0 | -100% |
| reduce_isolation | 22 | 10 | -55% |

## Key Insights

1. **Beam Width Critical for Complex Scenarios:** The mediator_test_primitive failed completely with beam width 6, demonstrating that complex coordinated patterns require sufficient parallel exploration paths.

2. **Solution Discovery Delayed:** Both successful scenarios found their first solutions at the final iteration (8), compared to earlier discoveries with beam width 12.

3. **Reduced Solution Diversity:** All scenarios showed fewer total solutions with the narrower beam, indicating less exploration of the solution space.

4. **Aggressive Beam Selection:** With beam width 6, the algorithm discarded 94% of generated candidates:
   - basic_sharing_primitive: 628/673 candidates discarded (6.7% selection rate)
   - mediator_test_primitive: 660/705 candidates discarded (6.4% selection rate) 
   - reduce_isolation: 802/845 candidates discarded (5.1% selection rate)

This demonstrates the beam search's aggressive filtering to maintain diversity while managing computational complexity.