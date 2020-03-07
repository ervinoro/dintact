# dintact

Make sure your data is still intact.

A simple utility, mostly geared towards enabling you to notice when cold backup of data needs to be re-created due to failing storage or similar issues. It keeps a simple text file `index.txt` listing hashes of all files in your archive.

It assumes that you have a hot version of a file archive (on your pc maybe), and a cold version of the exact same archive (on a removable storage maybe), and that you occasionally sync and verify them.

## Install

Depends on Python 3.8+ and two pip libraries: xxhash and tqdm.

    pip install -r requirements.txt

## Usage
`dintact check <cold_directory>`

--- or ---

`dintact sync <hot_directory> <cold_directory>`

Basic operations:
1. insert
2. delete
3. modify
4. move 