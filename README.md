# dintact

Make sure your data is still intact.

A simple utility, mostly geared towards enabling you to notice when cold backup of data needs to be re-created due to failing storage or similar issues. It keeps a simple text file `index.txt` listing hashes of all files in your archive.

It assumes that you have a hot version of a file archive (on your pc maybe), and a cold version of the exact same archive (on a removable storage maybe), and that you occasionally sync and verify them. It uses non-cryptographic hash to notice any file corruption, and does not protect against malicious interference.

## Requirements

Depends on Python 3.8+ and some pip libraries.

`pip install -r requirements.txt`

The entire index must fit in memory, but files are read chunk-by-chunk.

## Usage

`dintact check <cold_directory>`

--- or ---

`dintact sync <hot_directory> <cold_directory>`

### Ignored files

dintact respects any `.gitignore` files it finds, and does **not** back up files matched by these.

### Testing

`python -m unittest discover test`
