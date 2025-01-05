# Consumer Pyramids Manager
This package is designed to allow for sampling, building, and managing the CMIE Consumer Pyramids Data. The program runs in a GUI built with tkinkter and compiled for Apple Silicon Mac on version 15.2 using pyinstaller on python 3.10. See the release details for the latest version.
<br/><br/>

## Author:
- Micah Thomas
- (micahdthomas@gmail.com)
<br/><br/>

## Setup Instructions
This program is written as a standalone program and requires no dependencies. It was complied and tested on an arm64 Mac version 15.2. If you wish to use on an earlier version or a different architecture, you must recompile using pyinstaller. Due to program signatures, you will need to bypass GateKeeper and self sign. Unzip and attempt to run the program. You will get a failure to load pop-up. Go to "Privacy & Security" in settings and scroll down to the "Security" section. Find the program listed in the section and select the option to "Open Anyway" and complete the prompts. You can now open the program as you would normally. 


The data directory containing the raw data files from must be structured as follows: 

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

<br/><br/>
## Program Menus
### Pyramid Builder
Allows the researcher to sample and construct pyramids using the following options:  

    Date Range: Date of observations
    Sampling Level: Sample on individuals or households
    Data Directory: Location for raw pyramids data
    Output Directory: Location for sampled data
    Variable Options: Desired variables in output data
    Export Format: File format on output data
    File Size: Size of output chunks
    Random Seed: Value to set for random sampling

The sampled data will be output to a folder `sampled_pyramids_YYYYMMDD_HHMM` containing the output chunks and a log file which details the sampling parameters. Note that selecting large date ranges or many variables will result in significantly slower speeds. **Merging on all data is not advised.**
    <br/><br/>
### Variable Explorer
Allows the researcher to both view and select the desired variables from the available pyramids. Variables can also be selected outside the program by creating a manual variable selection based on the `pyramid_variables.yaml` in the repo.
<br/><br/>
### Configuration 
This menu shows the current configuration of the data and the last configuration. The `reinitialization` option is used to rebase the program if new pyramids are added to the data directory. The button will be disabled until the appropriate data directory is input. 
<br/><br/>