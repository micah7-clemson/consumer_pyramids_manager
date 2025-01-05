# Consumer Pyramids Manager
This package is designed to allow for sampling, building, and managing the CMIE Consumer Pyramids Data. The program runs in a GUI built with tkinkter and compiled for Apple Silicon Mac on version 15.2 using pyinstaller on python 3.10. See the release details for the latest version.
<br/><br/>

## Author:
- Micah Thomas
- (micahdthomas@gmail.com)
<br/><br/>


## Program Menus
### Pyramid Builder
Allows the researcher to sample and construct pyramids. A simple GUI framework allows the user to select the sampling options:  

    Date Range: Date of observations
    Sampling Level: Sample on individuals or households
    Output Directory: Location for sampled data
    Variable Options: Desired variables in output data
    Export Format: File format on output data
    File Size: Size of output chunks
    Random Seed: Value to set for random sampling

The sampled data will be output to a folder `sampled_pyramids_YYYYMMDD_HHMM` containing the output chunks and a log file which details the sampling parameters. 

**NOTE:** Selecting large date ranges or many variables will result in significantly slower speeds. Merging on all data is not advised.
    <br/><br/>
### Variable Explorer
Allows the researcher to both view and select the desired variables from the available pyramids. Variables can also be selected outside the program by creating a custom variable selection based on the `pyramid_variables.yaml` in the repo.
<br/><br/>
### Configuration 
This menu shows the current configuration of the data including the data directory and output directories. The `reinitialization` option is used to rebase the program if new pyramids data is added to the data directory.
<br/><br/>

## Setup Instructions
This program is written as a standalone program and requires no dependencies. It was complied and tested on an arm64 Mac version 15.2. If you wish to use on an earlier version or a different architecture, you must recompile using pyinstaller. Due to program signatures, you may need to enable the program in settings. 

Upon first run, you must set both the data and output directories in the configuration menu. Failure to do so may result in errors. 

The data directory containing the raw data files from CMIE Consumer Pyramids must be structured as follows. 

    data_directory 
           ├── aspirational
           │   └── waves
           │       ├─- aspirational_india_YYYYMMDD_YYYYMMDD_R.csv
           |       └── ...
           ├── consumption
           │   ├── monthly
           │   │   ├── consumption_pyramids_YYYYMMDD_MS_rev.csv
           │   │   └── ...
           │   └── waves
           │       ├── consumption_pyramids_YYYYMMDD_YYYYMMDD_R.csv
           │       └── ...
           ├── income
           │   └── monthly
           │       ├── household
           │       │   ├── household_income_YYYYMMDD_MS_rev.csv
           │       │   └── ...
           │       └── individual
           │           ├── member_income_YYYYMMDD_MS_rev.csv
           │           └── ...
           └── people
               └── waves
                   ├── people_of_india_YYYYMMDD_YYYYMMDD_R.csv
                   └── ...

