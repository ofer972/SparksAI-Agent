@echo off
REM Batch script to combine all Python files into combined_backend.txt
REM Generic script that works with any Python files in the directory

echo Combining all Python files into combined_agent.txt...

REM Delete the output file if it exists
if exist combined_agent.txt del combined_agent.txt

REM Loop through all .py files and append them to combined_agent.txt
for %%f in (*.py) do (
    echo. >> combined_agent.txt
    echo ========================================== >> combined_agent.txt
    echo File: %%f >> combined_agent.txt
    echo ========================================== >> combined_agent.txt
    echo. >> combined_agent.txt
    type "%%f" >> combined_agent.txt
    echo. >> combined_agent.txt
    echo. >> combined_agent.txt
)

echo Done! All Python files have been combined into combined_agent.txt
pause


