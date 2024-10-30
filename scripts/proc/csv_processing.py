""" 
Convert a raw CSV output from the CellulOS implementation to the OSmosis model

Transformations:
- Any PD with access to more than one ADS is converted into separate PDs per ADS 
- Any PD with access to more than one CPU is converted into separate PDs per CPU
"""

import pandas as pd
import os
import re
import logging, sys

logging.basicConfig(stream=sys.stderr, level=logging.INFO)
pd.set_option('future.no_silent_downcasting', True)

ROOT_TASK_PD = "PD_0"
TEST_TASK_PD = "PD_1"
IGNORE_PDS = [ROOT_TASK_PD,TEST_TASK_PD]

def read_csv_to_dataframe(filename):
    try:
        # Read CSV file into a pandas DataFrame
        df = pd.read_csv(filename, on_bad_lines='skip')
        return df
    except FileNotFoundError:
        logging.error(f"Error: File '{filename}' not found.")
        return None
    except Exception as e:
        logging.error(f"An error occurred: {e}")
        return None
    
def split_by_ads(df):
    resource_rows = df[df['NODE_TYPE'] == 'RESOURCE']

    vmr_rows = resource_rows[resource_rows['DATA'] == 'VMR']
    vmr_ids = vmr_rows['NODE_ID'].dropna().unique().tolist()
    vmr_out_edges = df[df['EDGE_FROM'].isin(vmr_ids)]

    pd_rows = df[df['NODE_TYPE'] == 'PD']
    pd_ids = pd_rows['NODE_ID'].dropna().unique().tolist()

    logging.debug(f"VMR IDS {vmr_ids}")

    # Find resource ID of all ADS
    ads_ids = resource_rows[resource_rows['DATA'] == 'ADS']['NODE_ID']
    ads_ids = ads_ids.dropna().unique().tolist()

    # Find which ADS each PD has access to
    ads_rows = df[df['EDGE_TO'].isin(ads_ids) & df['EDGE_FROM'].isin(pd_ids)]
    ads_rows = ads_rows[['EDGE_TO','EDGE_FROM']]
    ads_rows = ads_rows[~ads_rows['EDGE_FROM'].isin(IGNORE_PDS)]   # Ignore the root/test task
    ads_rows_grouped = ads_rows.groupby('EDGE_FROM')

    # Check which PDs have more than one ADS
    for pd_id, group in ads_rows_grouped:
        logging.debug(f"{pd_id} has ADS: {list(group['EDGE_TO'])}")

        # Get all relations of the original PD
        pd_relations = df[(df['EDGE_FROM'] == pd_id) | (df['NODE_ID'] == pd_id)]

        # Remove the original PD relations from the df
        df = df[(df['EDGE_FROM'] != pd_id) & (df['NODE_ID'] != pd_id)]

        for i, ads_id in enumerate(group['EDGE_TO']):
            # Get the VMRs in this ADS
            vmr_ids_in_ads = vmr_out_edges[vmr_out_edges['EDGE_TO'] == ads_id]['EDGE_FROM'].dropna().unique().tolist()

            # Replace pd id
            new_pd_id = f"{pd_id}.{i}"

            # Copy all relations except to the VMRs from other ADS
            exclude_ids = list(set(vmr_ids) - set(vmr_ids_in_ads))
            new_pd_relations = pd_relations[~pd_relations['EDGE_TO'].isin(exclude_ids)]
            new_pd_relations = new_pd_relations.replace(pd_id, new_pd_id)
            df = df.replace(pd_id, new_pd_id)

            # Add to the DF
            df = pd.concat([df, new_pd_relations], ignore_index=True)

    return df

def split_by_cpu(df):
    resource_rows = df[df['NODE_TYPE'] == 'RESOURCE']
    pd_rows = df[df['NODE_TYPE'] == 'PD']
    pd_ids = pd_rows['NODE_ID'].dropna().unique().tolist()

    # Find resource ID of all CPU
    cpu_ids = resource_rows[resource_rows['DATA'] == 'VCPU']['NODE_ID']
    cpu_ids = cpu_ids.dropna().unique().tolist()

    # Find which CPU each PD has access to
    cpu_rows = df[df['EDGE_TO'].isin(cpu_ids) & df['EDGE_FROM'].isin(pd_ids)]
    cpu_rows = cpu_rows[['EDGE_TO','EDGE_FROM']]
    cpu_rows = cpu_rows[~cpu_rows['EDGE_FROM'].isin(IGNORE_PDS)]   # Ignore the root/test task
    cpu_rows_grouped = cpu_rows.groupby('EDGE_FROM')

    # Check which PDs have more than one CPU
    for pd_id, group in cpu_rows_grouped:
        logging.debug(f"{pd_id} has CPU: {list(group['EDGE_TO'])}")

        # Get all relations of the original PD
        pd_relations = df[(df['EDGE_FROM'] == pd_id) | (df['NODE_ID'] == pd_id)]

        # Remove the original PD relations from the df
        df = df[(df['EDGE_FROM'] != pd_id) & (df['NODE_ID'] != pd_id)]

        for i, cpu_id in enumerate(group['EDGE_TO']):
            # Replace pd id
            new_pd_id = f"{pd_id}.{i}"

            # Copy all relations except to the other CPUs
            exclude_ids = [id for id in cpu_ids if id != cpu_id]
            new_pd_relations = pd_relations[~pd_relations['EDGE_TO'].isin(exclude_ids)]
            new_pd_relations = new_pd_relations.replace(pd_id, new_pd_id)
            df = df.replace(pd_id, new_pd_id)

            # Add to the DF
            df = pd.concat([df, new_pd_relations], ignore_index=True)

    return df

if __name__ == "__main__":
    # Define the folder path and regex pattern
    folder_path = "./"
    regex_pattern = r"raw_.*\.csv"

    # Compile the regex pattern
    pattern = re.compile(regex_pattern)

    # List to store matching filenames
    matching_files = []

    # Iterate through all files in the folder
    for filename in os.listdir(folder_path):
        if pattern.match(filename):
            print(f"Load file '{filename}'")

            # Load CSV to dataframe
            df = read_csv_to_dataframe(filename)

            # Process data
            logging.info("Splitting PDs by CPU")
            df = split_by_cpu(df)
            logging.info("Splitting PDs by ADS")
            df = split_by_ads(df)

            # Save dataframe to CSV file
            out_filename = filename[4:]
            df.to_csv(out_filename, index=False)

            print(f"Processed file saved to '{out_filename}'")

