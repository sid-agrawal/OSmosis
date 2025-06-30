# IsoSearch Decision Tree Visualizations

This directory contains decision tree visualizations for all IsoSearch scenarios, showing the complete exploration process as a tree of OSmosis graph states.

## Files

1. **basic_sharing_tree.html** - Basic Resource Sharing scenario
   - 2 PDs sharing 1 VMR resource with 1 mediator PD
   - Goals: minimize RSI to 0.3, TCB to 0, FR to 5
   - Result: 3 mechanisms discovered, could not achieve TCB goal

2. **high_sharing_tree.html** - High Resource Sharing scenario  
   - 3 PDs sharing multiple VMR resources with complex patterns
   - Goals: minimize RSI to 0.2, ASR to 2.0, TCB to 1
   - Result: 5 mechanisms discovered, successfully achieved all goals

3. **authority_chain_tree.html** - Authority Chain scenario
   - 4 PDs in authority hierarchy testing fault radius optimization
   - Goals: minimize FR to 3, TCB to 2, ASR to 1.5
   - Result: 2 mechanisms discovered, could not achieve FR goals

4. **rsi_focused_tree.html** - RSI Optimization scenario
   - Focus on minimizing resource sharing index only
   - Goals: minimize RSI to 0.1
   - Result: 4 mechanisms discovered, successfully achieved goal

5. **multi_objective_tree.html** - Multi-Objective Optimization scenario
   - Simultaneously optimize all metrics (most challenging)
   - Goals: minimize RSI to 0.3, ASR to 1.0, TCB to 1, FR to 4
   - Result: 3 mechanisms discovered, could not achieve FR goals

6. **attack_surface_reduction_tree.html** - Attack Surface Reduction scenario ⭐ **NEW**
   - Complex multi-service system demonstrating ASR metric optimization
   - Goals: minimize ASR to 2.5
   - Result: 5 mechanisms discovered, eliminated all shared resources (RSI: 1.0→0.0) but ASR remained at 4.5 due to REQUEST edges

## Visualization Features

Each HTML file contains:

- **Interactive Decision Tree**: Click nodes to view detailed OSmosis graph structures
- **Color-Coded Paths**: 
  - Blue: Initial state
  - Green: Selected transformations (applied)
  - Red: Discarded transformations (rejected)
- **Metrics Display**: Hover over nodes to see security metrics (RSI, ASR, TCB, FR)
- **Graph Viewer**: Detailed view of PDs, resources, and relationships for each state

## Key Insights

- **privatize_resource** is consistently the highest-impact transformation (1.0 improvement)
- **add_mediator_pd** is often available but rarely selected due to lower impact (0.5)
- **remove_hold_edge** is frequently used for fine-tuning (0.3 improvement)
- Multi-objective scenarios are significantly more challenging than single-objective
- Some combinations of goals (especially involving FR) are difficult to satisfy simultaneously
- **ASR (Attack Surface Ratio)** can be challenging to reduce when REQUEST edges remain (as seen in attack_surface_reduction scenario)
- Privatizing resources eliminates RSI but doesn't affect REQUEST edges contributing to ASR

## Generated

All visualizations were generated on 2024-06-30 using the IsoSearch algorithm with the `--visualize` flag.

```bash
python isosearch.py <scenario_name> --visualize
```