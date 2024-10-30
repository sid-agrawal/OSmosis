#!/bin/python3

import re
import argparse

def main():
    # Parse the arguments
    parser = argparse.ArgumentParser(description="Analyse iomem")
    parser.add_argument('--input', type=str, required=True, help='Input file')
    parser.add_argument('--out', type=str, required=True, help='Output file')
    args = parser.parse_args()

    f = open(args.input)

    curr_gPA = curr_hVA = curr_hPA = 0
    prev_gPA = prev_hVA = prev_hPA = 0

    page_size = 4096

    op_file = open(args.out, "w")
    for ln in f:        
        ln = ln.strip('\n')      
        # Regular expression to match hex values
        pattern = r"0x[0-9a-fA-F]+"

        # Find all hex values in the line
        hex_values = re.findall(pattern, ln)
        assert len(hex_values) == 3

        curr_gPA = int(hex_values[0], 16)
        curr_hVA = int(hex_values[1], 16)
        curr_hPA = int(hex_values[2], 16)
            
        cont_gPA = "" if (curr_gPA - prev_gPA == page_size) else "BRK"
        cont_hVA = "" if (curr_hVA - prev_hVA == page_size) else "BRK-VA"
        cont_hPA = "" if (curr_hPA - prev_hPA == page_size) else "BRK-PA"

        print(f"gPA : 0x{curr_gPA:<16x} {cont_gPA:6} --->"
              f" hVA: 0x{curr_hVA:<16x} {cont_hVA:6}"
              f" hPA: 0x{curr_hPA:<16x} {cont_hPA:6}", file=op_file)   
    
        prev_gPA = curr_gPA
        prev_hVA = curr_hVA
        prev_hPA = curr_hPA
    
if __name__ == "__main__":
    main()