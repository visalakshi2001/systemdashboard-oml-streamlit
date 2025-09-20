import os
import shutil
import re
import subprocess
from pathlib import Path
from utilities import logger

# Path to your project root (adjust if app.py lives elsewhere)
PROJECT_ROOT = Path(__file__).parent.resolve() / "omltemplateproject"
BUNDLE_PATH = PROJECT_ROOT / "src" / "oml" / "example.com" / "project" / "uaomlfile.oml"
BUILD_DIR   = PROJECT_ROOT / "build"
LOG_DIR     = BUILD_DIR / "logs"
SPARQL_DIR = PROJECT_ROOT / "src" / "sparql"

def buildoml(omlfile):
    # print("Received bundle upload:", omlfile.filename)
    # print(omlfile)
    # # 1. Validate upload
    # if not omlfile.filename.endswith(".oml"):
    #     raise HTTPException(status_code=400, detail="Must upload a .oml file")
    
    # 2. Ensure directories exist
    BUNDLE_PATH.parent.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    
    # 3. Save uploaded bundle.oml (overwrite any existing)
    with BUNDLE_PATH.open("w", encoding='utf-8') as f_out:
        contents = omlfile.read()
        # find the iri on first line of the file between '<http://(...)>' and replace with example.com/project/uaomlfile.oml
        contents = contents.decode('utf-8')
        # print(contents[:150])
        # print(re.sub(r'<http://.*?>', '<http://example.com/project/uaomlfile#>', contents, count=1)[:150])
        contents = re.sub(r'<http://.*?>', '<http://example.com/project/uaomlfile#>', contents, count=1)
        f_out.write(contents)
    
    # Provide executable permissions to the Gradle wrapper
    # code here
    for dirfile in os.listdir(PROJECT_ROOT):
        # st.write(dirfile, os.access(dirfile, os.X_OK))
        # st.write(os.stat(dirfile).st_mode | 0o100) 
        os.chmod(PROJECT_ROOT / dirfile, os.stat(PROJECT_ROOT / dirfile).st_mode | 0o100)
        # st.write(dirfile, os.access(dirfile, os.X_OK))
        # st.write("---"*10)

    # 4. Run Gradle build
    # Determine which Gradle wrapper to invoke
    if os.name == "nt":  # Windows
        wrapper = "gradlew.bat"
        # On Windows it’s often simpler to run under shell so the .bat is recognized
        shell_flag = True
    else:
        wrapper = str(PROJECT_ROOT / "gradlew")
        shell_flag = False
    
    cmd = [wrapper, "clean", "downloadDependencies", "build"]
    print(f"Running command: {' '.join(cmd)}")
    logger.infor(f"Running command: {' '.join(cmd)}")
    proc = subprocess.run(
        cmd,
        cwd=PROJECT_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        shell=shell_flag
    )
    
    
    # 5. Persist logs
    log_file = LOG_DIR / f"buildlogs_code{proc.returncode}.log"
    log_file.parent.mkdir(parents=True, exist_ok=True)
    with log_file.open("w") as log_file_f:
        log_file_f.write(proc.stdout)
        
    # 6. Prepare response URL
    #    We’ll serve BUILD_DIR on port 8080 (see next steps),
    #    so we just point clients there under /browse/
    
    return {
        "exit_code": proc.returncode,
        "log_path": str(log_file.relative_to(BUILD_DIR)),
    }


def sparql_query():

    # # check if SPARQL_DIR has sparql files
    # if not SPARQL_DIR.exists() or not any(SPARQL_DIR.glob("*.sparql")):
    #     return JSONResponse({"message": "No SPARQL files found in the directory"}, status_code=404)
    
    if os.name == "nt":  # Windows
        wrapper = "gradlew.bat"
        # On Windows it’s often simpler to run under shell so the .bat is recognized
        shell_flag = True
    else:
        wrapper = "./gradlew"
        shell_flag = False
    cmds = ["startFuseki", "owlQuery", "stopFuseki"]

    for subcmd in cmds:
        print(f"Running command: {wrapper} {subcmd}")
        logger.info(f"Running command: {wrapper} {subcmd}")
        proc = subprocess.run(
            [wrapper, subcmd],
            cwd=PROJECT_ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            shell=shell_flag
        )    
        # 5. Persist logs
        log_file = LOG_DIR / f"querylogs_code{proc.returncode}.log"
        log_file.parent.mkdir(parents=True, exist_ok=True)
        with log_file.open("a") as log_file_f:
            log_file_f.write(proc.stdout)
        
    # 6. Prepare response URL
    #    We’ll serve BUILD_DIR on port 8080 (see next steps),
    #    so we just point clients there under /browse/
    if os.path.exists(BUILD_DIR / "results"):
        files = os.listdir(BUILD_DIR / "results")
    else:
        files = []
    print("files", files)
    logger.debug(f"files {files}")
    # 7. Return JSON with status, code, and browse URL
    return {
        "exit_code": proc.returncode,
        "log_path": str(log_file.relative_to(BUILD_DIR)),
        "results": files,
    }