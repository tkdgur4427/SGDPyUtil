import json
from SGDPyUtil.logging_utils import Logger


def read_json_data(filename: str):
    try:
        json_data = open(filename).read()
    except:
        Logger.instance().info(f"[ERROR] could not read JSON file {filename}")
        return None

    try:
        data = json.loads(json_data)
    except:
        Logger.instance().info(f"[ERROR] could not parse JSON document")
        return None

    return data


def write_json_data(data, filename):
    with open(filename, "w") as outfile:
        json.dump(data, outfile)
