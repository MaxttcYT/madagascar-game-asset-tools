from bspLib import parse_file, write_obj
import sys
import json
import os

script_dir = os.path.dirname(os.path.abspath(__file__))

OUT_FOLDER = os.path.join(script_dir, "parsed_bsps")
MAKE_OBJ = True
TEXTURE_PREFIX = "textures/"
GEO_SCALE= 1

def parseBSP(file_path, output_folder=True, make_obj=False, texture_prefix=""):
    IS_COLLISION = "Col" in file_path

    os.makedirs(output_folder, exist_ok=True)

    if IS_COLLISION:
        print("Collision mode enabled")

    try:
        result = parse_file(file_path, IS_COLLISION)
        if make_obj:
            base_name = os.path.splitext(os.path.basename(file_path))[0]
            write_obj(output_folder, base_name, result, texture_prefix, GEO_SCALE)
        else:
            with open(os.path.join(output_folder, "parser.json"), "w") as f:
                json.dump(result, f, indent=2, default=str)

    except FileNotFoundError:
        print(f"Error: File not found: {file_path}")
        sys.exit(1)

    except Exception as e:
        print(f"Error parsing file: {e}")
        raise

if __name__ == "__main__":
    BATCH_INPUT_FOLDER = os.path.join(script_dir, "bsps")
    
    for filename in os.listdir(BATCH_INPUT_FOLDER):
        if filename.lower().endswith(".bsp"):
            file_path = os.path.join(BATCH_INPUT_FOLDER, filename)
            print(f"Parsing BSP: {file_path}")
            parseBSP(file_path, OUT_FOLDER, MAKE_OBJ, TEXTURE_PREFIX)