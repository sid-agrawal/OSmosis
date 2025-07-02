# Case Study Results

This directory contains the HTML visualization files generated from running the IsoSearch case studies for the workshop paper.

## Files Generated

### Case Study 1: Resource Isolation (basic_sharing scenario)
- **Timeline Visualization**: `isosearch_viz_basic_sharing_*.html`
- **Decision Tree**: `isosearch_tree_basic_sharing_*.html`

**Key Results:**
- Initial RSI: 0.143 (14.3% sharing between PD_1 and PD_2)
- Final RSI: 0.000 (complete isolation achieved)
- Mechanism: `privatize_resource` transformation
- Iterations: 1 successful transformation

### Case Study 2: Authority Mediation (mediator_test scenario)  
- **Timeline Visualization**: `isosearch_viz_mediator_test_*.html`
- **Decision Tree**: `isosearch_tree_mediator_test_*.html`

**Key Results:**
- Initial RSI: 0.143 (14.3% sharing between PD_1 and PD_2)
- Final RSI: 0.000 (complete isolation through mediation)
- Mechanism: `add_mediator` transformation
- Iterations: 1 successful transformation
- Architecture: Created PD_3 as mediator with REQUEST edges from PD_1 and PD_2

## Viewing the Visualizations

Open any of the HTML files in a web browser to see:

1. **Timeline Visualization**: Interactive exploration timeline showing:
   - Initial graph state
   - Transformation decisions at each iteration
   - Metric improvements over time
   - Final security architecture

2. **Decision Tree**: Interactive decision tree showing:
   - Candidate transformations considered
   - Selection criteria and scoring
   - Alternative paths not taken
   - Exploration strategy effectiveness

### Case Study 3: Primitive-Only Approach (basic_sharing_primitive)
- **Timeline Visualization**: `isosearch_viz_basic_sharing_primitive_20250630_221119.html`
- **Decision Tree**: `isosearch_tree_basic_sharing_primitive_20250630_221119.html`

**Key Results:**
- Initial RSI: 0.143 (14.3% sharing between PD_1 and PD_2)
- Final RSI: 0.000 (complete isolation achieved in iteration 1!)
- Mechanism: `create_private_copy` primitive transformation
- **SUCCESS**: Primitives achieved same core outcome as multi-step transitions

**Primitive Features Demonstrated:**
- **Strategy 1**: Comprehensive primitive set with atomic graph operations
- **Strategy 3**: Constraint-guided discovery identified sharing violations (scores 0.7-0.95 vs 0.3 for basic primitives)
- **Intelligent prioritization**: Constraint-addressing candidates boosted by +0.5 priority
- **Effective decision making**: Selected optimal solution in iteration 1, then optimized ASR through additional PDs

## Comparison Summary

| Approach | Iterations to RSI=0.000 | Final RSI | Final TCB[PD_1] | Primitive Type |
|----------|-------------------------|-----------|-----------------|----------------|
| **Multi-step** (basic_sharing) | 1 | 0.000 | 0 | Multi-step |
| **Basic Primitives** (original) | ∞ | 0.143 | 1 | Limited |
| **Unified Primitives** (current) | 1 | 0.000 | 0 | Comprehensive |

## Usage for Workshop Paper

These visualizations provide concrete evidence of IsoSearch's automated security mechanism discovery capabilities, showing both the exploration process and the final security improvements achieved through systematic graph transformations. The unified primitive approach demonstrates that comprehensive primitive design can match multi-step transformation effectiveness.