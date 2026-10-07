import sys
import subprocess
import argparse
import os

def main():
    parser = argparse.ArgumentParser(
        description="Compile and upload source files to WordPress."
    )
    parser.add_argument(
        "filename",
        help="The filename without extension (e.g., 'my_post')"
    )
    parser.add_argument(
        "--only-upload",
        action="store_true",
        help="Skip the compilation step and only upload"
    )

    args = parser.parse_args()

    filename = args.filename
    input_path = f"./src/{filename}.txt"
    output_path = f"./build/{filename}.txt"

    if not args.only_upload:
        print(f"Compiling {input_path}...")

        compile_result = subprocess.run([
            "python3", "./tools/compiler.py",
            "--input", input_path,
            "--output", output_path
        ])

        if compile_result.returncode == 0:
            print("Compile OK")
        else:
            print("Compile FAIL")
            sys.exit(1)
    else:
        print("Skipping compilation step")

    print(f"Uploading {output_path}...")
    upload_result = subprocess.run([
        "python3", "./tools/uploader.py",
        "--post", output_path
    ])

    if upload_result.returncode != 0:
        print("Upload FAIL")
        sys.exit(1)

if __name__ == "__main__":
    main()
