import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os
import sys
import yaml
import time
import glob
import pandas as pd
from pathlib import Path
import re
from datetime import datetime
import random
import threading
from functools import reduce


global RANDOM_SEED
RANDOM_SEED = 126


# This function is used to find the path to files such that it works when bundled and standalone
def resource_path(relative_path):
    # Grabbing the absoulte path for pyinstaller
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, relative_path)
    if getattr(sys, "frozen", False):
        # Running in a bundle
        bundle_dir = os.path.dirname(sys.executable)
        return os.path.join(bundle_dir, "..", "Resources", relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

# This function pulls all of the individual and household IDs
def indiv_id_finder(config, progress_bar, warning_window):
    individuals = pd.DataFrame(columns=["HH_ID", "MEM_ID"])
    for pyramid_type in ["PEOPLE_WAVES_LOCATION", "INDIV_INC_MONTHLY_LOCATION"]:
        progress_value = 50 / len(
            glob.glob(
                os.path.join(
                    Path(
                        str(config["DATA_DIRECTORY"]) + "/" + config[pyramid_type] + "/"
                    ),
                    "*.csv",
                )
            )
        )
        for file in os.listdir(
            Path(str(config["DATA_DIRECTORY"]) + config[pyramid_type])
        ):
            if file.endswith(".csv"):
                pyramid = pd.read_csv(
                    Path(
                        str(config["DATA_DIRECTORY"])
                        + "/"
                        + config[pyramid_type]
                        + "/"
                        + file
                    ),
                    usecols=["HH_ID", "MEM_ID"],
                ).astype(str)
                individuals = pd.concat([individuals, pyramid], axis=0)
                individuals = individuals.drop_duplicates()
            progress_bar["value"] = progress_bar["value"] + progress_value
            warning_window.update()
    return individuals

# This function finds all of the available variables in the given pyramids data
def variable_finder(config):
    pyramid_variables = {}
    for pyramid_type in [
        "ASPIRATIONAL_WAVES",
        "CONSUMPTION_MONTHLY",
        "CONSUMPTION_WAVES",
        "HH_INC_MONTHLY",
        "INDIV_INC_MONTHLY",
        "PEOPLE_WAVES",
    ]:
        pyramid_type_location = pyramid_type + "_LOCATION"
        pyramid_files = glob.glob(
            os.path.join(
                Path(
                    str(config["DATA_DIRECTORY"]) + "/" + config[pyramid_type_location]
                ),
                "*.csv",
            )
        )
        unique_variables = {
            var for file in pyramid_files for var in pd.read_csv(file, nrows=0).columns
        }
        pyramid_variables[pyramid_type] = sorted(list(unique_variables))

    return pyramid_variables

# This function resets the configuration file used to manage the program
def reinitializer(config, progress_bar, warning_window):
    # Check data directory
    if config["DATA_DIRECTORY"] is None:
        messagebox.showerror("Error", "Data directory is missing.")
        return 1
    elif not os.path.exists(resource_path(config["DATA_DIRECTORY"])):
        messagebox.showerror("Error", "Data directory does not exist.")
        return 1
    
    individuals = indiv_id_finder(config, progress_bar, warning_window)
    pyramid_variables = variable_finder(config)
    individual_data_location = config["INDIV_INC_MONTHLY_LOCATION"]
    individual_monthly_pyramids = os.path.join(
        Path(str(config["DATA_DIRECTORY"]) + individual_data_location + "/"), "*.csv"
    )
    individual_monthly_pyramids = glob.glob(individual_monthly_pyramids)
    all_pyramid_dates = [re.findall(r"\d+", s) for s in individual_monthly_pyramids]
    pyramid_dates = [sublist[-1] if sublist else None for sublist in all_pyramid_dates]

    config["MIN_SAMPLE_DATE"] = datetime.strptime(
        min(pyramid_dates), "%Y%m%d"
    ).strftime("%m-%d-%Y")
    config["MAX_SAMPLE_DATE"] = datetime.strptime(
        max(pyramid_dates), "%Y%m%d"
    ).strftime("%m-%d-%Y")
    config["TOTAL_HOUSEHOLDS"] = individuals["HH_ID"].nunique()
    config["TOTAL_INDIVIDUALS"] = (
        individuals["HH_ID"] + individuals["MEM_ID"].str.zfill(2)
    ).nunique()
    config["INITIALIZATION_DATE"] = datetime.now().strftime("%m-%d-%Y")

    individuals.to_csv(resource_path("pyramid_ids.csv"), index=False)
    with open(resource_path("pyramid_variables.yaml"), "w") as f:
        yaml.dump(pyramid_variables, f)
    with open(resource_path("config.yaml"), "w") as f:
        yaml.dump(config, f)
    return


# This function constructs the sampled data
def pyramid_builder(
    data_dir,
    output_dir,
    file_format,
    file_size,
    random_seed,
    start_date,
    end_date,
    var_selection,
    selected_vars_location,
    is_sample_enabled,
    sample_type,
    selected_ids_location,
    n_households=None,
    n_individuals=None,
    running_flag=lambda: True,
    summary_text="",
):

    # Function used to check if the filename is appropraite for the month iteration
    def check_contains_month(list_of_date_files, current_month, date_format="%Y%m%d"):
        contains_checker = []
        for inner_list in list_of_date_files:
            current_month = current_month.replace(day=1)
            if len(inner_list) == 1:
                contains = (
                    datetime.strptime(inner_list[0], date_format).replace(day=1)
                    == current_month
                )
            else:
                contains = datetime.strptime(
                    inner_list[0], date_format
                ) <= current_month and datetime.strptime(
                    inner_list[1], date_format
                ) >= current_month.replace(
                    day=1
                )
            contains_checker.append(contains)
        return contains_checker

    # Create output directory with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    output_folder = os.path.join(output_dir, f"sampled_pyramids_{timestamp}")
    os.makedirs(output_folder, exist_ok=True)

    # Initialize variables
    continuing_df = pd.DataFrame()
    file_counter = 1
    file_size_bytes = float(file_size) * 1024 * 1024 * 1024  # Convert GB to bytes

    # Set random seed
    random.seed(random_seed)

    # Check output directory
    if output_dir is None:
        messagebox.showerror("Error", "Output directory is missing.")
        return 1
    if not os.path.exists(resource_path(output_dir)):
        messagebox.showerror("Error", "Output directory does not exist.")
        return 1
    
    # Check data directory
    if data_dir is None:
        messagebox.showerror("Error", "Data directory is missing.")
        return 1
    elif not os.path.exists(resource_path(data_dir)):
        messagebox.showerror("Error", "Data directory does not exist.")
        return 1

    # Sampling households or individuals based on user selection
    if is_sample_enabled:
        if not os.path.exists(resource_path("pyramid_ids.csv")):
            messagebox.showerror("Error", "Pyramid IDs not found.")
            return 1
        print("PASS")
        if sample_type == "ids":
            if not os.path.exists(resource_path(selected_ids_location)):
                messagebox.showerror("Error", "Selected IDs not found.")
                return 1
            else:
                sampled_ids = pd.read_csv(resource_path(selected_ids_location))
            print("YEP")
            if "MEM_ID" in sampled_ids.columns and "HH_ID" in sampled_ids.columns:
                sampled_individuals = (str(sampled_ids["HH_ID"]) + sampled_ids["MEM_ID"].astype(str).str.zfill(2)).tolist()
                sample_type == "individuals"
            elif "HH_ID" in sampled_ids.columns:
                sampled_households = sampled_ids["HH_ID"].tolist()
                sample_type == "households"
        else:
            print("NAH")
            pyramid_ids = pd.read_csv(resource_path("pyramid_ids.csv"))
            if sample_type == "households":
                print("BLEH")
                sampled_households = random.sample(
                    pyramid_ids["HH_ID"].tolist(), int(n_households)
                )
            elif sample_type == "individuals":
                sampled_individuals = random.sample(
                    (
                        pyramid_ids["HH_ID"] + pyramid_ids["MEM_ID"].str.zfill(2)
                    ).tolist(),
                    int(n_individuals),
                )

    # Variable selection as either the selected list or all variables
    if var_selection == "selected":
        if not os.path.exists(resource_path(selected_vars_location)):
            messagebox.showerror("Error", "Selected variables file does not exist.")
            return 1
        else:
            with open(resource_path(selected_vars_location), "r") as f:
                selected_vars = yaml.safe_load(f)
            selected_pyramid_types = [
                key for key in selected_vars.keys() if selected_vars[key]
            ]
    else:
        selected_pyramid_types = [
            "ASPIRATIONAL_WAVES",
            "CONSUMPTION_MONTHLY",
            "CONSUMPTION_WAVES",
            "HH_INC_MONTHLY",
            "INDIV_INC_MONTHLY",
            "PEOPLE_WAVES",
        ]
        if not os.path.exists(resource_path("pyramid_variables.yaml")):
            messagebox.showerror("Error", "Pyramid variables not found.")
            return 1
        else:
            with open(resource_path("pyramid_variables.yaml"), "r") as f:
                selected_vars = yaml.safe_load(f)

    # Pull all of the available data files for each of the pyramids
    selected_pyramid_files = {}
    for pyramid_type in selected_pyramid_types:
        pyramid_files = os.path.join(
            Path(
                str(data_dir)
                + config[pyramid_type + "_LOCATION"]
                + "/"
            ),
            "*.csv",
        )
        selected_pyramid_files[pyramid_type] = sorted(glob.glob((pyramid_files)))

    # Function used to export the merged data
    def export_dataframe(df, file_path, format):
        try:
            if format.lower() == ".csv":
                df.to_csv(f"{file_path}.csv", index=False)
            elif format.lower() == ".parquet":
                df.to_parquet(f"{file_path}.parquet", index=False)
            elif format.lower() == ".dta":
                if any(len(col) > 32 for col in df.columns):
                    df.columns = [col[:32] for col in df.columns]
                df.to_stata(f"{file_path}.dta", write_index=False)
        except Exception as e:
            print(f"Error exporting file: {e}")
            raise

    # Setting start and end dates
    current_month = datetime.strptime(start_date, "%m-%Y").replace(day=1)
    end_month = datetime.strptime(end_date, "%m-%Y").replace(day=1)

    # Looping through each time period
    while current_month <= end_month:
        if not running_flag():
            print("Operation cancelled by user")
            return 1
        # Dictionary to store current month's pyramids
        current_pyramids = {}
        # Looping through each of the desired pyramids
        for pyramid_type in selected_pyramid_types:
            if not running_flag():
                print("Operation cancelled by user")
                return 1

            ### Finding if that pyramid has data for the given month and locating that file
            pyramids_time_filter = check_contains_month(
                list_of_date_files=[
                    re.findall(r"\d+", s)
                    for s in selected_pyramid_files[pyramid_type]
                ],
                current_month=current_month,
            )
            correct_pyramid = [
                inner_list
                for inner_list, include in zip(
                    selected_pyramid_files[pyramid_type], pyramids_time_filter
                )
                if include
            ]
            correct_pyramid = correct_pyramid[0] if correct_pyramid else None
            if correct_pyramid is None:
                continue
            print(correct_pyramid)

            # Reading in the variables in the given pyramid file
            available_vars = pd.read_csv(correct_pyramid, nrows=0).columns.tolist()
            # Ensuring that at minimum these variables are included (necessary for merging)
            pyramid_selected_vars = list(
                set(
                    selected_vars[pyramid_type]
                    + ["HH_ID", "MEM_ID", "WAVE_NO", "MONTH"]
                )
            )
            vars_to_load = [
                col for col in pyramid_selected_vars if col in available_vars
            ]

            # Reading in the pyramid for the selected columns
            pyramid_iteration = pd.read_csv(correct_pyramid, usecols=vars_to_load)
            # Sampling the pyramid if desired
            if is_sample_enabled:
                if sample_type == "households":
                    pyramid_iteration = pyramid_iteration[
                        pyramid_iteration["HH_ID"]
                        .astype(str)
                        .isin(sampled_households)
                    ]
                elif sample_type == "individuals":
                    if "MEM_ID" in pyramid_iteration.columns:
                        # For pyramids that have individual-level data
                        pyramid_iteration = pyramid_iteration[
                            (
                                pyramid_iteration["HH_ID"].astype(str)
                                + pyramid_iteration["MEM_ID"]
                                .astype(str)
                                .str.zfill(2)
                            ).isin(sampled_individuals)
                        ]
                    else:
                        # For household-level pyramids, just filter by the household part of the individual IDs
                        sampled_households = [
                            id[:8] for id in sampled_individuals
                        ]  # Assuming HH_ID is 8 digits
                        pyramid_iteration = pyramid_iteration[
                            pyramid_iteration["HH_ID"]
                            .astype(str)
                            .isin(sampled_households)
                        ]
            # Storing the pyramid iteration to the data dictionary
            current_pyramids[pyramid_type] = pyramid_iteration

        # Merge pyramids for current month
        merged_df = None
        individual_pyramids = []
        household_pyramids = []

        # Separate individual and household level pyramids
        for ptype, df in current_pyramids.items():
            print(f"Processing {ptype}")
            # Remove duplicate columns except for key columns
            if ptype in ["INDIV_INC_MONTHLY", "PEOPLE_WAVES"]:
                individual_pyramids.append(df)
            else:
                household_pyramids.append(df)

        # Function to handle duplicate columns during merge
        def merge_with_duplicate_handling(left, right, on):
            # Get duplicate columns (excluding merge keys)
            duplicate_cols = set(left.columns) & set(right.columns) - set(on)
            if duplicate_cols:
                print(f"Dropping duplicate columns: {duplicate_cols}")
                # Drop duplicate columns from right dataframe
                right = right.drop(columns=duplicate_cols)
            return pd.merge(left, right, on=on, how="outer")

        # Merge individual level pyramids
        if individual_pyramids:
            print("Merging individual pyramids...")
            merged_individual = individual_pyramids[0]
            for right_df in individual_pyramids[1:]:
                merged_individual = merge_with_duplicate_handling(
                    merged_individual, right_df, on=["HH_ID", "MEM_ID"]
                )

        # Merge household level pyramids
        if household_pyramids:
            print("Merging household pyramids...")
            merged_household = household_pyramids[0]
            for right_df in household_pyramids[1:]:
                merged_household = merge_with_duplicate_handling(
                    merged_household, right_df, on=["HH_ID"]
                )

        # Final merge between individual and household level data
        if individual_pyramids and household_pyramids:
            print("Performing final merge...")
            merged_df = merge_with_duplicate_handling(
                merged_individual, merged_household, on=["HH_ID"]
            )
        elif individual_pyramids:
            merged_df = merged_individual
        else:
            merged_df = merged_household

        # Concatenate with continuing DataFrame
        if continuing_df.empty:
            continuing_df = merged_df
        else:
            print("Concatenating with previous data...")
            # Align columns first and handle duplicates
            merged_df = merged_df.reindex(
                columns=continuing_df.columns, fill_value=None
            )
            continuing_df = pd.concat([continuing_df, merged_df], ignore_index=True)

        print(
            f"Current DataFrame size: {continuing_df.memory_usage(deep=True).sum() / (1024**3):.2f} GB"
        )
        continuing_df = continuing_df.drop_duplicates()


        # Check file size and exporting if chunk exceeds the desired file size
        df_size = continuing_df.memory_usage(deep=True).sum()
        if df_size >= file_size_bytes or current_month == end_month:
            # Export to file
            file_path = os.path.join(output_folder, f"pyramid_part_{file_counter}")
            export_dataframe(continuing_df, file_path, file_format)
            # Reset continuing_df and increment counter
            continuing_df = pd.DataFrame()
            file_counter += 1

        # Move to next month with debugging
        print(f"Current date before increment: {current_month}")
        next_month = current_month.month % 12 + 1
        next_year = current_month.year + (current_month.month // 12)
        current_month = current_month.replace(month=next_month, year=next_year)
        print(f"Current date after increment: {current_month}")
        print(f"End date: {end_month}")
        print(f"Comparison: {current_month <= end_month}")


    # Export summary log to the output directory
    with open(os.path.join(output_folder, "log.txt"), "w") as f:
        f.write(summary_text)

    return output_folder


class CPB_GUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Consumer Pyramids Manager")
        self.center_window(self.root, 800, 600)
        # Create main container
        self.main_container = ttk.Frame(self.root)
        self.main_container.pack(fill="both", expand=True)
        # Start with main menu
        self.show_main_menu()

    # Function to center windows on the display
    def center_window(self, window, width=None, height=None):
        """Center a window on the screen"""
        window.update_idletasks()
        # Use provided dimensions or window's current dimensions
        win_width = width if width else window.winfo_width()
        win_height = height if height else window.winfo_height()
        # Get screen dimensions
        screen_width = window.winfo_screenwidth()
        screen_height = window.winfo_screenheight()
        # Calculate position
        x = (screen_width - win_width) // 2
        y = (screen_height - win_height) // 2
        # Set position
        window.geometry(f"+{x}+{y}")


    # Function to clear the given window
    def clear_window(self):
        # Destroy all widgets in main container
        if hasattr(self, "main_container"):
            for widget in self.main_container.winfo_children():
                widget.destroy()


    # Function to display the main menu
    def show_main_menu(self):
        self.clear_window()
        self.root.geometry("400x300")
        self.center_window(self.root, 400, 300)
        # Title Frame
        title_frame = ttk.Frame(self.main_container, padding="20")
        title_frame.pack(fill="x")

        title_label = ttk.Label(
            title_frame,
            text="Consumer Pyramids Manager",
            font=("Helvetica", 16, "bold"),
        )
        title_label.pack()
        # Buttons Frame
        buttons_frame = ttk.Frame(self.main_container, padding="20")
        buttons_frame.pack(fill="both", expand=True)
        # Stack of buttons
        self.create_option_button(buttons_frame, "Pyramid Builder", self.pyramid_builder_window)
        self.create_option_button(buttons_frame, "Variable Explorer", self.variable_explorer_window)
        self.create_option_button(buttons_frame, "Configuration", self.configuration_window)
        # self.create_option_button(buttons_frame, "Help", self.show_build_window)


    # Function to place option button on window
    def create_option_button(self, parent, text, command):
        button = ttk.Button(parent, text=text, command=command, width=30)
        button.pack(pady=10)

    # Function to make a call a new window
    def create_content_window(self, title):
        self.clear_window()
        # Title
        title_frame = ttk.Frame(self.main_container, padding="20")
        title_frame.pack(fill="x")
        title_label = ttk.Label(title_frame, text=title, font=("Helvetica", 14, "bold"))
        title_label.pack()
        # Content frame
        content_frame = ttk.Frame(self.main_container, padding="20")
        content_frame.pack(fill="both", expand=True)
        # Create a frame for the action buttons
        action_frame = ttk.Frame(self.main_container)
        action_frame.pack(fill="x", side="bottom", padx=20, pady=(0, 10))
        # Button frame for back button
        button_frame = ttk.Frame(self.main_container, padding="20")
        button_frame.pack(fill="x", side="bottom")
        # Back button
        back_button = ttk.Button(
            button_frame, text="Back", command=self.show_main_menu, width=15
        )
        back_button.pack(side="left", padx=5)
        return content_frame, action_frame, button_frame

    # Function to create the main pyramid sampling driver
    def pyramid_builder_window(self):
        content_frame, action_frame, button_frame = self.create_content_window(
            "Pyramid Builder"
        )
        self.root.geometry("700x800")
        self.center_window(self.root, 700, 800)


        ### DATE SELECTION OPTIONS
        # Create date range frame
        date_frame = ttk.Frame(content_frame)
        date_frame.pack(fill="x", padx=20, pady=20)
        # Create left (start date) and right (end date) frames
        start_frame = ttk.Frame(date_frame)
        start_frame.pack(side="left", padx=(0, 20))
        end_frame = ttk.Frame(date_frame)
        end_frame.pack(side="left")
        # Labels
        ttk.Label(start_frame, text="Start Date").pack(anchor="w")
        ttk.Label(end_frame, text="End Date").pack(anchor="w")
        # Generate date options
        def generate_date_options():
            start_date = datetime.strptime(config["MIN_SAMPLE_DATE"], "%m-%d-%Y")
            end_date = datetime.strptime(config["MAX_SAMPLE_DATE"], "%m-%d-%Y")
            date_list = []

            current_date = start_date
            while current_date <= end_date:
                date_list.append(current_date.strftime("%m-%Y"))
                # Move to next month
                if current_date.month == 12:
                    current_date = datetime(current_date.year + 1, 1, 1)
                else:
                    current_date = datetime(
                        current_date.year, current_date.month + 1, 1
                    )

            return date_list

        date_options = generate_date_options()

        # Variables to store selected dates
        start_var = tk.StringVar()
        end_var = tk.StringVar()

        # Function to check that the dates in the boxes are compliant
        def validate_dates(*args):
            try:
                start_date = datetime.strptime(start_var.get(), "%m-%Y")
                end_date = datetime.strptime(end_var.get(), "%m-%Y")
                # If start date is after end date, adjust end date
                if start_date > end_date:
                    end_var.set(start_var.get())
                # Update available end dates
                end_dates = [
                    date
                    for date in date_options
                    if datetime.strptime(date, "%m-%Y") >= start_date
                ]
                end_combobox["values"] = end_dates
                # Update available start dates
                start_dates = [
                    date
                    for date in date_options
                    if datetime.strptime(date, "%m-%Y") <= end_date
                ]
                start_combobox["values"] = start_dates
            except ValueError:
                pass

        # Boxes used to select the start and end dates
        start_combobox = ttk.Combobox(
            start_frame,
            textvariable=start_var,
            values=date_options,
            width=10,
            state="readonly",
        )
        start_combobox.pack(pady=(0, 0))
        end_combobox = ttk.Combobox(
            end_frame,
            textvariable=end_var,
            values=date_options,
            width=10,
            state="readonly",
        )
        end_combobox.pack(pady=(0, 0))

        # Set initial values (earliest date for start, latest for end)
        start_var.set(date_options[0])  # First date
        end_var.set(date_options[-1])  # Last date

        # Bind validation to variable changes
        start_var.trace("w", validate_dates)
        end_var.trace("w", validate_dates)

        # Initial validation
        validate_dates()


        ### DATA SAMPLING OPTIONS
        # Create sample observations frame
        sample_frame = ttk.Frame(content_frame)
        sample_frame.pack(fill="x", padx=20, pady=(0, 0), anchor="w")

        # Main sample observations row
        sample_enabled = tk.BooleanVar(value=False)
        sample_radio = ttk.Checkbutton(
            sample_frame, text="Sample Observations", variable=sample_enabled
        )
        sample_radio.pack(anchor="w")

        # Create indented frame for options
        options_frame = ttk.Frame(sample_frame)
        options_frame.pack(fill="x", padx=(20, 0), pady=(5, 0))

        # Variable to track which option is selected (households or individuals)
        sample_type = tk.StringVar(value="households")  # Default to households

        # Household selection options
        households_frame = ttk.Frame(options_frame)
        households_frame.pack(fill="x", pady=2)

        households_radio = ttk.Radiobutton(
            households_frame,
            text="Households:",
            variable=sample_type,
            value="households",
            state="disabled",
        )
        households_radio.pack(side="left")

        # Function to check validity of the households selection
        def validate_household_value(event=None):
            try:
                # Try to convert to float first, then round to int
                value = float(households_value.get())
                value = round(value)
                # Clamp between min and max
                value = max(1, min(value, config["TOTAL_HOUSEHOLDS"]))
                households_value.set(str(value))
            except ValueError:
                # If conversion fails, reset to default
                households_value.set(str(config["TOTAL_HOUSEHOLDS"]))

        households_value = tk.StringVar(value=str(config["TOTAL_HOUSEHOLDS"]))

        households_spinbox = ttk.Spinbox(
            households_frame,
            from_=1,
            to=config["TOTAL_HOUSEHOLDS"],
            textvariable=households_value,
            width=10,
            state="disabled",
        )
        households_spinbox.pack(side="left", padx=(5, 0))

        # Bind validation to focus out and Enter key
        households_spinbox.bind("<FocusOut>", validate_household_value)
        households_spinbox.bind("<Return>", validate_household_value)

        # Individuals selection options
        individuals_frame = ttk.Frame(options_frame)
        individuals_frame.pack(fill="x", pady=2)

        individuals_radio = ttk.Radiobutton(
            individuals_frame,
            text="Individuals:",
            variable=sample_type,
            value="individuals",
            state="disabled",
        )
        individuals_radio.pack(side="left")

        # Function to validate the individual selections
        def validate_individual_value(event=None):
            try:
                # Try to convert to float first, then round to int
                value = float(individuals_value.get())
                value = round(value)
                # Clamp between min and max
                value = max(1, min(value, config["TOTAL_INDIVIDUALS"]))
                individuals_value.set(str(value))
            except ValueError:
                # If conversion fails, reset to default
                individuals_value.set(str(config["TOTAL_INDIVIDUALS"]))

        individuals_value = tk.StringVar(value=str(config["TOTAL_INDIVIDUALS"]))

        individuals_spinbox = ttk.Spinbox(
            individuals_frame,
            from_=1,
            to=config["TOTAL_INDIVIDUALS"],
            textvariable=individuals_value,
            width=10,
            state="disabled",
        )
        individuals_spinbox.pack(side="left", padx=(5, 0))

        # Bind validation to focus out and Enter key
        individuals_spinbox.bind("<FocusOut>", validate_individual_value)
        individuals_spinbox.bind("<Return>", validate_individual_value)

        # Function to check consistency of selection of sampling options
        def update_sample_state(*args):
            state = "normal" if sample_enabled.get() else "disabled"
            households_radio.configure(state=state)
            individuals_radio.configure(state=state)
            ids_radio.configure(state=state)
            households_spinbox.configure(state=state)
            individuals_spinbox.configure(state=state)
            ids_file_entry.configure(state=state)
            ids_file_button.configure(state=state)

            # If enabling and nothing selected, default to households
            if sample_enabled.get() and not sample_type.get():
                sample_type.set("households")

            # Configure specific states based on selection
            if sample_enabled.get():
                if sample_type.get() == "households":
                    individuals_spinbox.configure(state="disabled")
                    ids_file_entry.configure(state="disabled")
                    ids_file_button.configure(state="disabled")
                elif sample_type.get() == "individuals":
                    households_spinbox.configure(state="disabled")
                    ids_file_entry.configure(state="disabled")
                    ids_file_button.configure(state="disabled")
                else:  # ids
                    households_spinbox.configure(state="disabled")
                    individuals_spinbox.configure(state="disabled")

            # Reset to max values if disabled
            if not sample_enabled.get():
                households_value.set(str(config["TOTAL_HOUSEHOLDS"]))
                individuals_value.set(str(config["TOTAL_INDIVIDUALS"]))
                ids_file.set("")  # Clear the ids file path when disabled


        # Bind the update function to the sample_enabled variable
        sample_enabled.trace("w", update_sample_state)

        # Add the IDs radio button
        ids_radio = ttk.Radiobutton(
            sample_frame,
            text="Selected IDs:",
            variable=sample_type,
            value="ids",
            command=update_sample_state
        )
        ids_radio.pack(anchor="w", padx=(20, 0))

        # Add the IDs file selection box and button
        ids_file = tk.StringVar()
        ids_file_frame = ttk.Frame(sample_frame)
        ids_file_frame.pack(fill="x", padx=(40, 0))

        ids_file_entry = ttk.Entry(
            ids_file_frame,
            textvariable=ids_file,
            width=10
        )
        ids_file_entry.pack(side="left", fill="x", expand=True)

        # Function to search for variable selection file
        def browse_ids_file(ids_file):
            filename = filedialog.askopenfilename(
                initialdir=os.path.dirname(vars_file.get()),
                title="Select IDs File",
                filetypes=(("CSV files", "*.csv"), ("All files", "*.*")),
            )
            if filename:  # Only update if a file was selected
                ids_file.set(filename)

        ids_file_button = ttk.Button(
            ids_file_frame,
            text="Browse",
            command=lambda: browse_ids_file(ids_file)
        )
        ids_file_button.pack(side="right")


        # Initial state update
        update_sample_state()



        ### DATA DIRECTORY OPTIONS
        # Create output directory frame
        data_frame = ttk.Frame(content_frame)
        data_frame.pack(fill="x", padx=20, pady=(20, 0), anchor="w")

        # Output Directory Label
        ttk.Label(data_frame, text="Data Directory:").pack(anchor="w")

        # Create frame for directory entry and browse button
        dir_select_frame = ttk.Frame(data_frame)
        dir_select_frame.pack(fill="x", pady=(5, 0))

        # Directory entry
        data_dir = tk.StringVar(value=config.get("DATA_DIRECTORY", ""))
        dir_entry = ttk.Entry(dir_select_frame, textvariable=data_dir, width=50)  # Connect to data_dir
        dir_entry.pack(side="left", fill="x", expand=True)

        # Function to allow selection of the output directory
        def browse_directory():
            directory = filedialog.askdirectory(
                initialdir=data_dir.get() if data_dir.get() else "/",
                title="Select Data Directory",
            )
            if directory:  # Only update if a directory was selected
                data_dir.set(directory)
                config["DATA_DIRECTORY"] = directory  # Update config
                # Save to file
                with open(resource_path("config.yaml"), "w") as file:
                    yaml.dump(config, file)

        # Browse button
        browse_button = ttk.Button(
            dir_select_frame, text="Browse", command=browse_directory
        )
        browse_button.pack(side="left")



        ### OUTPUT DIRECTORY OPTIONS
        # Create output directory frame
        output_frame = ttk.Frame(content_frame)
        output_frame.pack(fill="x", padx=20, pady=(20, 0), anchor="w")

        # Output Directory Label
        ttk.Label(output_frame, text="Output Directory:").pack(anchor="w")

        # Create frame for directory entry and browse button
        dir_select_frame = ttk.Frame(output_frame)
        dir_select_frame.pack(fill="x", pady=(5, 0))

        # Directory entry
        output_dir = tk.StringVar(value=config.get("OUTPUT_DIRECTORY", ""))
        dir_entry = ttk.Entry(dir_select_frame, textvariable=output_dir, width=50)
        dir_entry.pack(side="left", fill="x", expand=True)

        # Function to allow selection of the output directory
        def browse_directory():
            directory = filedialog.askdirectory(
                initialdir=output_dir.get() if output_dir.get() else "/",
                title="Select Output Directory",
            )
            if directory:  # Only update if a directory was selected
                output_dir.set(directory)
                config["OUTPUT_DIRECTORY"] = directory  # Update config
                # Save to file
                with open(resource_path("config.yaml"), "w") as file:
                    yaml.dump(config, file)


        # Browse button
        browse_button = ttk.Button(
            dir_select_frame, text="Browse", command=browse_directory
        )
        browse_button.pack(side="left")




        ### VARIABLE SELECTION OPTIONS
        # Create Variable Options frame
        variables_frame = ttk.Frame(content_frame)
        variables_frame.pack(fill="x", padx=20, pady=(20, 0), anchor="w")

        # Variable Options Label
        ttk.Label(variables_frame, text="Variable Options:").pack(anchor="w")

        # Variable selection variable
        var_selection = tk.StringVar(value="all")  # Default to "all"

        # Use All Variables radio button
        all_vars_frame = ttk.Frame(variables_frame)
        all_vars_frame.pack(fill="x", pady=(5, 0))

        all_vars_radio = ttk.Radiobutton(
            all_vars_frame, text="All Variables", variable=var_selection, value="all"
        )
        all_vars_radio.pack(anchor="w")

        # Import Selected Variables radio button and file selection
        selected_vars_frame = ttk.Frame(variables_frame)
        selected_vars_frame.pack(fill="x", pady=(5, 0))

        selected_vars_radio = ttk.Radiobutton(
            selected_vars_frame,
            text="Selected Variables:",
            variable=var_selection,
            value="selected",
        )
        selected_vars_radio.pack(anchor="w")

        # Frame for file entry and browse button
        file_select_frame = ttk.Frame(variables_frame)
        file_select_frame.pack(fill="x", padx=(20, 0), pady=(5, 0))

        # Get default file path (current directory + filename)
        default_vars_file = os.path.join(
            resource_path("selected_pyramid_variables.yaml")
        )

        # File entry
        vars_file = tk.StringVar() #value=default_vars_file
        file_entry = ttk.Entry(file_select_frame, textvariable=vars_file, width=48)  # Add textvariable here
        file_entry.pack(side="left", fill="x", expand=True)

        # Function to search for variable selection file
        def browse_variables_file():
            filename = filedialog.askopenfilename(
                initialdir=os.path.dirname(vars_file.get()),
                title="Select Variables File",
                filetypes=(("YAML files", "*.yaml"), ("All files", "*.*")),
            )
            if filename:  # Only update if a file was selected
                vars_file.set(filename)


        # Browse button
        vars_browse_button = ttk.Button(
            file_select_frame, text="Browse", command=browse_variables_file
        )
        vars_browse_button.pack(side="left")

        # Function to update entry state based on radio selection
        def update_vars_state(*args):
            state = "normal" if var_selection.get() == "selected" else "disabled"
            file_entry.configure(state=state)
            vars_browse_button.configure(state=state)

        # Bind the update function to the var_selection variable
        var_selection.trace("w", update_vars_state)

        # Initial state update
        update_vars_state()

        ### FILE EXPORT OPTIONS
        # Create Export Options frame
        export_frame = ttk.Frame(content_frame)
        export_frame.pack(fill="x", padx=20, pady=(20, 0), anchor="w")

        # Export Format row
        format_frame = ttk.Frame(export_frame)
        format_frame.pack(fill="x", pady=(0, 5))

        ttk.Label(format_frame, text="Export Format:").pack(side="left")

        format_var = tk.StringVar()
        format_combobox = ttk.Combobox(format_frame, width=10, state="readonly")
        format_combobox["values"] = (".csv", ".dta", ".parquet")
        format_combobox.pack(side="left", padx=(5, 0))

        # Set default after a brief delay to ensure widget is fully initialized
        format_combobox.after(10, lambda: format_combobox.set(".csv"))

        # File Size row
        size_frame = ttk.Frame(export_frame)
        size_frame.pack(fill="x", pady=5)

        ttk.Label(size_frame, text="File Size:").pack(side="left")

        def validate_file_size(event=None):
            try:
                value = float(file_size_var.get())
                if value < 0.25:
                    value = 0.25
                # Remove trailing zeros after decimal point
                formatted_value = f"{value:.2f}".rstrip("0").rstrip(".")
                file_size_var.set(formatted_value)
            except ValueError:
                file_size_var.set("2.5")

        file_size_var = tk.StringVar(value="2.5")
        file_size_entry = ttk.Entry(
            size_frame, textvariable=file_size_var, width=4, justify="right"
        )
        file_size_entry.pack(side="left", padx=(5, 0))

        # Add GB label
        ttk.Label(size_frame, text="GB").pack(side="left", padx=(5, 0))

        # Bind validation to focus out and Enter key
        file_size_entry.bind("<FocusOut>", validate_file_size)
        file_size_entry.bind("<Return>", validate_file_size)

        # Random Seed row
        seed_frame = ttk.Frame(export_frame)
        seed_frame.pack(fill="x", pady=(5, 0))

        ttk.Label(seed_frame, text="Random Seed:").pack(side="left")

        def validate_seed(event=None):
            try:
                value = float(seed_var.get())
                # Convert to int and ensure positive
                value = max(0, int(value))
                seed_var.set(str(value))
            except ValueError:
                seed_var.set("126")

        seed_var = tk.StringVar(value="126")
        seed_entry = ttk.Entry(seed_frame, textvariable=seed_var, width=10)
        seed_entry.pack(side="left", padx=(5, 0))

        # Bind validation to focus out and Enter key
        seed_entry.bind("<FocusOut>", validate_seed)
        seed_entry.bind("<Return>", validate_seed)


        ### DATA BUILDER DRIVER
        # Button to initiate the data construction
        construct_button = ttk.Button(
            button_frame, text="Construct Data", command=lambda: show_summary_popup(), width=15
        )
        construct_button.pack(side="right", pady=5)  # Add consistent padding

        # Function to initiate building summary confirmation window
        def show_summary_popup():
            # Create popup window
            popup = tk.Toplevel(self.root)
            popup.title("Summary")
            popup.geometry("600x400")
            self.center_window(popup, 600, 400)
            popup.transient(self.root)
            popup.grab_set()

            # Create main frame for content
            popup_content = ttk.Frame(popup, padding="20")
            popup_content.pack(fill="both", expand=True)

            # Add summary title
            ttk.Label(
                popup_content,
                text="Please confirm your selections:",
                font=("Helvetica", 14),
            ).pack(anchor="w", pady=(0, 10))

            # Create summary text
            summary_frame = ttk.Frame(popup_content)
            summary_frame.pack(fill="both", expand=True)

            # Build summary text
            summary_text = f"""
Build Date/Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

Data Initialization Date: {config['INITIALIZATION_DATE']}

Data Directory: {data_dir.get()}
Output Directory: {output_dir.get()}
Export Format: {format_combobox.get()}
File Size: {file_size_var.get()} GB
Random Seed: {seed_var.get()}

Date Range: {start_var.get()} to {end_var.get()}

Variable Selection: {"All Variables" if var_selection.get() == "all" else "Selected Variables"}"""

            if var_selection.get() == "selected":
                summary_text += f"\nVariables File: {vars_file.get()}"

            if sample_enabled.get():
                sample_text = {
                    'households': 'Households',
                    'individuals': 'Individuals',
                    'ids': 'Selected IDs'
                }[sample_type.get()]
                
                if sample_type.get() in ["households", "individuals"]:
                    sample_value = (
                        households_value.get()
                        if sample_type.get() == "households"
                        else individuals_value.get()
                    )
                    summary_text += f"\n\nSample Observations: {sample_text}"
                    summary_text += f"\nSample Count: {sample_value}"
                else:  # ids
                    summary_text += f"\n\nSample Type: {sample_text}"
                    summary_text += f"\nIDs File: {ids_file.get()}"

            # Create text widget for summary
            summary_widget = tk.Text(
                summary_frame, wrap="word", height=12, width=50, font=("Helvetica", 13)
            )
            summary_widget.pack(fill="both", expand=True, pady=(0, 20))
            summary_widget.insert("1.0", summary_text)
            summary_widget.configure(state="disabled")  # Make read-only

            # Create button frame
            button_frame = ttk.Frame(popup_content)
            button_frame.pack(fill="x", pady=(0, 10))

            # Add Back button
            back_button = ttk.Button(button_frame, text="Back", command=popup.destroy)
            back_button.pack(side="left", padx=5)

            # Function to display the progress of the data construction
            def show_progress_window():
                popup.geometry("250x200")
                popup.running = True

                # Store the main window's current position
                main_x = self.root.winfo_x()
                main_y = self.root.winfo_y()

                # Clear the popup window
                for widget in popup_content.winfo_children():
                    widget.destroy()

                # Create frame for progress elements
                progress_frame = ttk.Frame(popup_content)
                progress_frame.pack(expand=True)

                # Center the popup relative to main window
                popup_width = 250
                popup_height = 200
                x = main_x + (self.root.winfo_width() - popup_width) // 2
                y = main_y + (self.root.winfo_height() - popup_height) // 2

                # Set the popup position
                popup.geometry(f"{popup_width}x{popup_height}+{x}+{y}")

                # Keep the main window centered
                self.center_window(self.root)

                # Add progress label
                progress_label = ttk.Label(
                    progress_frame, text="Processing...", font=("Helvetica", 16)
                )
                progress_label.pack(pady=(0, 10))

                # Add progress bar - set mode to indeterminate
                progress_bar = ttk.Progressbar(
                    progress_frame, length=200, mode="indeterminate"
                )
                progress_bar.pack()

                # Add Quit button
                quit_button = ttk.Button(
                    progress_frame,
                    text="Quit",
                    command=lambda: [stop_function(), popup.destroy()],
                )
                quit_button.pack(side="right", pady=(20, 0))

                # Function to call the pyramid builder
                def run_task():
                    popup.running = True
                    try:
                        # Your long running task here
                        pyramid_builder(
                            data_dir=data_dir.get(),
                            output_dir=output_dir.get(),
                            file_format=format_combobox.get(),
                            file_size=file_size_var.get(),
                            random_seed=int(seed_var.get()),
                            start_date=start_var.get(),
                            end_date=end_var.get(),
                            var_selection=var_selection.get(),
                            selected_vars_location=(
                                vars_file.get()
                                if var_selection.get() == "selected"
                                else None
                            ),
                            is_sample_enabled=sample_enabled.get(),
                            sample_type=sample_type.get(),
                            n_households=(
                                households_value.get()
                                if sample_type.get() == "households"
                                else None
                            ),
                            n_individuals=(
                                individuals_value.get()
                                if sample_type.get() == "individuals"
                                else None
                            ),
                            selected_ids_location=(
                                ids_file.get()
                                if sample_type.get() == "ids"
                                else None
                            ),
                            running_flag=lambda: popup.running,
                            summary_text=summary_text,
                        )

                        # After task completes, schedule the done button on the main thread
                        popup.after(0, show_done_button)
                    except Exception as e:
                        print(f"Error: {e}")
                    finally:
                        # Stop the progress bar
                        progress_bar.stop()

                # Function to initiate process on an individual thread
                def start_process():
                    # Start the progress bar
                    progress_bar.start(10)  # Update every 10ms

                    # Create and start the worker thread
                    thread = threading.Thread(target=run_task)
                    thread.daemon = (
                        True  # Make thread daemon so it closes with the window
                    )
                    thread.start()

                # Start the process after a short delay
                popup.after(100, start_process)

                def stop_function():
                    popup.running = False

                def show_done_button():
                    # Clear window
                    for widget in progress_frame.winfo_children():
                        widget.destroy()

                    # Create frame for done button
                    done_frame = ttk.Frame(progress_frame)
                    done_frame.pack(expand=True)

                    # Add Done button
                    done_btn = ttk.Button(
                        done_frame,
                        text="Done",
                        command=lambda: [popup.destroy(), self.show_main_menu()],
                        width=15,
                    )
                    done_btn.pack(expand=True, pady=20)

            # Add Continue button
            continue_button = ttk.Button(
                button_frame, text="Continue", command=show_progress_window
            )
            continue_button.pack(side="right", padx=5)

    # Function to build the variable exploration window
    def variable_explorer_window(self):
        content_frame, action_frame, button_frame = self.create_content_window(
            "Variable Explorer"
        )
        self.root.geometry("800x800")
        self.center_window(self.root, 800, 800)

        # Create a mapping of display names to actual category names
        button_display_names = {
            "ASPIRATIONAL_WAVES": "Aspirational (Waves)",
            "CONSUMPTION_MONTHLY": "Consumption (Monthly)",
            "CONSUMPTION_WAVES": "Consumption (Waves)",
            "HH_INC_MONTHLY": "Household Income (Monthly)",
            "INDIV_INC_MONTHLY": "Individual Income (Monthly)",
            "PEOPLE_WAVES": "Demographics (Waves)",
        }

        # Load the variables dictionary from your yaml file
        with open(resource_path("pyramid_variables.yaml"), "r") as f:
            variables_dict = yaml.safe_load(f)

        # Create frame for category buttons on the left
        category_frame = ttk.Frame(content_frame)
        category_frame.pack(side="left", fill="y", padx=(0, 10))

        # Create main frame for checkboxes
        main_frame = ttk.Frame(content_frame)
        main_frame.pack(side="left", fill="both", expand=True)

        # Create canvas and scrollbar
        canvas = tk.Canvas(main_frame, width=400)
        scrollbar = ttk.Scrollbar(main_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        # Configure canvas
        canvas.configure(yscrollcommand=scrollbar.set)

        # Dictionary to store checkbutton variables
        self.var_dict = {category: {} for category in variables_dict.keys()}

        # Dictionary to store category buttons
        self.category_buttons = {}

        # Current category tracker
        self.current_category = tk.StringVar(value=list(variables_dict.keys())[0])

        # Function to change the displayed variables based on the selection pyramid
        def show_category_variables(category):
            # Update button states
            for cat, btn in self.category_buttons.items():
                if cat == category:
                    btn.state(["pressed"])  # Set pressed state for selected button
                else:
                    btn.state(["!pressed"])  # Remove pressed state from other buttons

            # Clear current checkboxes
            for widget in scrollable_frame.winfo_children():
                widget.destroy()

            # Create checkboxes for selected category
            for var in variables_dict[category]:
                if var not in self.var_dict[category]:
                    self.var_dict[category][var] = tk.BooleanVar(value=False)

                chk = ttk.Checkbutton(
                    scrollable_frame, text=var, variable=self.var_dict[category][var]
                )
                chk.pack(anchor="w", pady=2)

            self.current_category.set(category)
            canvas.configure(scrollregion=canvas.bbox("all"))

        # Create style for the buttons
        style = ttk.Style()
        style.map(
            "Category.TButton",
            relief=[("pressed", "sunken"), ("!pressed", "raised")],
            background=[("pressed", "#d9d9d9"), ("!pressed", "white")],
        )

        # Create category buttons with display names
        for category, display_name in button_display_names.items():
            btn = ttk.Button(
                category_frame,
                text=display_name,
                command=lambda c=category: show_category_variables(c),
                width=20,
                style="Category.TButton",
            )
            btn.pack(pady=5)
            self.category_buttons[category] = btn

        # Show initial category
        show_category_variables(list(variables_dict.keys())[0])

        def select_all():
            current = self.current_category.get()
            for var in self.var_dict[current].values():
                var.set(True)

        def deselect_all():
            current = self.current_category.get()
            for var in self.var_dict[current].values():
                var.set(False)

        def export_selected():
            # Create warning popup
            warning = tk.Toplevel(self.root)
            warning.title("Export Variables")
            warning.geometry("500x200")
            # self.center_window(self.root, 500, 200)
            # warning.transient(self.root)
            # warning.grab_set()  # Make window modal

            # Warning message
            message = ttk.Label(
                warning,
                text="Choose the export location:",
                font=("Helvetica", 14),
                justify="left",
            )
            message.pack(anchor="w", pady=(20, 10), padx=(20,))

            # File path entry
            file_path = tk.StringVar(
                value=resource_path("selected_pyramid_variables.yaml")
            )
            path_entry = ttk.Entry(warning, textvariable=file_path, width=40)
            path_entry.pack(fill="x", padx=20)

            def browse_file():
                filename = filedialog.asksaveasfilename(
                    defaultextension=".yaml",
                    initialfile="selected_pyramid_variables.yaml",
                    filetypes=[("YAML files", "*.yaml"), ("All files", "*.*")],
                )
                if filename:
                    file_path.set(filename)

            # Browse button
            browse_btn = ttk.Button(
                warning, text="Browse", command=browse_file, width=10
            )
            browse_btn.pack(anchor="e", padx=20, pady=(5, 0))

            # Button frame
            btn_frame = ttk.Frame(warning)
            btn_frame.pack(fill="x", padx=20, pady=20, side="bottom")

            # Cancel button
            cancel_btn = ttk.Button(
                btn_frame, text="Cancel", command=warning.destroy, width=15
            )
            cancel_btn.pack(side="left", padx=5)

            # Save button
            def perform_export():
                selected_vars = {}
                for category in variables_dict.keys():
                    selected = [
                        var
                        for var, bool_var in self.var_dict[category].items()
                        if bool_var.get()
                    ]
                    # if selected:  # Only add category if there are selected variables
                    selected_vars[category] = selected

                # Save to the selected file location
                try:
                    with open(file_path.get(), "w") as f:
                        yaml.dump(selected_vars, f)
                    warning.destroy()
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to save file: {str(e)}")

            save_btn = ttk.Button(
                btn_frame, text="Save", command=perform_export, width=15
            )
            save_btn.pack(side="right", padx=0)

            # Center the popup window on the main window
            warning.geometry(
                "+{}+{}".format(
                    self.root.winfo_x() + (self.root.winfo_width() // 2 - 200),
                    self.root.winfo_y() + (self.root.winfo_height() // 2 - 100),
                )
            )
            self.center_window(
                "+{}+{}".format(
                    self.root.winfo_x() + (self.root.winfo_width() // 2 - 200),
                    self.root.winfo_y() + (self.root.winfo_height() // 2 - 100),
                )
            )

        # Set up scrollable frame
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")

        # Pack canvas and scrollbar
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        def on_frame_configure(event=None):
            canvas.configure(scrollregion=canvas.bbox("all"))
            canvas.itemconfig(frame_id, width=canvas.winfo_width())

        # Create the window and store its id
        frame_id = canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")

        # Bind the frame to configure events
        scrollable_frame.bind("<Configure>", on_frame_configure)
        canvas.bind(
            "<Configure>",
            lambda e: canvas.itemconfig(frame_id, width=canvas.winfo_width()),
        )

        # Configure mousewheel scrolling
        def on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        canvas.bind_all("<MouseWheel>", on_mousewheel)

        # Show initial category
        show_category_variables(list(variables_dict.keys())[0])

        # Create selection control buttons in the same frame as back button

        export_btn = ttk.Button(
            button_frame, text="Export", command=export_selected, width=15
        )
        export_btn.pack(side="right", padx=5)

        deselect_all_btn = ttk.Button(
            button_frame, text="Deselect All", command=deselect_all, width=15
        )
        deselect_all_btn.pack(side="right", padx=5)

        select_all_btn = ttk.Button(
            button_frame, text="Select All", command=select_all, width=15
        )
        select_all_btn.pack(side="right", padx=5)


    # Function used to show the configuration window
    def configuration_window(self):
        content_frame, action_frame, button_frame = self.create_content_window(
            "Configuration"
        )
        self.root.geometry("600x500")
        self.center_window(self.root, 600, 500)

        def select_data_directory():
            directory = filedialog.askdirectory()
            if directory:
                # Update config with new directory
                config["DATA_DIRECTORY"] = directory
                # Save to file
                with open(resource_path("config.yaml"), "w") as file:
                    yaml.dump(config, file)
                # Refresh the window
                self.configuration_window()

        def select_output_directory():
            directory = filedialog.askdirectory()
            if directory:
                # Update config with new directory
                config["OUTPUT_DIRECTORY"] = directory
                # Save to file
                with open(resource_path("config.yaml"), "w") as file:
                    yaml.dump(config, file)
                # Refresh the window
                self.configuration_window()

        def show_reinit_warning():
            warning = tk.Toplevel(self.root)
            warning.title("Reinitialization")
            warning.geometry("400x200")
            warning.transient(self.root)
            warning.grab_set()
            self.center_window(warning, 400, 200)

            # Warning message
            message = ttk.Label(
                warning,
                text="This process takes ~5 minutes.\nIt will overwrite the existing config.yaml.\nDo you wish to continue?",
                font=("Helvetica", 14, "bold"),
                justify="center",
            )
            message.pack(expand=True)

            # Button frame
            btn_frame = ttk.Frame(warning)
            btn_frame.pack(fill="x", padx=20, pady=20)

            # No button
            no_btn = ttk.Button(
                btn_frame, text="Back", command=warning.destroy, width=8
            )
            no_btn.pack(side="left", padx=5)

            # Yes button
            yes_btn = ttk.Button(
                btn_frame,
                text="Continue",
                command=lambda: start_reinitialization(warning),
                width=8,
            )
            yes_btn.pack(side="right", padx=5)

            # Center the popup window on the main window
            warning.geometry(
                "+{}+{}".format(
                    self.root.winfo_x() + (self.root.winfo_width() // 2 - 200),
                    self.root.winfo_y() + (self.root.winfo_height() // 2 - 100),
                )
            )
            self.center_window(
                "+{}+{}".format(
                    self.root.winfo_x() + (self.root.winfo_width() // 2 - 200),
                    self.root.winfo_y() + (self.root.winfo_height() // 2 - 100),
                )
            )

        # Function used to rebuild the config file
        def start_reinitialization(warning_window):
            # Clear warning window but keep it
            for widget in warning_window.winfo_children():
                widget.destroy()

            # Create a frame to hold progress elements
            progress_frame = ttk.Frame(warning_window)
            progress_frame.pack(expand=True)

            # Add progress label
            progress_label = ttk.Label(
                progress_frame, text="Reinitializing...", font=("Helvetica", 16)
            )
            progress_label.pack(
                pady=(0, 10)
            )  # Reduced top padding, 10px bottom padding

            # Add progress bar
            progress_bar = ttk.Progressbar(
                progress_frame, length=200, mode="determinate"
            )
            progress_bar.pack()

            def show_done_button():
                # Clear window except title
                for widget in warning_window.winfo_children():
                    widget.destroy()

                # Create frame for done button to allow centering
                done_frame = ttk.Frame(warning_window)
                done_frame.pack(expand=True)

                # Add Done button
                done_btn = ttk.Button(
                    done_frame,
                    text="Done",
                    command=lambda: [warning_window.destroy(), self.configuration_window()],
                    width=15,
                )
                done_btn.pack(
                    expand=True, pady=20
                )  # Using expand=True for vertical centering

            def update_progress():
                reinitializer(config, progress_bar, warning_window)
                # Only show done button after progress bar reaches 100%
                progress_bar.update()
                warning_window.after(100, show_done_button)

            # Start the progress update
            warning_window.after(100, update_progress)


        # Define order and custom names for config keys
        config_display = [
            ("INITIALIZATION_DATE", "Configuration Date"),
            # ("DATA_DIRECTORY", "Data Directory"),
            # ("OUTPUT_DIRECTORY", "Output Directory"),
            ("MIN_SAMPLE_DATE", "Data Start Date"),
            ("MAX_SAMPLE_DATE", "Data End Date"),
            ("TOTAL_HOUSEHOLDS", "Households in Data"),
            ("TOTAL_INDIVIDUALS", "Individuals in Data"),
        ]

        # Create frame for config values (without scrollbar)
        config_frame = ttk.Frame(content_frame)
        config_frame.pack(fill="both", expand=True, padx=10, pady=10)

        # Display each config value in specified order
        for key, display_name in config_display:
            # Skip if key doesn't exist in config
            if key not in config:
                continue

            # Create frame for each key-value pair
            pair_frame = ttk.Frame(config_frame)
            pair_frame.pack(fill="x", pady=5)

            # Key label
            key_label = ttk.Label(
                pair_frame,
                text=f"{display_name}:",
                width=20,
                font=("Helvetica", 14, "bold"),
            )
            key_label.pack(side="left", padx=5)

            # Value label
            value_label = ttk.Label(
                pair_frame,
                text=str(config[key]),
                width=80,
            )
            value_label.pack(side="left", padx=5)

        ### DATA DIRECTORY OPTIONS
        # Create output directory frame
        data_frame = ttk.Frame(content_frame)
        data_frame.pack(fill="x", padx=20, pady=(20, 0), anchor="w")

        # Output Directory Label
        ttk.Label(data_frame, text="Data Directory:").pack(anchor="w")

        # Create frame for directory entry and browse button
        dir_select_frame = ttk.Frame(data_frame)
        dir_select_frame.pack(fill="x", pady=(5, 0))

        # Directory entry
        data_dir = tk.StringVar(value=config.get("DATA_DIRECTORY", ""))
        dir_entry = ttk.Entry(dir_select_frame, textvariable=data_dir, width=40)  # Connect to data_dir
        dir_entry.pack(side="left", fill="x", expand=True)

        # Function to allow selection of the output directory
        def browse_directory():
            directory = filedialog.askdirectory(
                initialdir=data_dir.get() if data_dir.get() else "/",
                title="Select Data Directory",
            )
            if directory:  # Only update if a directory was selected
                data_dir.set(directory)
                config["DATA_DIRECTORY"] = directory  # Update config
                # Save to file
                with open(resource_path("config.yaml"), "w") as file:
                    yaml.dump(config, file)
                update_reinit_button()  # Update button state

        # Function to update reinit button state
        def update_reinit_button():
            if data_dir.get().strip():  # Enable if there's a directory
                reinit_button.configure(state="normal")
            else:  # Disable if directory is empty
                reinit_button.configure(state="disabled")

        # Browse button
        browse_button = ttk.Button(
            dir_select_frame, text="Browse", command=browse_directory
        )
        browse_button.pack(side="left")

        # Add the reinit button (modified to start disabled)
        reinit_button = ttk.Button(
            button_frame, 
            text="Reinitialize", 
            command=show_reinit_warning, 
            width=15,
            state="disabled" if not data_dir.get().strip() else "normal"
        )
        reinit_button.pack(side="right", padx=5)

        # Initial button state
        update_reinit_button()



    # Function to start the GUI
    def run(self):
        self.root.mainloop()


# Function to initialize the config file during program start-up
def load_config():
    # Then use it when opening your config file:
    if not os.path.exists(resource_path("config.yaml")):
        # Create error window
        error_window = tk.Tk()
        error_window.title("Error")
        error_window.geometry("600x400")

        # Error message
        message_label = ttk.Label(
            error_window,
            text="CONFIG FILE NOT FOUND\n\nProgram terminated. \nCheck documentation.",
            font=("Helvetica", 16),
            justify="center",
        )
        message_label.pack(expand=True)

        # Close button
        close_button = ttk.Button(
            error_window, text="Close", command=lambda: sys.exit()
        )
        close_button.pack(pady=20)

        error_window.mainloop()
        return 0
    else:
        global config
        with open(resource_path("config.yaml"), "r") as f:
            config = yaml.safe_load(f)
        return 1


if __name__ == "__main__":
    if load_config():
        app = CPB_GUI()
        app.run()
