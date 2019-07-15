# dintact

Make sure your data is still intact.

A simple utility, mostly geared towards enabling you to notice when cold backup of data needs to be re-created due to failing storage or similar issues. It keeps a simple index file listing hashes of all files in your archive.

## Install

Depends on Python 3.5+ and two pip libraries: xxhash and tqdm.

    pip install -r requirements.txt

## Usage

    dintact.py [-h] [-a ADD] index

* `-a`: File or directory to start tracking. Repeat multiple times to add several things at once.
* `index`: Location of the index files where hashes are (to be) stored.

Note that dintact uses file paths relative to current working directory.
