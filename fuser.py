"""
a small CLI to fuse multiple python requirements files into a single one,
detecting dependendy conflicts along the way.

path to input/output requirements are read from the command line, requirements
are fused and validated and an output file is written. if no `-o` `--output`
is provided, output is written to stdout
"""

#NOTE so far, only major and minor versions are checked. fixes (ie, the `.1` in `v3.2.1`) are not checked
#TODO more file-grained check of `<=` vs `<` and `>=` vs `>`
#TODO rework `rgx` for comma-separated version specs. i.e, "Pillow>2.0,3.0"
#TODO handle recursive references to other requirements files

import os
import re
import math
import argparse
import typing as t

# -------------------------------------
# helpers

class DependencyConflictError(ValueError):
    pass

class UnsupportedOperatorError(ValueError):
    pass

root = os.path.dirname(os.path.realpath(__file__))

allowed_ops = ["<","<=","==",">=",">"]

# in: Pillow<=10.0.0 => out: ("Pillow", "<=", "10.0.0")
rgx = re.compile(r"([A-Za-z]+)([<>=]*)([\d\.]*)")

dependency_conflict_error_msg = lambda pkg, versions: f"dependency conflict for package '{pkg}' with versions {versions}"

def read_file(fp:str|os.PathLike) -> str:
    with open(fp, mode="r") as fh:
        return fh.read()

def write_file(fp:str, contents:str) -> None:
    with open(fp, mode="w") as fh:
        fh.write(contents)
    return

def version_number_to_float(v:str|None) -> float:
    return float(re.search("^\d+\.\d+", v)[0]) if v is not None else v

# -------------------------------------
# cli stuff

def init_cli():
    parser = argparse.ArgumentParser('fuser', description="a small CLI to fuse multiple python requirements files into a single one, detecting dependendy conflicts along the way.")
    parser.add_argument("-i", "--input", required=True, help="relative or absolute path to requirements files. pipe '|' separated if many are provided")
    parser.add_argument("-o", "--output", help="relative or absolute path to output requirements file. if none is provided, will output to stdout")
    parser.add_argument("-w", "--overwrite", action="store_true", default=False, help="overwrite output file. defaults to false")
    return parser


def validate_arguments(inputs: t.List[str], output:str, overwrite:bool) -> None:
    for _in in inputs:
        if not os.path.isfile(_in):
            raise FileNotFoundError(f"input file '{_in}' not found")
    if output is not None and os.path.isfile(output) and not overwrite:
        raise FileExistsError(f"output file '{output}' aldready exists. use -w --overwrite to bypass")
    return

# -------------------------------------
# pipeline

def parse_requirements(t:str) -> t.List[t.Tuple[str, str, str]]:
    """
    parse a requirements file into a list of strings
    :param t: the contents of a requirements file
    :returns:
        [ ("package", "operator?", "version?") ]
        ex: [('yapf', '==', '0.3.1'), ('timm', '', '')]
    """
    reqs = []
    for r in t.split("\n"):
        if len(r) and not r.startswith("#"):
            if re.search(r"^(--|git\+)", r):
                reqs.append(( r, "", "" ))
            else:
                match = rgx.search(r)
                reqs.append(( match[1], match[2], match[3] ))
    return reqs


def fuser(
    reqs_list: t.List[ t.List[ t.Tuple[str, str, str] ] ]
) -> t.Dict[str, t.List[ t.Tuple[str, float] ]]:
    """
    fuse requirements file and detect version errors, if any

    :example:
    >>> reqs_list = [
    ...     [('wandb', '', ''), ('pytorch', '>=', '2.2')],
    ...     [('wandb', '', ''), ('pytorch', '<=', '3.0'), ('editdistance', '==', '3.2')]
    ... ]
    >>> fuser(reqs_list)
    ... # returns
    ... {
    ...     'wandb': [('', ''),
    ...     'pytorch': [('>=', 2.2), ('<=', 3.0)],
    ...     'editdistance':  [('==', 3.2)]
    ... }

    :param reqs_list: list of requirements returned by `parse_requirements`.parse_requirements
    :returns: fused requirements, as a dict
    """
    # all individidual packages, without version numbers
    pkgs = set([
        item[0]
        for reqs in reqs_list
        for item in reqs
    ])
    # packages mapped to list of ("comparison operator", "version")
    pkgs_to_versions = {}

    for pkg in pkgs:
        # a list of `("comparison operator", version)`
        versions: t.List[t.Tuple[str, float]] = [
            ( item[1], version_number_to_float(item[2]) )
            for reqs in reqs_list
            for item in reqs
            if item[0] == pkg
            and len(item[2])  #  only add item if there's a version number
        ]

        # more than 1 version for pkg => resolve dependency errors
        if len(versions) == 0:
            versions = [("", "")]
        elif len(versions) == 1:
            versions = versions  # useless but whatever

        # there are several versions specifications for the same package. find a version specification that satistifes all individual specs. 
        # this is done by computing, for each version spec, a range of [min, max] allowed versions, and then computing the intersection of all those ranges. if no valid intersection is found, there is a conflict
        else:
            # dict of { operator: [sorted list of versions for that operator] }
            versions_by_op = {
                op: sorted(_v for (_op,_v) in versions if _op==op)
                for (op,v) in versions
            }

            # match each operator to an allowed range of versions
            op_range = {}
            for op, versions in versions_by_op.items():
                if op in ["<=", "<"]:
                    op_range[op] = [0, versions[0]]
                elif op in [">=", ">"]:
                    op_range[op] = [versions[-1], math.inf]
                elif op == "==" and len(set(versions)) > 1:
                    raise DependencyConflictError(dependency_conflict_error_msg(pkg, versions))
                elif op == "==":
                    op_range[op] = [versions[0], versions[0]]
                else:
                    raise UnsupportedOperatorError(f"unsupported operator {op}. epected one of {alowed_ops}")

            # compute an intersection between all ranges
            roof  = max(_range[1] for _range in  op_range.values())
            floor = min(_range[0] for _range in op_range.values())

            if roof < floor:
                raise DependencyConflictError(dependency_conflict_error_msg(pkg, versions))

            versions = []
            if roof == math.inf:
                versions = (
                    [(">=", floor)] if ">=" in op_range.keys() and floor == op_range[">="]
                    else [(">", floor)]
                )
            elif floor == 0:
                versions = (
                    [("<=", roof)] if "<=" in op_range.keys() and roof == op_range["<="]
                    else [("<", roof)]
                )
            else:
                versions = [(">=", floor), ("<=", roof)]
        pkgs_to_versions[pkg] = versions
    return pkgs_to_versions

def to_string(reqs_obj: t.Dict[str, t.List[ t.Tuple[str, float] ]]) -> str:
    return "\n".join(
        f"{pkg}{','.join(f'{op}{version}' for (op, version) in op_version)}"
        for pkg, op_version in reqs_obj.items()
    )

# -------------------------------------
# tadaaaaaaa

if __name__ == "__main__":
    parser = init_cli()
    args = parser.parse_args()
    input_reqs_files = [ i.strip() for i in args.input.split("|") ]
    output = args.output
    overwrite = args.overwrite

    # will raise if arguments are invalid
    validate_arguments(input_reqs_files, output, overwrite)

    input_requirements = [ read_file(reqs_file) for reqs_file in input_reqs_files ]
    input_requirements = [ parse_requirements(reqs) for reqs in input_requirements ]
    fused_reqs = fuser(input_requirements)
    fused_reqs = to_string(fused_reqs)

    if output:
        write_file(output, fused_reqs)
    else:
        print(fused_reqs)


