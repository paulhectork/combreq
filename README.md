# FUSER

`fuser` (for `FUSE-Requirements`) is a small CLI to fuse multiple python requirements files into a single one,
detecting dependendy conflicts along the way.

path to input/output requirements are read from the command line, requirements
are fused and validated and an output file is written. if no `-o` `--output`
is provided, output is written to stdout.

## INSTALL

requires `python3.10` or more. no external libraries used, so no need to lose time setting up venvs.

```bash
git clone git@github.com:paulhectork/fuser.git
```

## USAGE

feed `fuser` pipe-separated paths to requirements files and see the magic in action !

```bash
# a small example
python3.10 fuser.py \
    -i "./LinePred/requirements.txt|./DTLR/requirements.txt" \ 
    -o requirements.txt \
    -w
```

```
usage: fuse_requirements [-h] -i INPUT [-o OUTPUT] [-w]

a small CLI to fuse multiple python requirements files into a single one, detecting dependendy
conflicts along the way.

options:
  -h, --help            show this help message and exit
  -i INPUT, --input INPUT
                        relative or absolute path to requirements files. pipe '|' separated if many are
                        provided
  -o OUTPUT, --output OUTPUT
                        relative or absolute path to output requirements file. if none is provided,
                        will output to stdout
  -w, --overwrite       overwrite output file. defaults to false

```

## LICENSE

gnu-gpl 3.0
