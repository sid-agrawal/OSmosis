# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

This is an OS modeling system that extracts process and memory state from Linux `/proc` filesystem, processes it into graph models, and visualizes them in Neo4j. The system combines C++ for efficient procfs parsing with Python for model processing and analysis.

## Setup and Build Commands

### Python Environment Setup
```bash
# Create and activate virtual environment
python -m venv venv
source ./venv/bin/activate

# Install Python dependencies
pip install -r requirements.txt
```

### C++ PFS Library Build
```bash
# Navigate to pfs directory and build
cd pfs
cmake .
make

# This generates a Python module at: pfs/lib/pypfs.[...].so
```

### Running the Main Model Extraction
```bash
# Must run with sudo to access /proc data, preserving virtualenv
sudo -E env PATH="./venv/bin:$PATH" python proc_model.py
```

### Neo4j Setup (Local Docker)
```bash
# Start local Neo4j with CSV data
./neo4j_docker.sh start <csv_file>

# Access at http://localhost:7474
# Stop when done
./neo4j_docker.sh stop
```

## Architecture

### Core Components

- **proc_model.py**: Main entry point for process model extraction
- **vm_model.py**: Virtual machine model extraction (QEMU/Cellulos support)
- **pfs/**: C++ library for efficient procfs parsing with Python bindings
- **procfs_data.py**: Data structures for process, memory, and namespace modeling
- **csv_processing.py**: Processes raw model state into proper graph format
- **import_csv.py**: Imports processed CSV data into Neo4j
- **metrics.py**: Calculates RSI (Resource Sharing Index) and FR (Fault Ratio) metrics

### Data Flow

1. Extract raw process/memory state → CSV files (prefixed with `raw_`)
2. Process implementation-level data to model-level → processed CSV files
3. Import to Neo4j for visualization and querying
4. Calculate metrics on model relationships

### Key Data Structures

- **Process**: Contains PID, namespaces, memory mappings, file descriptors
- **VMR (Virtual Memory Region)**: Virtual memory mappings with page-level data
- **PMR (Physical Memory Region)**: Physical memory representations  
- **Namespace**: Different namespace types (PID, network, etc.)
- **MappingType**: Categorizes memory mapping types (heap, stack, file, etc.)

## Testing and Validation

### Running Tests
```bash
# C++ library tests
cd pfs
make unittest
./unittest

# Python test script
python test.py
```

### Processing Pipeline Test
```bash
# Process raw CSV files (prefixed with raw_)
python csv_processing.py

# Import specific CSV to Neo4j (requires setup)
python import_csv.py -i <index>

# Calculate metrics for specific PD pair
python metrics.py <config_index>
```

## Common Development Patterns

### Working with PFS Library
```python
import sys
sys.path.append("pfs/lib")
import pypfs

pfs_obj = pypfs.procfs()
processes = pfs_obj.get_processes()
```

### Process Configuration Structure
The system uses run configurations in `proc_model.py` to define which programs to monitor. Add new programs to `program_names` and configure in `run_configs`.

### Memory Analysis
The system supports detailed memory analysis including:
- Page-level virtual to physical mappings via `/proc/pid/pagemap`
- Memory region categorization (heap, stack, shared libraries)
- Cross-process memory sharing detection

### Namespace Support
Full Linux namespace analysis including PID, network, mount, and user namespaces. The system currently supports up to 2 levels of PID namespace nesting.

## Important Files

- `requirements.txt`: Python dependencies including neo4j, pandas, networkx
- `config.txt`: Neo4j connection configuration (auto-generated)
- `outputs/`: Directory containing timestamped model extraction results
- `manual_examples/`: Hand-crafted examples for specific security mechanisms (CZ, LWC, etc.)