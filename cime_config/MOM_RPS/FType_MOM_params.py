import os
import re
from collections import OrderedDict

from CIME.ParamGen.paramgen import ParamGen

MAX_LINE_LENGTH = 256

class FType_MOM_params(ParamGen):
    """Encapsulates data and read/write methods for MOM6 case parameter files: MOM_input, user_nl."""

    supported_formats_out = ["MOM_input", "MOM_override"]

    @classmethod
    def from_MOM_input(cls, input_path):
        """
        Reads in a given MOM_input file (or user_nl_mom) and initializes an FType_MOM_params
        object. This method is an alternative to from_yaml(input_path) and from_json(input_path)
        methods already available from the base MOM_RPS class.

        Parameters
        ----------
        input_path: str
            Path to MOM_input file to read in and generate a FType_MOM_params object.
        """

        _data = FType_MOM_params._read_MOM_input(input_path)
        return FType_MOM_params(_data)

    @staticmethod
    def _read_MOM_input(input_path):
        """Reads in input files in MOM_input syntax. Note that this method may be used to
        read in MOM_override and user_nl_mom too, since the syntax is the same, but
        write methods for MOM_input and MOM_override are different."""

        _data = OrderedDict()
        with open(input_path, "r") as param_file:
            within_comment_block = False
            curr_module = "Global"
            logical_line = ""
            for raw_line in param_file:
                line = raw_line.strip()
                if len(line) > 1:
                    

                    # check if within comment block.
                    if (not within_comment_block) and line.strip()[0:2] == "/*":
                        within_comment_block = True

                    if within_comment_block and line.strip()[-2:] == "*/":
                        within_comment_block = False
                        continue
                    # Join continuation lines ending with '&'
                    if logical_line:
                        # Continuing a logical line
                        logical_line += " " + line.lstrip()
                    else:
                        logical_line = line

                    # Check if logical_line ends with '&' for continuation
                    if logical_line.endswith("&"):
                        # Remove trailing '&' and continue reading next line
                        logical_line = logical_line[:-1].rstrip()
                        continue

                    line_s = logical_line.split()
                    if (
                        not within_comment_block and line_s[0][0] != "!"
                    ):  # not a single comment line either
                        # check format:
                        if (curr_module == "Global") and logical_line.strip()[-1] == "%":
                            curr_module = logical_line.strip()[:-1]
                        elif curr_module != "Global" and logical_line.strip()[0] == "%":
                            curr_module = "Global"
                        else:
                            # discard override keyword if provided:
                            if line_s[0] == "#override" and len(line_s) > 1:
                                line_s = line_s[1:]
                            line_j = " ".join(line_s)

                            # now parse the line:
                            if re.search("^\s*\w*\s*=\s*[^ \t\n\r\f\v!]+", line_j):
                                eq_ix = line_j.index("=")
                                varname = line_j[:eq_ix].strip()
                                val_str = line_j[eq_ix + 1 :].strip()
                                if "!" in val_str:
                                    val_str = val_str.split("!")[
                                        0
                                    ]  # discard the comment in val str, if there is

                                # add this module if not added before:
                                if not curr_module in _data:
                                    _data[curr_module] = dict()

                                # check if param already provided:
                                if varname in _data[curr_module]:
                                    raise SystemExit(
                                        "ERROR: "
                                        + varname
                                        + " listed more than once in "
                                        + input_path
                                    )

                                # enter the parameter in the dictionary:
                                _data[curr_module][varname] = {"value": val_str}
                            else:
                                raise SystemExit(
                                    "ERROR: Cannot parse the following line in user_nl_mom: "
                                    + logical_line
                                )
                logical_line = "" # Reset for next parameter

            # Check if there is unclosed block:
            if within_comment_block:
                raise SystemExit("ERROR: faulty comment block!")
            if curr_module != "Global":
                raise SystemExit("ERROR: faulty module block!")

        return _data

    def write(self, output_path, output_format, case=None, def_params=None):
        if output_format == "MOM_input":
            assert case != None, "Must provide a case object to write out MOM_input"
            self._write_MOM_input(output_path, case)
        elif output_format == "MOM_override":
            assert (
                def_params != None
            ), "Must provide a def_params object to write out MOM_override"
            self._write_MOM_override(output_path, def_params)

    def _write_MOM_input(self, output_path, case):
        """writes a MOM_input file from a given json or yaml parameter file in accordance with
        the guards and additional parameters that are passed."""

        # From the general template (MOM_input.yaml), reduce a custom MOM_input for this case
        self.reduce(lambda varname: case.get_value(varname))

        # 2. Now, write MOM_input

        MOM_input_header = """/* WARNING: DO NOT EDIT this file. Any changes you make will be
        overriden. To make changes in MOM6 parameters within CESM
        framework, use SourceMods or user_nl_mom mechanisms.

        This input file provides the adjustable run-time parameters
        for version 6 of the Modular Ocean Model (MOM6). By default,
        this file contains the out-of-the-box CESM configuration. A
        full list of parameters for this case can be found in the
        corresponding MOM_parameter_doc.all file which is generated
        by the model at runtime. */\n\n"""

        with open(os.path.join(output_path), "w") as MOM_input:

            MOM_input.write(MOM_input_header)

            tab = " " * 32
            for module in self._data:

                # Begin module block:
                if module != "Global":
                    MOM_input.write(module + "%\n")

                for var in self._data[module]:
                    val = self._data[module][var]["value"]
                    if val == None:
                        continue

                    # write "variable = value" pair
                    if isinstance(val, float):
                        val_str = "%.16g" % val
                        if ("." not in val_str) and ("e" not in val_str.lower()):
                            val_str += ".0"
                        MOM_input.write(var + " = " + val_str + "\n")
                    else:
                        wrapped_lines = wrap_MOM_string(var, str(val))
                        for line in wrapped_lines:
                            MOM_input.write(line + "\n")

                    # Write the variable description:
                    var_comments = self._data[module][var]["description"].split("\n")
                    if len(var_comments[-1]) == 0:
                        var_comments.pop()
                    for line in var_comments:
                        MOM_input.write(tab + "! " + line + "\n")
                    MOM_input.write("\n")

                # End module block:
                if module != "Global":
                    MOM_input.write("%" + module + "\n")

    def _write_MOM_override(self, output_path, def_params):

        MOM_override_header = """/* WARNING: DO NOT EDIT this file! Any user changes made in files
        in RUNDIR will be overriden. This file is automatically generated.
        MOM6 parameter changes may ve made via SourceMods or user_nl_mom
        within CASEROOT.*/\n"""

        with open(os.path.join(output_path), "w") as MOM_override:

            MOM_override.write(MOM_override_header)

            for module in self._data:
                # Begin module block:
                if module != "Global":
                    MOM_override.write("\n" + module + "%\n")

                for var in self._data[module]:
                    val = self._data[module][var]["value"]

                    # parameter is provided in both MOM_input and user_nl_mom
                    if module in def_params.data and var in def_params.data[module]:

                        # values are different
                        if val != def_params.data[module][var]["value"]:
                            wrapped_lines = wrap_MOM_string(var, val, prefix="#override ")
                            for line in wrapped_lines:
                                MOM_override.write(line + "\n")

                        # values are the same
                        else:
                            MOM_override.write(
                                "!!! {varname} = {value} !(UNCHANGED)\n".format(
                                    varname=var, value=val
                                )
                            )

                    # parameter is provided only in user_nl_mom
                    else:
                        wrapped_lines = wrap_MOM_string(var, val)
                        for line in wrapped_lines:
                            MOM_override.write(line + "\n")

                # End module block:
                if module != "Global":
                    MOM_override.write("%" + module + "\n\n")

def wrap_MOM_string(var, val, prefix=None, max_len=MAX_LINE_LENGTH):
    """
    Format a MOM6-style parameter assignment string, wrapping across multiple lines if necessary using an & as described in MOM6/src/framework/MOM_file_parser.F90.

    Parameters
    ----------
    var : str
        The name of the parameter variable (e.g., 'OBC_SEGMENT_001_DATA').
    val : str 
        The value to assign to the variable
    prefix : str or None, optional
        Optional prefix to include before the variable assignment. Used for "#override " If None, uses just "<var> = ".
    max_len : int, optional
        Maximum allowed line length. Lines exceeding this will be wrapped with continuation lines.

    Returns
    -------
    lines : list of str
        List of strings representing wrapped lines in MOM6-compatible Fortran format.
    
    Examples
    --------
    >>> wrap_MOM_string('varname', 'a_long_value_string', prefix='  ', max_len=20)
    ['  varname = a_long_val"&',
     '"ue_string"']
    """

    # Add passed in prefix or default to "var = "
    if prefix is None:
        prefix = var + " = "
    else:
        prefix = prefix + var + " = "

    # Convert value to string
    val_str = str(val)

    # Create list of lines
    lines = []

    # If the value is empty, return an empty list, if not start iterating
    while val_str:

        # On the first line
        if not lines:

            # Calculate space for the first line based on the maximum length allowed. 
            space_left = max_len - len(prefix)
            chunk = val_str[:space_left]
            val_str = val_str[space_left:]
            line = prefix + chunk

            # If there is more value string left, add continuation character
            if val_str:
                line += "\"&"

            # Add line
            lines.append(line)
        
        # For continuation lines
        else:
            # Add Quotation
            continuation_prefix = "\""

            # Calculate Space
            space_left = max_len - len(continuation_prefix)
            chunk = val_str[:space_left]
            val_str = val_str[space_left:]
            line = continuation_prefix + chunk

            # If there is more value string left, add continuation character
            if val_str:
                line += "\"&"

            # Add line
            lines.append(line)

    return lines
