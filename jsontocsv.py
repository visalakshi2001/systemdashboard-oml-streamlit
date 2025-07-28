import json
import csv
import os

import pandas as pd

def json_to_csv(csv_output_path, json_input_path="", json_file_object=None):
    """
    Converts a JSON file (with 'head'->'vars' and 'results'->'bindings') to a CSV file.
    If a column's value is missing in bindings, it writes an empty value.
    If a binding's value is a URI containing '#', only the part after '#' is extracted.
    """
    # 1. Read the JSON file
    if json_input_path != "" and json_file_object != None:
        raise Exception("Only provide either file object or file path")
    elif json_input_path == "" and json_file_object == None:
        raise Exception("Provide wither file object or file path of json file")
    elif json_file_object != None:
        data = json.loads(json_file_object)
    elif json_input_path != "":
        with open(json_input_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

    # 2. Extract columns from data["head"]["vars"]
    columns = data["head"]["vars"]

    # 3. Get rows from data["results"]["bindings"]
    bindings = data["results"]["bindings"]

    # 4. Create and write to a CSV file
    with open(csv_output_path, 'w+', newline='', encoding='utf-8') as csv_file:
        writer = csv.writer(csv_file)
        # Write header row
        writer.writerow(columns)

        # 5. For each row in the JSON, gather values for each column
        for row_binding in bindings:
            row_data = []
            for col in columns:
                # If the column is missing, write empty string
                if col not in row_binding:
                    row_data.append('')
                    continue

                # Otherwise, get the "value"
                value = row_binding[col].get('value', '')

                # If there's a '#' in the URI or string, split and take the last part
                if '#' in value:
                    value = value.split('#')[-1]

                row_data.append(value)

            writer.writerow(row_data)

def validate_csv(file_path, expected_columns, skip_non_null_check=False):
    try:
        df = pd.read_csv(file_path)

        # Check if all expected columns are present
        if not set(expected_columns).issubset(df.columns):
            print(f"{file_path} has Missing required columns.")
            return False

        if not skip_non_null_check:
            # Drop rows with any null values
            non_null_rows = df.dropna()

            # Also check for empty strings (optional, if required)
            non_null_rows = non_null_rows[~(non_null_rows == '').any(axis=1)]

            # Check if any rows remain
            if len(non_null_rows) == 0:
                print("No complete non-null rows found.")
                return False

        return True

    except Exception as e:
        print(f"Error reading CSV: {e}")
        return False

# if __name__ == "__main__":
    # json_to_csv(json_input_path="reports/system_dashboard/TestEquipment.json", csv_output_path="reports/system_dashboard/TestEquipment.csv")
    # json_to_csv(json_input_path="reports/system_dashboard/TestFacilities.json", csv_output_path="reports/system_dashboard/TestFacilities.csv")
    # json_to_csv(json_input_path="reports/system_dashboard/TestPersonnel.json", csv_output_path="reports/system_dashboard/TestPersonnel.csv")
    # json_to_csv(json_input_path="reports/system_dashboard/TestStrategy.json", csv_output_path="reports/system_dashboard/TestStrategy.csv")
