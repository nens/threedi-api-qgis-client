import os
import shutil
import re


def get_version(directory):
    metadata = os.path.join(directory, "metadata.txt")
    reg = '\nversion=(.+)\n'
    version = ""
    with open(metadata, "r") as f:
        m0 = re.search(reg, f.read())
        if m0:
            version = m0.group(1)
    return version


if __name__ == "__main__":
    print('ZIPPING PLUGIN STARTED')
    this_dir = os.path.dirname(os.path.realpath(__file__))
    plugin_dirname = "threedi_api_qgis_client"
    plugin_path = os.path.join(this_dir, plugin_dirname)
    plugin_version = get_version(plugin_path)
    zip_filename = f"{plugin_dirname}_{plugin_version}"
    plugin_zip_path = os.path.join(this_dir, zip_filename)
    shutil.make_archive(plugin_zip_path, 'zip', this_dir, plugin_dirname)
    print('ZIPPING PLUGIN FINISHED')
